from dataclasses import dataclass
from typing import Optional, NamedTuple
import os

class HSV(NamedTuple):
    hue: int
    saturation: int
    value: int

class Config:
    SAMPLE_RATE = 48000
    CHANNELS = 2
    AUDIO_FORMAT = "S32_LE"
    RECORDING_DIR = "/srv/recordings"
    MAX_RECORDING_TIME = 3600
    TRIGGER_KEY_CODE = 115
    BULB_NAME = "Recording Light"
    BULB_CACHE_FILE = "/var/lib/audio-recorder/last_bulb.json"
    BULB_DISCOVERY_TIMEOUT = 8  # seconds
    RECORDING_HUE = 0
    RECORDING_SATURATION = 100
    RECORDING_BRIGHTNESS = 100
    RECORDING_COLOR = HSV(RECORDING_HUE, RECORDING_SATURATION, RECORDING_BRIGHTNESS)
    POWER_COMMAND_DELAY = 1.2
    COLOR_COMMAND_DELAY = 1.1
    BRIGHTNESS_COMMAND_DELAY = 1.0
    RECORDING_PREFIX = "audio-recorder"
    TIMESTAMP_FORMAT = "%Y-%m-%d-%H-%M-%S"
    LOG_FILE = "/var/log/audio-recorder.log"
    RECORDING_EXTENSION = "mp3"

@dataclass
class BulbState:
    is_on: bool
    brightness: Optional[int] = None
    hsv: Optional[HSV] = None
    color_temp: Optional[int] = None
