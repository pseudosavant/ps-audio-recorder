#!/bin/bash

set -euo pipefail

# Resolve the directory of this script to allow running from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SUFFIX="$(date +%Y%m%d_%H%M%S)"
OVERWRITE_EXISTING=1
UPGRADE_MODE=0
APP_CONFIG_DIR="/etc/ps-audio-recorder"
APP_ENV_FILE="$APP_CONFIG_DIR/ps-audio-recorder.env"
SRC_APP_ENV_EXAMPLE="$SCRIPT_DIR/ps-audio-recorder/ps-audio-recorder.env.example"
APP_HOME="/home/pi/ps-audio-recorder"
REQUIREMENTS_FILE="$SCRIPT_DIR/ps-audio-recorder/requirements.txt"

usage() {
    cat <<'EOF'
Usage: ./setup.sh [--no-overwrite]

Options:
  --no-overwrite  Do not replace existing config files; only create missing ones.
  --upgrade       Force upgrade behavior (restart managed services).
  -h, --help      Show this help text.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-overwrite)
            OVERWRITE_EXISTING=0
            shift
            ;;
        --upgrade)
            UPGRADE_MODE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
done

log() {
    echo "[setup] $*"
}

# Normalize text file to UNIX LF endings to avoid shebang /bin/bash^M issues.
normalize_unix() {
    local f="$1"
    if [[ -f "$f" ]]; then
        if command -v dos2unix >/dev/null 2>&1; then
            dos2unix -q "$f" || true
        else
            sed -i 's/\r$//' "$f" || true
        fi
    fi
}

backup_file() {
    local target="$1"
    local backup="${target}.bak.${BACKUP_SUFFIX}"
    if [[ -f "$target" && ! -f "$backup" ]]; then
        cp -a "$target" "$backup"
        log "Backed up $target -> $backup"
    fi
}

write_managed_file() {
    local target="$1"
    local mode="$2"
    local label="$3"
    local tmp
    tmp="$(mktemp)"
    cat > "$tmp"
    normalize_unix "$tmp"

    if [[ -f "$target" ]] && cmp -s "$tmp" "$target"; then
        rm -f "$tmp"
        log "$label unchanged: $target"
        return 0
    fi

    if [[ -f "$target" && "$OVERWRITE_EXISTING" -eq 0 ]]; then
        rm -f "$tmp"
        log "Skipping existing $label (--no-overwrite): $target"
        return 0
    fi

    if [[ -f "$target" ]]; then
        backup_file "$target"
    fi

    install -d -m 0755 "$(dirname "$target")"
    install -m "$mode" "$tmp" "$target"
    rm -f "$tmp"
    log "Wrote $label: $target"
}

ensure_line_in_file() {
    local line="$1"
    local file="$2"
    touch "$file"
    if ! grep -Fqx "$line" "$file"; then
        echo "$line" >> "$file"
        log "Added line to $file: $line"
    else
        log "Line already present in $file: $line"
    fi
}

add_user_to_group() {
    local user="$1"
    local group="$2"
    if id -u "$user" >/dev/null 2>&1; then
        usermod -a -G "$group" "$user"
    else
        log "User '$user' not found; skipping group '$group' assignment"
    fi
}

ensure_python_dependencies() {
    local venv_path="$APP_HOME/.venv"
    local pip_path="$venv_path/bin/pip"

    if [[ ! -d "$APP_HOME" ]]; then
        log "App directory not found at $APP_HOME; skipping dependency refresh"
        return 0
    fi

    if [[ ! -d "$venv_path" ]]; then
        log "Creating virtual environment at $venv_path"
        python3 -m venv "$venv_path" --system-site-packages
    fi

    if [[ ! -x "$pip_path" ]]; then
        log "pip not found in venv at $pip_path; skipping dependency refresh"
        return 0
    fi

    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        log "Installing Python dependencies from $REQUIREMENTS_FILE"
        "$pip_path" install -r "$REQUIREMENTS_FILE"
    else
        log "Requirements file not found; installing fallback dependency python-kasa"
        "$pip_path" install python-kasa
    fi
}

