# One-Button Audio Recorder

## Overview

Headless Raspberry Pi recorder triggered by a Bluetooth HID clicker (or any keyboard) and optionally indicating state via a TP-Link Kasa smart bulb. Audio is captured with `arecord` and encoded on-the-fly to MP3 using `lame`. Designed for fast, reliable single-action start/stop with clear visual feedback and easily accessible files (optionally via SMB share).

Designed and tested primarily on a Raspberry Pi Zero 2 W (sufficient CPU for real-time MP3 at preset extreme). It should run on any full-size Raspberry Pi. NOTE: The original Pi Zero W (v1) often cannot keep up with live MP3 encoding at the current quality setting.

## Key Features

- Bluetooth clicker / wireless keyboard toggle (no GPIO wiring)
- MP3 pipeline: `arecord` -> `lame --preset extreme`
- Auto USB audio capability probing
- Kasa smart bulb tally (solid red while recording) with state restore
- Auto-discovery of bulb named "Recording Light" (same subnet)
- Safe timestamped filenames (`audio-recorder-YYYY-MM-DD-HH-MM-SS.mp3`)
- Auto-stop on Bluetooth device reconnection
- Systemd friendly, concise logging (`/var/log/audio-recorder.log`)
- Tested with Kasa KL125 color bulb

## Setup (Quick)

```sh
git clone https://github.com/yourrepo/ps-audio-recorder.git
cd ps-audio-recorder
chmod +x setup.sh
./setup.sh
```

The script:

- Installs required APT packages (ALSA, BlueZ, lame, etc.)
- Installs Python deps (e.g. python-kasa)
- Creates `/srv/recordings` with group permissions
- Touches/permissions the log file
- Optionally installs & enables the systemd service (if you confirm)
- Leaves config in `config.py` (edit if needed: bulb name, key code, etc.)

After running setup, pair your Bluetooth clicker (most show up as a HID keyboard). If pairing wasn’t done automatically inside the script, you can still use `bluetoothctl` manually; usually no config changes are needed if the remote emits key code 115 (F14). If not, update `TRIGGER_KEY_CODE` in `config.py`.

## Bluetooth Clicker
A generic Bluetooth “selfie” / presentation clicker works (appears as a tiny keyboard). These are inexpensive (typically < $5). Example model used for testing: https://www.amazon.com/gp/product/B0C6GXZRTJ  
Most send a single key code (often 115) which the recorder treats as the toggle.

## Kasa Smart Bulb

Automatically searches the local subnet for a TP-Link Kasa bulb whose alias matches `Recording Light` (`Config.BULB_NAME`). Tested with KL125. Other color Kasa models should work.

## Usage

Manual run (same script systemd uses):
```sh
~/ps-audio-recorder/start-recorder.sh
```
This script creates/activates the virtual environment and launches the recorder.  
- Press the Bluetooth remote button (mapped key code 115) or spacebar (if interactive TTY) to toggle recording.
- MP3 files appear in `/srv/recordings`.

Systemd service (already installed/enabled by setup.sh unless you skipped it):
```sh
sudo systemctl status ps-audio-recorder
journalctl -u ps-audio-recorder -f
```

## Configuration (config.py)

Adjust:

- SAMPLE_RATE / AUDIO_FORMAT fallback
- TRIGGER_KEY_CODE (remote key)
- BULB_NAME (default "Recording Light")
- RECORDING_EXTENSION (mp3)
- TIMESTAMP_FORMAT / RECORDING_PREFIX
- RECORDING_DIR / LOG_FILE

## Recording Details

Pipeline example:

```
arecord -r 48000 -t wav -f S32_LE -c 2 ... | lame --ignorelength --preset extreme --silent - file.mp3
```

Files created with group write (umask 002) for easy sharing (e.g. Samba/NFS if you add it later).

## Troubleshooting (Condensed)

- Remote not toggling: run `sudo evtest` to confirm key code; update `TRIGGER_KEY_CODE`.
- Audio device: `arecord -l` to verify card presence.
- Empty/short MP3: check log for early `arecord` or `lame` exit.
- Bulb not found: confirm alias, same subnet, run `python -m kasa discover`.

## Hardware / Performance Notes

- Zero 2 W and larger Pis: OK at `--preset extreme`.
- Original Zero W: likely too slow; lower quality (e.g. `-V5`) or record WAV then transcode offline.

## License

MIT (see LICENSE).

## Author

© John Paul Ellis (https://github.com/pseudosavant)