#!/bin/bash

# Exit on any error
set -e

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
    python3-venv

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

echo "Setup complete!"
echo ""
echo "Services status:"
echo "- Nginx: $(systemctl is-active nginx)"
echo "- Samba: $(systemctl is-active smbd)"
echo "- Audio Recorder: $(systemctl is-active ps-audio-recorder)"
echo ""
echo "Verify you can access:"
echo "- Web: http://$(hostname).local"
echo "- Samba: \\\\$(hostname).local\\recordings"
echo ""
echo "Note: A reboot is recommended to apply audio configuration changes"