if [[ "$EUID" -ne 0 ]]; then
    echo "Please run as root" >&2
    exit 1
fi

log "Installing required packages..."
apt update
apt install -y \
    nginx \
    samba \
    python3-evdev \
    python3-venv \
    python3-pip \
    inotify-tools \
    mp3gain

ensure_python_dependencies

# Add pi user to audio group (if present).
add_user_to_group pi audio

# Disable onboard audio to ensure USB is default, without duplicate entries.
ensure_line_in_file "blacklist snd_bcm2835" /etc/modprobe.d/raspi-blacklist.conf

if ! getent group audiofiles >/dev/null; then
    groupadd audiofiles
fi

mkdir -p /srv/recordings
mkdir -p /var/log
mkdir -p /var/lib/audio-recorder
install -d -m 0755 "$APP_CONFIG_DIR"

OWNER_USER="pi"
if ! id -u "$OWNER_USER" >/dev/null 2>&1; then
    OWNER_USER="root"
    log "User 'pi' not found; using '$OWNER_USER' for ownership where needed"
fi

touch /var/log/audio-recorder.log
chown "$OWNER_USER":audiofiles /var/log/audio-recorder.log
chmod 664 /var/log/audio-recorder.log

chown "$OWNER_USER":audiofiles /var/lib/audio-recorder
chmod 775 /var/lib/audio-recorder

add_user_to_group www-data audiofiles
add_user_to_group pi audiofiles
add_user_to_group nobody audiofiles

chown "$OWNER_USER":audiofiles /srv/recordings
chmod 775 /srv/recordings
chmod g+s /srv/recordings

if [[ ! -f "$APP_ENV_FILE" ]]; then
    if [[ -f "$SRC_APP_ENV_EXAMPLE" ]]; then
        install -m 0644 "$SRC_APP_ENV_EXAMPLE" "$APP_ENV_FILE"
        normalize_unix "$APP_ENV_FILE"
        log "Created recorder env file: $APP_ENV_FILE"
    else
        log "Recorder env example missing at $SRC_APP_ENV_EXAMPLE; skipping env file creation"
    fi
else
    log "Recorder env file already exists: $APP_ENV_FILE"
fi

write_managed_file /etc/nginx/sites-available/default 0644 "nginx site config" <<'EOF'
server {
        listen 80 default_server;
        listen [::]:80 default_server;

        server_name _;

        location / {
                root /srv/recordings;
                autoindex on;
        }
}
EOF

write_managed_file /etc/samba/smb.conf 0644 "samba config" <<'EOF'
[global]
   workgroup = WORKGROUP
   server string = Recording Server
   log file = /var/log/samba/log.%m
   max log size = 1000
   logging = file
   map to guest = Bad User
   guest account = nobody

[recordings]
   comment = Audio Recordings
   path = /srv/recordings
   browseable = yes
   read only = no
   guest ok = yes
   guest only = yes
   force user = nobody
   force group = audiofiles
   create mask = 0664
   directory mask = 0775
EOF

write_managed_file /etc/systemd/system/ps-audio-recorder.service 0644 "recorder systemd unit" <<'EOF'
[Unit]
Description=Piano Studio Audio Recorder
After=network.target

[Service]
ExecStart=/home/pi/ps-audio-recorder/start-recorder.sh
WorkingDirectory=/home/pi/ps-audio-recorder
EnvironmentFile=-/etc/ps-audio-recorder/ps-audio-recorder.env
StandardOutput=append:/var/log/audio-recorder.log
StandardError=append:/var/log/audio-recorder.log
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF

if [[ -f /home/pi/ps-audio-recorder/start-recorder.sh ]]; then
    chmod +x /home/pi/ps-audio-recorder/start-recorder.sh
