# One-Button Audio Recording Solution

## Overview

This project is designed to provide a simple, one-button audio recording solution using a UAC USB audio interface connected to a Raspberry Pi Zero W. The system is controlled via a physical button and an LED indicator, with a web interface for additional control and playback of recorded audio files. The project also includes an anonymous Windows (SMB) file share for easy access to the recordings.

## Features

- **One-Button Recording**: Start and stop audio recording with a single button connected to the Raspberry Pi.
- **LED Indicator**: Provides visual feedback on the recording status. The LED is connected to a GPIO pin and will likely require a resistor.
- **Web Interface**: Allows for starting/stopping recordings and playing back recorded audio through a web browser.
- **SMB File Sharing**: Automatically shares recorded audio files over a network via an anonymous Windows (SMB) file share.

## Default GPIO Pin Configuration

- **Button**: GPIO pin 17.
- **LED**: GPIO pin 18.
  - **Note**: The LED will likely require a resistor to prevent damage.

## Recording File Location

- Recordings are saved in the `~/recordings` directory on the Raspberry Pi.

## Requirements

- Raspberry Pi Zero W
- UAC USB Audio Interface
- Python 3.x
- Flask (installed via `apt`)
- RPi.GPIO (installed via `apt`)
- nginx
- Samba
- arecord utility
- A web browser for accessing the web interface
- Network connection for SMB file sharing

## Installation

1. Clone this repository to your Raspberry Pi:
   ```sh
   git clone https://github.com/yourusername/one-button-audio-recorder.git
   ```

2. Install the necessary dependencies:
   ```sh
   sudo apt update
   sudo apt install python3 python3-flask python3-rpi.gpio nginx samba arecord
   ```

3. Configure Samba to share the `~/recordings` directory over SMB. Update `/etc/samba/smb.conf` with:
   ```
   [recordings]
   path = /home/pi/recordings
   browseable = yes
   read only = no
   guest ok = yes
   ```
   Then restart the Samba service:
   ```sh
   sudo systemctl restart smbd
   ```

4. Configure nginx to proxy requests to the Flask app. Add the following text to the `/etc/nginx/sites-available/default` file:
   ```
   location /api/ {
       proxy_pass http://localhost:5000/;  # Forward to your Flask app
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```
   Then restart the nginx service:
   ```sh
   sudo systemctl restart nginx
   ```

5. Connect the button and LED to the default GPIO pins as described above.

6. Run the Python script to start the recording service:
   ```sh
   python3 /home/pi/one-button-audio-recorder/ps-audio-recorder.py
   ```

## Running as a System Service

To run the script as a system service, follow these steps:

1. Create a service file for the script:
   ```sh
   sudo nano /etc/systemd/system/audio-recorder.service
   ```

2. Add the following content to the file:
   ```
   [Unit]
   Description=One-Button Audio Recorder
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /home/pi/one-button-audio-recorder/ps-audio-recorder.py
   WorkingDirectory=/home/pi/one-button-audio-recorder
   StandardOutput=inherit
   StandardError=inherit
   Restart=always
   User=pi

   [Install]
   WantedBy=multi-user.target
   ```

3. Reload the systemd daemon and enable the service:
   ```sh
   sudo systemctl daemon-reload
   sudo systemctl enable audio-recorder.service
   sudo systemctl start audio-recorder.service
   ```

4. The script will now automatically run as a service on boot.

## Usage

### Physical Button Control

- **Start/Stop Recording**: Press the button connected to the specified GPIO pin to start or stop recording.
- **LED Indicator**: The LED will light up during recording and turn off when recording stops.

### Web Interface

1. Open a web browser and navigate to the IP address of your Raspberry Pi. e.g. http://audio-recorder.local/audio-player.html 
2. Use the interface to start or stop recordings and play back previously recorded audio files.

### SMB File Sharing

- Access recorded audio files from any device on the network by connecting to the Raspberry Pi's SMB file share. The files are shared anonymously, so no login credentials are required.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## Author

- &copy; Paul Ellis (https://github.com/pseudosavant)