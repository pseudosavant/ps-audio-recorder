import RPi.GPIO as GPIO
import subprocess
import time
import os
import re
from datetime import datetime

# GPIO setup
BUTTON_PIN = 17
LED_PIN = 18

# Recording parameters
SAMPLE_RATE = 48000
RECORDING_DIR = os.path.expanduser("~/recordings")
MAX_RECORDING_TIME = 3600  # 1 hour

# Ensure the recording directory exists
os.makedirs(RECORDING_DIR, exist_ok=True)

# Global variables
recording = False
process = None

def log(message):
    print(f"{datetime.now()}: {message}")
    with open(os.path.expanduser("~/audio_recorder.log"), "a") as log_file:
        log_file.write(f"{datetime.now()}: {message}\n")

def get_usb_audio_device():
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        for line in lines:
            if 'USB Audio' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    card_info = parts[0].split(' ')
                    if len(card_info) >= 2:
                        card_num = card_info[1]
                        return f"hw:{card_num},0"
        log("No USB audio device found. Using default audio device.")
        return None
    except Exception as e:
        log(f"Error detecting USB audio device: {str(e)}")
        return None

def get_optimal_settings(device):
    try:
        result = subprocess.run(['arecord', '--dump-hw-params', '-D', device], capture_output=True, text=True)
        hw_params = result.stderr
        log(f"Hardware parameters for {device}:\n{hw_params}")
        
        # Get optimal format
        formats = re.findall(r'FORMAT: (.+)', hw_params)
        optimal_format = None
        if formats:
            available_formats = formats[0].split()
            preferred_formats = ['S24_3LE', 'S24_LE', 'S32_LE', 'S16_LE']
            for fmt in preferred_formats:
                if fmt in available_formats:
                    optimal_format = fmt
                    break
        
        # Get optimal channel count
        channels = re.findall(r'CHANNELS: (.+)', hw_params)
        optimal_channels = 1
        if channels:
            available_channels = channels[0].split()
            if '2' in available_channels:
                optimal_channels = 2
        
        log(f"Optimal format: {optimal_format}, Optimal channels: {optimal_channels}")
        return optimal_format, optimal_channels
    except Exception as e:
        log(f"Error getting device settings: {str(e)}")
        return None, 1

def setup_gpio():
    GPIO.setwarnings(False)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)

def start_recording():
    global recording, process
    if not recording:
        recording = True
        GPIO.output(LED_PIN, GPIO.HIGH)
        filename = os.path.join(RECORDING_DIR, f"auto-recorder-{datetime.now():%Y%m%d-%H%M%S}.wav")
        log(f"Starting recording: {filename}")
        
        audio_device = get_usb_audio_device()
        audio_format, channels = get_optimal_settings(audio_device) if audio_device else (None, 1)
        
        command = [
            "arecord",
            "-r", str(SAMPLE_RATE),
            "-c", str(channels),
            "-t", "wav",
            filename
        ]
        if audio_device:
            command.insert(1, "-D")
            command.insert(2, audio_device)
        if audio_format:
            command.insert(1, "-f")
            command.insert(2, audio_format)
        
        process = subprocess.Popen(command, stderr=subprocess.PIPE)
        time.sleep(1)
        if process.poll() is not None:
            _, err = process.communicate()
            log(f"Recording failed to start: {err.decode().strip()}")
            recording = False
            GPIO.output(LED_PIN, GPIO.LOW)
        else:
            log(f"Recording started successfully using device: {audio_device if audio_device else 'default'}, format: {audio_format if audio_format else 'default'}, and channels: {channels}")

def stop_recording():
    global recording, process
    if recording:
        recording = False
        GPIO.output(LED_PIN, GPIO.LOW)
        if process:
            process.terminate()
            process.wait()
            log("Stopped recording")
        process = None

def cleanup():
    stop_recording()
    GPIO.cleanup()
    log("Script terminated")

def main():
    try:
        setup_gpio()
        log("Audio recorder started. Press Ctrl+C to exit.")
        
        audio_device = get_usb_audio_device()
        if audio_device:
            get_optimal_settings(audio_device)
        else:
            log("Using default audio device. Unable to determine optimal settings.")
        
        while True:
            if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                time.sleep(0.05)  # Debounce
                if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                    if recording:
                        stop_recording()
                    else:
                        start_recording()
                time.sleep(0.2)  # Additional debounce
            time.sleep(0.1)

    except KeyboardInterrupt:
        log("KeyboardInterrupt received")
    except Exception as e:
        log(f"An error occurred: {str(e)}")

    finally:
        cleanup()

if __name__ == "__main__":
    log("Script started")
    main()