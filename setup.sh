#!/bin/bash

# Exit on any error
set -e

# Resolve the directory of this script to allow running from any CWD
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Normalize text file to UNIX LF endings to avoid shebang /bin/bash^M issues
normalize_unix() {
    local f="$1"
    if [ -f "$f" ]; then
        # Try dos2unix if available, otherwise use sed fallback
        if command -v dos2unix >/dev/null 2>&1; then
            dos2unix -q "$f" || true
        else
            sed -i 's/\r$//' "$f" || true
        fi
    fi
}

# Must run as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

# Install required packages
echo "Installing required packages..."
apt update
apt install -y \
    nginx \
    samba \
    python3-evdev \
    python3-venv \
    inotify-tools \
    mp3gain

# Add pi user to audio group
usermod -a -G audio pi

# Disable onboard audio to ensure USB is default
echo "blacklist snd_bcm2835" >> /etc/modprobe.d/raspi-blacklist.conf

# Create audiofiles group if it doesn't exist
if ! getent group audiofiles > /dev/null; then
    groupadd audiofiles
fi

# Create recordings directory
mkdir -p /srv/recordings

# Create log directory and file
mkdir -p /var/log
touch /var/log/audio-recorder.log
chown pi:audiofiles /var/log/audio-recorder.log
chmod 664 /var/log/audio-recorder.log

# Create bulb cache directory
mkdir -p /var/lib/audio-recorder
chown pi:audiofiles /var/lib/audio-recorder
chmod 775 /var/lib/audio-recorder

# Add users to audiofiles group
usermod -a -G audiofiles www-data
usermod -a -G audiofiles pi
usermod -a -G audiofiles nobody  # for Samba

# Set directory ownership and permissions
chown pi:audiofiles /srv/recordings
chmod 775 /srv/recordings
chmod g+s /srv/recordings  # Set SGID bit so new files inherit group

# Create Nginx configuration
cat > /etc/nginx/sites-available/default << 'EOF'
server {
        listen 80 default_server;
        listen [::]:80 default_server;

        server_name _;

        location / {
                root /srv/recordings;
                autoindex on;
        }

        location /api/ {
            proxy_pass http://localhost:5000/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
}
EOF

# Create Samba configuration
cat > /etc/samba/smb.conf << 'EOF'
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

# Create systemd service
cat > /etc/systemd/system/ps-audio-recorder.service << 'EOF'
[Unit]
Description=Piano Studio Audio Recorder
After=network.target

[Service]
ExecStart=/home/pi/ps-audio-recorder/start-recorder.sh
WorkingDirectory=/home/pi/ps-audio-recorder
StandardOutput=append:/var/log/audio-recorder.log
StandardError=append:/var/log/audio-recorder.log
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF

# Set proper permissions for service file and start script
chmod 644 /etc/systemd/system/ps-audio-recorder.service
chmod +x /home/pi/ps-audio-recorder/start-recorder.sh

# Reload systemd, enable and start service
systemctl daemon-reload
systemctl enable ps-audio-recorder
systemctl start ps-audio-recorder

# Restart other services
systemctl restart smbd
systemctl restart nginx

# ------------------------------
# ReplayGain Auto-Processor Service
# ------------------------------

# Install watcher script to home directory if not already there
install -d -m 0755 /home/pi/ps-audio-recorder

SRC_WATCHER_SH="$SCRIPT_DIR/ps-audio-recorder/replaygain-watcher.sh"
DEST_WATCHER_SH="/home/pi/ps-audio-recorder/replaygain-watcher.sh"
if [ "$SRC_WATCHER_SH" != "$DEST_WATCHER_SH" ]; then
    install -m 0755 "$SRC_WATCHER_SH" "$DEST_WATCHER_SH"
else
    chmod 0755 "$DEST_WATCHER_SH" || true
fi
normalize_unix "$DEST_WATCHER_SH"

SRC_ENV_EXAMPLE="$SCRIPT_DIR/ps-audio-recorder/replaygain-watcher.env.example"
DEST_ENV="/home/pi/ps-audio-recorder/replaygain-watcher.env"
if [ ! -f "$DEST_ENV" ]; then
    if [ -f "$SRC_ENV_EXAMPLE" ] && [ "$SRC_ENV_EXAMPLE" != "$DEST_ENV" ]; then
        install -m 0644 "$SRC_ENV_EXAMPLE" "$DEST_ENV"
    fi
fi
normalize_unix "$DEST_ENV"

chown -R pi:pi /home/pi/ps-audio-recorder

cat > /etc/systemd/system/ps-replaygain.service << 'EOF'
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

chmod 644 /etc/systemd/system/ps-replaygain.service
normalize_unix /etc/systemd/system/ps-replaygain.service

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
echo ""
echo "Note: A reboot is recommended to apply audio configuration changes"