import asyncio
from datetime import datetime as real_datetime
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import AsyncMock, mock_open, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "ps-audio-recorder"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Linux-only dependency in runtime code; provide test stub on non-Linux hosts.
if "grp" not in sys.modules:
    grp_stub = types.ModuleType("grp")
    grp_stub.getgrnam = lambda _name: SimpleNamespace(gr_gid=1000)
    sys.modules["grp"] = grp_stub

# Optional runtime dependency for recorder import in test environments.
if "kasa" not in sys.modules:
    kasa_stub = types.ModuleType("kasa")

    class _SmartBulb:
        pass

    kasa_stub.SmartBulb = _SmartBulb
    sys.modules["kasa"] = kasa_stub

import recorder  # noqa: E402
from config import Config  # noqa: E402


class FakeStdout:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, returncode=None):
        self.returncode = returncode
        self.stdout = FakeStdout()
        self.terminated = False
        self.killed = False
        self.wait_calls = []

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        if self.returncode is None:
            self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class _FixedDatetime:
    @staticmethod
    def now():
        return real_datetime(2026, 1, 15, 8, 30, 0)


class RecorderTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_stop_lifecycle_with_mocked_processes(self):
        arecord_proc = FakeProcess(returncode=None)
        lame_proc = FakeProcess(returncode=None)
        m = mock_open()
        expected_dir = os.path.join("/tmp/recordings", "2026/01")
        expected_file = os.path.join(expected_dir, "audio-recorder-2026-01-15-08-30-00.mp3")

        with (
            patch.object(Config, "RECORDING_DIR", "/tmp/recordings"),
            patch.object(Config, "RECORDING_SUBDIR_FORMAT", "%Y/%m"),
            patch("recorder.log"),
            patch("recorder.open", m, create=True),
            patch("recorder.datetime", _FixedDatetime),
            patch("recorder.get_usb_audio_device", return_value=None),
            patch("recorder.os.getuid", return_value=1000, create=True),
            patch("recorder.os.makedirs"),
            patch("recorder.grp.getgrnam", return_value=SimpleNamespace(gr_gid=1000)),
            patch("recorder.os.chown", create=True),
            patch("recorder.os.chmod"),
            patch("recorder.asyncio.sleep", new=AsyncMock()),
            patch("recorder.subprocess.Popen", side_effect=[arecord_proc, lame_proc]),
        ):
            rec = recorder.Recorder(kasa_device=None)

            started = await rec.start()
            self.assertTrue(started)
            self.assertTrue(rec.is_recording())
            self.assertTrue(arecord_proc.stdout.closed)
            recorder.os.makedirs.assert_called_once_with(expected_dir, exist_ok=True)
            m.assert_called_with(expected_file, "w")

            await rec.stop()
            self.assertFalse(rec.is_recording())
            self.assertTrue(arecord_proc.terminated)
            self.assertIsNone(rec.process)
            self.assertIsNone(rec.encoder_process)

    async def test_toggle_calls_are_serialized(self):
        events = []

        async def fake_start(self):
            await asyncio.sleep(0.01)
            self.recording = True
            events.append("start")
            return True

        async def fake_stop(self):
            await asyncio.sleep(0.01)
            self.recording = False
            events.append("stop")

        with (
            patch.object(recorder.Recorder, "_start_unlocked", new=fake_start),
            patch.object(recorder.Recorder, "_stop_unlocked", new=fake_stop),
        ):
            rec = recorder.Recorder(kasa_device=None)
            await asyncio.gather(rec.toggle(), rec.toggle())

        self.assertEqual(events, ["start", "stop"])
        self.assertFalse(rec.is_recording())

    async def test_parallel_start_calls_do_not_overlap(self):
        running = 0
        max_running = 0

        async def fake_start(self):
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            self.recording = True
            running -= 1
            return True

        with patch.object(recorder.Recorder, "_start_unlocked", new=fake_start):
            rec = recorder.Recorder(kasa_device=None)
            await asyncio.gather(rec.start(), rec.start())

        self.assertEqual(max_running, 1)


if __name__ == "__main__":
    unittest.main()
