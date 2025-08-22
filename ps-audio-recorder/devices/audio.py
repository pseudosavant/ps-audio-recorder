import subprocess
import re
from utils.logging import log
from config import Config

def get_usb_audio_device():
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'USB Audio' in line:
                card_num = line.split(':')[0].split(' ')[1]
                return f"hw:{card_num},0"
        return None
    except Exception as e:
        log(f"Error detecting USB audio device: {str(e)}")
        return None

def get_optimal_settings(device):
    try:
        result = subprocess.run(['arecord', '--dump-hw-params', '-D', device], capture_output=True, text=True)
        hw_params = result.stderr
        
        formats = re.findall(r'FORMAT: (.+)', hw_params)
        optimal_format = None
        if formats:
            available_formats = formats[0].split()
            for fmt in ['S24_3LE', 'S24_LE', 'S32_LE', 'S16_LE']:
                if fmt in available_formats:
                    optimal_format = fmt
                    break
        
        channels = re.findall(r'CHANNELS: (.+)', hw_params)
        optimal_channels = Config.CHANNELS
        if channels and str(optimal_channels) not in channels[0].split():
            optimal_channels = 2 if '2' in channels[0].split() else 1
        
        return optimal_format, optimal_channels
    except Exception as e:
        log(f"Error getting device settings: {str(e)}")
        return None, Config.CHANNELS
