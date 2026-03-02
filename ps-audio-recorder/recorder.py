import os
import grp
import subprocess
from datetime import datetime
import asyncio

from utils.logging import log
from config import Config
from devices.audio import get_usb_audio_device, get_optimal_settings
from kasa import SmartBulb

class Recorder:
    def __init__(self, kasa_device: SmartBulb = None):
        self.recording = False
        self.process = None
        self.kasa_device = kasa_device
        self.original_bulb_state = None
        self.encoder_process = None  # lame process
        self._state_lock = asyncio.Lock()

    async def _wait_process(self, process, timeout=None):
        if process is None:
            return True
        try:
            if timeout is None:
                await asyncio.to_thread(process.wait)
            else:
                await asyncio.to_thread(process.wait, timeout)
            return True
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            log(f"Warning: Error waiting on process: {str(e)}")
            return False

    async def _terminate_process(self, process, name, timeout=5):
        if process is None:
            return
        try:
            process.terminate()
        except Exception as e:
            log(f"Warning: Error terminating {name}: {str(e)}")
            return

        if await self._wait_process(process, timeout):
            return

        try:
            process.kill()
            await self._wait_process(process, 2)
            log(f"Warning: {name} needed SIGKILL after terminate timeout")
        except Exception as e:
            log(f"Warning: Error killing {name}: {str(e)}")
    
    async def _start_unlocked(self):
        if self.recording:
            return False
            
        try:
            self.recording = True
            
            # Set umask for correct file permissions
            old_umask = os.umask(0o002)
            try:
                now = datetime.now()
                subdir = now.strftime(Config.RECORDING_SUBDIR_FORMAT).strip().strip("/\\")
                target_dir = Config.RECORDING_DIR if not subdir else os.path.join(Config.RECORDING_DIR, subdir)
                os.makedirs(target_dir, exist_ok=True)
                filename = os.path.join(
                    target_dir,
                    f"{Config.RECORDING_PREFIX}-{now.strftime(Config.TIMESTAMP_FORMAT)}.{Config.RECORDING_EXTENSION}"
                )
                
                # Pre-create the file with correct permissions
                with open(filename, 'w') as f:
                    pass
                os.chown(filename, os.getuid(), grp.getgrnam('audiofiles').gr_gid)
                os.chmod(filename, 0o664)
                
                log(f"Setting up recording: {filename}")

                # Build arecord base command (output to stdout for piping)
                arecord_command = ["arecord", "-r", str(Config.SAMPLE_RATE), "-t", "wav"]
                
                audio_device = get_usb_audio_device()
                if audio_device:
                    log(f"Using USB audio device: {audio_device}")
                    arecord_command.extend(["-D", audio_device])
                    audio_format, channels = get_optimal_settings(audio_device)
                else:
                    log("Using default audio device")
                    audio_format, channels = Config.AUDIO_FORMAT, Config.CHANNELS
                
                if audio_format:
                    arecord_command.extend(["-f", audio_format])
                arecord_command.extend(["-c", str(channels)])
                # (No output filename so data goes to stdout)

                lame_command = [
                    "lame",
                    "--ignorelength",
                    "--preset", "extreme",
                    "--silent",
                    "-",  # stdin
                    filename
                ]

                log(f"Starting recording pipeline: {' '.join(arecord_command)} | {' '.join(lame_command)}")
                self.process = subprocess.Popen(arecord_command, stdout=subprocess.PIPE, stderr=None)
                self.encoder_process = subprocess.Popen(lame_command, stdin=self.process.stdout, stderr=None)
                # Detach stdout so arecord doesn't get SIGPIPE when we terminate lame
                self.process.stdout.close()

                await asyncio.sleep(1)

                if self.process.poll() is not None or self.encoder_process.poll() is not None:
                    arecord_rc = self.process.poll() if self.process else None
                    lame_rc = self.encoder_process.poll() if self.encoder_process else None
                    log(f"Recording failed to start. arecord rc: {arecord_rc} lame rc: {lame_rc}")
                    self.recording = False
                    # Cleanup
                    if self.process and self.process.poll() is None:
                        await self._terminate_process(self.process, "arecord", timeout=2)
                    if self.encoder_process and self.encoder_process.poll() is None:
                        await self._terminate_process(self.encoder_process, "lame", timeout=2)
                    self.process = None
                    self.encoder_process = None
                    return False
                else:
                    log("Recording (MP3) started successfully")
                    # Only control light after recording starts successfully
                    if self.kasa_device is not None:
                        try:
                            from devices.light import set_recording_state
                            self.original_bulb_state = await set_recording_state(self.kasa_device, start=True)
                        except Exception as e:
                            log(f"Warning: Could not control Kasa bulb: {str(e)}")
                    return True
                    
            finally:
                os.umask(old_umask)
                
        except Exception as e:
            log(f"Error in start_recording: {str(e)}")
            self.recording = False
            if self.process:
                await self._terminate_process(self.process, "arecord", timeout=5)
            if self.encoder_process:
                await self._terminate_process(self.encoder_process, "lame", timeout=5)
            self.process = None
            self.encoder_process = None
            return False

    async def start(self):
        async with self._state_lock:
            return await self._start_unlocked()
    
    async def _stop_unlocked(self):
        if not self.recording:
            return
        
        # Turn off light before stopping recording
        if self.kasa_device is not None and self.original_bulb_state is not None:
            try:
                from devices.light import set_recording_state
                await set_recording_state(self.kasa_device, start=False, original_state=self.original_bulb_state)
            except Exception as e:
                log(f"Warning: Could not reset Kasa bulb: {str(e)}")
            
        self.recording = False
        if self.process:
            try:
                await self._terminate_process(self.process, "arecord", timeout=5)
            except Exception as e:
                log(f"Warning: Error stopping arecord: {str(e)}")
        if self.encoder_process:
            try:
                # After arecord ends, lame should finish encoding
                if not await self._wait_process(self.encoder_process, 10):
                    await self._terminate_process(self.encoder_process, "lame", timeout=2)
            except Exception as e:
                log(f"Warning: Error stopping lame: {str(e)}")
        log("Recording stopped")
        self.process = None
        self.encoder_process = None

    async def stop(self):
        async with self._state_lock:
            await self._stop_unlocked()
    
    async def toggle(self):
        async with self._state_lock:
            if self.recording:
                await self._stop_unlocked()
            else:
                await self._start_unlocked()

    def is_recording(self):
        return self.recording
