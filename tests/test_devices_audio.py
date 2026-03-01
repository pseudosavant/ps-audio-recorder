from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "ps-audio-recorder"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from devices import audio as audio_mod  # noqa: E402
from config import Config  # noqa: E402


class AudioDeviceTests(unittest.TestCase):
    def test_get_usb_audio_device_parses_card_number(self):
        stdout = "card 1: USB Audio [USB Audio], device 0: USB Audio [USB Audio]\n"
        with patch("devices.audio.subprocess.run", return_value=SimpleNamespace(stdout=stdout)):
            result = audio_mod.get_usb_audio_device()
        self.assertEqual(result, "hw:1,0")

    def test_get_usb_audio_device_returns_none_when_missing(self):
        with patch("devices.audio.subprocess.run", return_value=SimpleNamespace(stdout="card 0: Headphones\n")):
            result = audio_mod.get_usb_audio_device()
        self.assertIsNone(result)

    def test_get_usb_audio_device_logs_and_returns_none_on_error(self):
        with (
            patch("devices.audio.subprocess.run", side_effect=RuntimeError("boom")),
            patch("devices.audio.log") as mock_log,
        ):
            result = audio_mod.get_usb_audio_device()
        self.assertIsNone(result)
        mock_log.assert_called()

    def test_get_optimal_settings_prefers_highest_supported_format(self):
        stderr = "FORMAT: S16_LE S32_LE\nCHANNELS: 1 2\n"
        with patch("devices.audio.subprocess.run", return_value=SimpleNamespace(stderr=stderr)):
            fmt, channels = audio_mod.get_optimal_settings("hw:1,0")
        self.assertEqual(fmt, "S32_LE")
        self.assertEqual(channels, Config.CHANNELS)

    def test_get_optimal_settings_falls_back_channel_to_one(self):
        stderr = "FORMAT: S16_LE\nCHANNELS: 1\n"
        with patch("devices.audio.subprocess.run", return_value=SimpleNamespace(stderr=stderr)):
            fmt, channels = audio_mod.get_optimal_settings("hw:1,0")
        self.assertEqual(fmt, "S16_LE")
        self.assertEqual(channels, 1)

    def test_get_optimal_settings_logs_and_returns_defaults_on_error(self):
        with (
            patch("devices.audio.subprocess.run", side_effect=RuntimeError("bad call")),
            patch("devices.audio.log") as mock_log,
        ):
            fmt, channels = audio_mod.get_optimal_settings("hw:1,0")
        self.assertIsNone(fmt)
        self.assertEqual(channels, Config.CHANNELS)
        mock_log.assert_called()


if __name__ == "__main__":
    unittest.main()
