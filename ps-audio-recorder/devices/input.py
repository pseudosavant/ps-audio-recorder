import evdev
from evdev import InputDevice
import sys
import termios
import tty
from select import select
from config import Config
from utils.logging import log

class NonBlockingInput:
    def __init__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
    
    def __enter__(self):
        tty.setcbreak(sys.stdin.fileno())
        return self
    
    def __exit__(self, type, value, traceback):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
    
    def check_input(self):
        if select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            return key
        return None

def find_input_devices():
    devices = []
    try:
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
                capabilities = device.capabilities()
                if evdev.ecodes.EV_KEY in capabilities:
                    key_codes = capabilities[evdev.ecodes.EV_KEY]
                    if Config.TRIGGER_KEY_CODE in key_codes:
                        devices.append(device)
            except:
                continue
    except:
        pass
    return devices
