from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import mock_open, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "ps-audio-recorder"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from utils import logging as logging_mod  # noqa: E402


class _FixedDatetime:
    @staticmethod
    def now():
        return datetime(2026, 1, 1, 12, 0, 0)


class LoggingTests(unittest.TestCase):
    def test_log_writes_to_file_and_stdout(self):
        m = mock_open()
        with (
            patch("utils.logging.datetime", _FixedDatetime),
            patch("builtins.open", m),
            patch("builtins.print") as mock_print,
            patch.object(logging_mod.Config, "LOG_FILE", "/tmp/audio-recorder.log"),
        ):
            logging_mod.log("hello")

        mock_print.assert_called_once()
        m.assert_called_once_with("/tmp/audio-recorder.log", "a", encoding="utf-8")
        handle = m()
        handle.write.assert_called_once_with("2026-01-01 12:00:00: hello\n")

    def test_log_does_not_raise_when_file_write_fails(self):
        with (
            patch("utils.logging.datetime", _FixedDatetime),
            patch("builtins.open", side_effect=OSError("disk full")),
            patch("builtins.print") as mock_print,
            patch.object(logging_mod.Config, "LOG_FILE", "/tmp/audio-recorder.log"),
        ):
            logging_mod.log("hello")

        self.assertEqual(mock_print.call_count, 2)
        warning_call = mock_print.call_args_list[1]
        self.assertIn("failed to write log file", warning_call.args[0])


if __name__ == "__main__":
    unittest.main()
