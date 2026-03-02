from pathlib import Path
import importlib
import os
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "ps-audio-recorder"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import config as config_mod  # noqa: E402


ENV_KEYS = [
    "PS_AUDIO_SAMPLE_RATE",
    "PS_AUDIO_CHANNELS",
    "PS_AUDIO_AUDIO_FORMAT",
    "PS_AUDIO_RECORDING_DIR",
    "PS_AUDIO_MAX_RECORDING_TIME",
    "PS_AUDIO_TRIGGER_KEY_CODE",
    "PS_AUDIO_BULB_NAME",
    "PS_AUDIO_BULB_DISCOVERY_TIMEOUT",
    "PS_AUDIO_BULB_REDISCOVERY_INTERVAL",
    "PS_AUDIO_RECORDING_HUE",
    "PS_AUDIO_RECORDING_SATURATION",
    "PS_AUDIO_RECORDING_BRIGHTNESS",
    "PS_AUDIO_POWER_COMMAND_DELAY",
    "PS_AUDIO_COLOR_COMMAND_DELAY",
    "PS_AUDIO_BRIGHTNESS_COMMAND_DELAY",
    "PS_AUDIO_RECORDING_PREFIX",
    "PS_AUDIO_RECORDING_SUBDIR_FORMAT",
    "PS_AUDIO_TIMESTAMP_FORMAT",
    "PS_AUDIO_LOG_FILE",
    "PS_AUDIO_RECORDING_EXTENSION",
]


class ConfigEnvTests(unittest.TestCase):
    def _reload_config(self, overrides):
        original = {k: os.environ.get(k) for k in ENV_KEYS}
        try:
            for key in ENV_KEYS:
                os.environ.pop(key, None)
            os.environ.update(overrides)
            importlib.reload(config_mod)
            return config_mod.Config
        finally:
            for key in ENV_KEYS:
                os.environ.pop(key, None)
            for key, value in original.items():
                if value is not None:
                    os.environ[key] = value
            importlib.reload(config_mod)

    def test_defaults_when_env_unset(self):
        cfg = self._reload_config({})
        self.assertEqual(cfg.SAMPLE_RATE, 48000)
        self.assertEqual(cfg.TRIGGER_KEY_CODE, 115)
        self.assertEqual(cfg.RECORDING_DIR, "/srv/recordings")
        self.assertEqual(cfg.RECORDING_SUBDIR_FORMAT, "%Y/%m")
        self.assertEqual(cfg.LOG_FILE, "/var/log/audio-recorder.log")

    def test_env_overrides_apply(self):
        cfg = self._reload_config(
            {
                "PS_AUDIO_SAMPLE_RATE": "44100",
                "PS_AUDIO_TRIGGER_KEY_CODE": "57",
                "PS_AUDIO_RECORDING_DIR": "/mnt/usb/recordings",
                "PS_AUDIO_RECORDING_SUBDIR_FORMAT": "%Y/%m/%d",
                "PS_AUDIO_BULB_NAME": "Studio Light",
                "PS_AUDIO_POWER_COMMAND_DELAY": "2.5",
                "PS_AUDIO_RECORDING_HUE": "120",
                "PS_AUDIO_RECORDING_SATURATION": "80",
                "PS_AUDIO_RECORDING_BRIGHTNESS": "60",
            }
        )
        self.assertEqual(cfg.SAMPLE_RATE, 44100)
        self.assertEqual(cfg.TRIGGER_KEY_CODE, 57)
        self.assertEqual(cfg.RECORDING_DIR, "/mnt/usb/recordings")
        self.assertEqual(cfg.RECORDING_SUBDIR_FORMAT, "%Y/%m/%d")
        self.assertEqual(cfg.BULB_NAME, "Studio Light")
        self.assertEqual(cfg.POWER_COMMAND_DELAY, 2.5)
        self.assertEqual(cfg.RECORDING_COLOR.hue, 120)
        self.assertEqual(cfg.RECORDING_COLOR.saturation, 80)
        self.assertEqual(cfg.RECORDING_COLOR.value, 60)

    def test_invalid_numeric_values_fall_back_to_defaults(self):
        cfg = self._reload_config(
            {
                "PS_AUDIO_SAMPLE_RATE": "invalid",
                "PS_AUDIO_TRIGGER_KEY_CODE": "oops",
                "PS_AUDIO_POWER_COMMAND_DELAY": "bad",
            }
        )
        self.assertEqual(cfg.SAMPLE_RATE, 48000)
        self.assertEqual(cfg.TRIGGER_KEY_CODE, 115)
        self.assertEqual(cfg.POWER_COMMAND_DELAY, 1.2)


if __name__ == "__main__":
    unittest.main()
