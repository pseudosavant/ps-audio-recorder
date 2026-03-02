from dataclasses import dataclass
from typing import Optional, NamedTuple
import os


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


class HSV(NamedTuple):
    hue: int
    saturation: int
    value: int


class Config:
    SAMPLE_RATE = _env_int("PS_AUDIO_SAMPLE_RATE", 48000)
    CHANNELS = _env_int("PS_AUDIO_CHANNELS", 2)
    AUDIO_FORMAT = _env_str("PS_AUDIO_AUDIO_FORMAT", "S32_LE")
    RECORDING_DIR = _env_str("PS_AUDIO_RECORDING_DIR", "/srv/recordings")
    MAX_RECORDING_TIME = _env_int("PS_AUDIO_MAX_RECORDING_TIME", 3600)
    TRIGGER_KEY_CODE = _env_int("PS_AUDIO_TRIGGER_KEY_CODE", 115)
    BULB_NAME = _env_str("PS_AUDIO_BULB_NAME", "Recording Light")
    BULB_CACHE_FILE = _env_str("PS_AUDIO_BULB_CACHE_FILE", "/var/lib/audio-recorder/last_bulb.json")
    BULB_DISCOVERY_TIMEOUT = _env_int("PS_AUDIO_BULB_DISCOVERY_TIMEOUT", 8)  # seconds
    # If the bulb wasn't available at service startup (e.g. powered on later
    # or received a new IP), we periodically retry discovery while idle.
    BULB_REDISCOVERY_INTERVAL = _env_int("PS_AUDIO_BULB_REDISCOVERY_INTERVAL", 300)
    RECORDING_HUE = _env_int("PS_AUDIO_RECORDING_HUE", 0)
    RECORDING_SATURATION = _env_int("PS_AUDIO_RECORDING_SATURATION", 100)
    RECORDING_BRIGHTNESS = _env_int("PS_AUDIO_RECORDING_BRIGHTNESS", 100)
    RECORDING_COLOR = HSV(RECORDING_HUE, RECORDING_SATURATION, RECORDING_BRIGHTNESS)
    POWER_COMMAND_DELAY = _env_float("PS_AUDIO_POWER_COMMAND_DELAY", 1.2)
    COLOR_COMMAND_DELAY = _env_float("PS_AUDIO_COLOR_COMMAND_DELAY", 1.1)
    BRIGHTNESS_COMMAND_DELAY = _env_float("PS_AUDIO_BRIGHTNESS_COMMAND_DELAY", 1.0)
    RECORDING_PREFIX = _env_str("PS_AUDIO_RECORDING_PREFIX", "audio-recorder")
    RECORDING_SUBDIR_FORMAT = _env_str("PS_AUDIO_RECORDING_SUBDIR_FORMAT", "%Y/%m")
    TIMESTAMP_FORMAT = _env_str("PS_AUDIO_TIMESTAMP_FORMAT", "%Y-%m-%d-%H-%M-%S")
    LOG_FILE = _env_str("PS_AUDIO_LOG_FILE", "/var/log/audio-recorder.log")
    RECORDING_EXTENSION = _env_str("PS_AUDIO_RECORDING_EXTENSION", "mp3")


@dataclass
class BulbState:
    is_on: bool
    brightness: Optional[int] = None
    hsv: Optional[HSV] = None
    color_temp: Optional[int] = None
