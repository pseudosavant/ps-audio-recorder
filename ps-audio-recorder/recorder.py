import os
import time
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
    
    async def start(self):
        if self.recording:
            return False
            
        try:
            self.recording = True
            
            # Set umask for correct file permissions
            old_umask = os.umask(0o002)
            try:
                filename = os.path.join(
                    Config.RECORDING_DIR,
                    f"{Config.RECORDING_PREFIX}-{datetime.now().strftime(Config.TIMESTAMP_FORMAT)}.{Config.RECORDING_EXTENSION}"
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
                self.process = subprocess.Popen(arecord_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.encoder_process = subprocess.Popen(lame_command, stdin=self.process.stdout, stderr=subprocess.PIPE)
                # Detach stdout so arecord doesn't get SIGPIPE when we terminate lame
                self.process.stdout.close()

                time.sleep(1)

                if self.process.poll() is not None or self.encoder_process.poll() is not None:
                    # Gather stderr for diagnostics
                    arecord_err = ""
                    lame_err = ""
                    if self.process:
                        try:
                            _, aerr = self.process.communicate(timeout=0.2)
                            arecord_err = aerr.decode(errors="ignore").strip()
                        except Exception:
                            pass
                    if self.encoder_process:
                        try:
                            _, lerr = self.encoder_process.communicate(timeout=0.2)
                            lame_err = lerr.decode(errors="ignore").strip()
                        except Exception:
                            pass
                    log(f"Recording failed to start. arecord err: {arecord_err} lame err: {lame_err}")
                    self.recording = False
                    # Cleanup
                    if self.process and self.process.poll() is None:
                        try: self.process.terminate()
                        except: pass
                    if self.encoder_process and self.encoder_process.poll() is None:
                        try: self.encoder_process.terminate()
                        except: pass
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
                try:
                    self.process.terminate()
                    self.process.wait()
                except Exception as e2:
                    log(f"Warning: Error terminating arecord: {str(e2)}")
            if self.encoder_process:
                try:
                    self.encoder_process.terminate()
                    self.encoder_process.wait()
                except Exception as e3:
                    log(f"Warning: Error terminating lame: {str(e3)}")
            self.process = None
            self.encoder_process = None
            return False
    
    async def stop(self):
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
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception as e:
                log(f"Warning: Error stopping arecord: {str(e)}")
        if self.encoder_process:
            try:
                # After arecord ends, lame should finish encoding
                self.encoder_process.wait(timeout=10)
            except Exception as e:
                try:
                    self.encoder_process.terminate()
                except:
                    pass
                log(f"Warning: Error stopping lame: {str(e)}")
        log("Recording stopped")
        self.process = None
        self.encoder_process = None
    
    async def toggle(self):
        if self.recording:
            await self.stop()
        else:
            await self.start()

    def is_recording(self):
        return self.recording