else
    log "start-recorder.sh not found at /home/pi/ps-audio-recorder; skipping chmod"
fi

systemctl daemon-reload
systemctl enable ps-audio-recorder
if [[ "$UPGRADE_MODE" -eq 1 ]]; then
    systemctl restart ps-audio-recorder || systemctl start ps-audio-recorder
else
    systemctl start ps-audio-recorder
fi

if [[ "$UPGRADE_MODE" -eq 1 ]]; then
    systemctl restart smbd || true
    systemctl restart nginx || true
else
    systemctl restart smbd
    systemctl restart nginx
fi

# ------------------------------
# ReplayGain Auto-Processor Service
# ------------------------------

install -d -m 0755 /home/pi/ps-audio-recorder

SRC_WATCHER_SH="$SCRIPT_DIR/ps-audio-recorder/replaygain-watcher.sh"
DEST_WATCHER_SH="/home/pi/ps-audio-recorder/replaygain-watcher.sh"
if [[ "$SRC_WATCHER_SH" != "$DEST_WATCHER_SH" ]]; then
    install -m 0755 "$SRC_WATCHER_SH" "$DEST_WATCHER_SH"
else
    chmod 0755 "$DEST_WATCHER_SH" || true
fi
normalize_unix "$DEST_WATCHER_SH"

SRC_ENV_EXAMPLE="$SCRIPT_DIR/ps-audio-recorder/replaygain-watcher.env.example"
DEST_ENV="/home/pi/ps-audio-recorder/replaygain-watcher.env"
if [[ ! -f "$DEST_ENV" ]]; then
    if [[ -f "$SRC_ENV_EXAMPLE" && "$SRC_ENV_EXAMPLE" != "$DEST_ENV" ]]; then
        install -m 0644 "$SRC_ENV_EXAMPLE" "$DEST_ENV"
    fi
fi
normalize_unix "$DEST_ENV"

if id -u pi >/dev/null 2>&1; then
    chown -R pi:pi /home/pi/ps-audio-recorder
fi

write_managed_file /etc/systemd/system/ps-replaygain.service 0644 "replaygain systemd unit" <<'EOF'
[Unit]
Description=ReplayGain Auto-Processor for /srv/recordings
After=network.target
RequiresMountsFor=/srv/recordings

[Service]
Type=simple
User=pi
Group=pi
EnvironmentFile=-/home/pi/ps-audio-recorder/replaygain-watcher.env
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin
ExecStart=/bin/bash /home/pi/ps-audio-recorder/replaygain-watcher.sh
WorkingDirectory=/home/pi/ps-audio-recorder
StandardOutput=journal
StandardError=journal
Nice=15
IOSchedulingClass=idle
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ProtectKernelTunables=yes
ProtectControlGroups=yes
ProtectKernelModules=yes
PrivateDevices=true
LockPersonality=true
RestrictRealtime=true
SystemCallFilter=@default
SystemCallErrorNumber=EPERM
ReadWritePaths=/srv/recordings /home/pi/ps-audio-recorder
ProtectClock=yes
IPAddressDeny=any
RestrictAddressFamilies=AF_UNIX

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ps-replaygain.service
systemctl restart ps-replaygain.service || systemctl start ps-replaygain.service

echo "Setup complete!"
echo ""
echo "Services status:"
echo "- Nginx: $(systemctl is-active nginx)"
echo "- Samba: $(systemctl is-active smbd)"
echo "- Audio Recorder: $(systemctl is-active ps-audio-recorder)"
echo "- ReplayGain: $(systemctl is-active ps-replaygain)"
echo ""
echo "Verify you can access:"
echo "- Web: http://$(hostname).local"
echo "- Samba: \\\\$(hostname).local\\recordings"
echo "- Recorder config: $APP_ENV_FILE"
echo ""
echo "Note: A reboot is recommended to apply audio configuration changes"
