from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "ps-audio-recorder"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Stubs for non-Linux test hosts.
if "evdev" not in sys.modules:
    evdev_stub = types.ModuleType("evdev")
    evdev_stub.ecodes = SimpleNamespace(EV_KEY=1)
    evdev_stub.list_devices = lambda: []

    class _InputDevice:
        def __init__(self, _path):
            self.path = _path

    evdev_stub.InputDevice = _InputDevice
    sys.modules["evdev"] = evdev_stub

if "termios" not in sys.modules:
    termios_stub = types.ModuleType("termios")
    termios_stub.TCSADRAIN = 0
    termios_stub.tcgetattr = lambda _stream: [0]
    termios_stub.tcsetattr = lambda *_args, **_kwargs: None
    sys.modules["termios"] = termios_stub

if "tty" not in sys.modules:
    tty_stub = types.ModuleType("tty")
    tty_stub.setcbreak = lambda _fd: None
    sys.modules["tty"] = tty_stub

from devices import input as input_mod  # noqa: E402
from config import Config  # noqa: E402


class FakeInputDevice:
    def __init__(self, path, keycodes):
        self.path = path
        self._keycodes = keycodes
        self.closed = False

    def capabilities(self):
        return {input_mod.evdev.ecodes.EV_KEY: self._keycodes}

    def close(self):
        self.closed = True


class InputDeviceTests(unittest.TestCase):
    def test_find_input_devices_selects_matching_key_code(self):
        device = FakeInputDevice("/dev/input/event0", [Config.TRIGGER_KEY_CODE])
        with (
            patch("devices.input.evdev.list_devices", return_value=["/dev/input/event0"]),
            patch("devices.input.evdev.InputDevice", return_value=device),
        ):
            result = input_mod.find_input_devices()
        self.assertEqual(result, [device])
        self.assertFalse(device.closed)

    def test_find_input_devices_closes_non_matching_device(self):
        device = FakeInputDevice("/dev/input/event1", [999])
        with (
            patch("devices.input.evdev.list_devices", return_value=["/dev/input/event1"]),
            patch("devices.input.evdev.InputDevice", return_value=device),
        ):
            result = input_mod.find_input_devices()
        self.assertEqual(result, [])
        self.assertTrue(device.closed)

    def test_find_input_devices_logs_device_inspection_errors(self):
        with (
            patch("devices.input.evdev.list_devices", return_value=["/dev/input/event2"]),
            patch("devices.input.evdev.InputDevice", side_effect=RuntimeError("cannot open")),
            patch("devices.input.log") as mock_log,
        ):
            result = input_mod.find_input_devices()
        self.assertEqual(result, [])
        mock_log.assert_called()

    def test_find_input_devices_logs_enumeration_errors(self):
        with (
            patch("devices.input.evdev.list_devices", side_effect=RuntimeError("bad enumerate")),
            patch("devices.input.log") as mock_log,
        ):
            result = input_mod.find_input_devices()
        self.assertEqual(result, [])
        mock_log.assert_called()


if __name__ == "__main__":
    unittest.main()
