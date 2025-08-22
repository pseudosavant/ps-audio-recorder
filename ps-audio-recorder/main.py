import asyncio
from select import select
import time
import os
import sys
from contextlib import nullcontext
import evdev
from evdev import ecodes

from config import Config
from devices.input import NonBlockingInput, find_input_devices
from devices.light import find_kasa_bulb, test_bulb_connection
from utils.logging import log
from recorder import Recorder

# Skip keyboard input if running as a service
def is_running_as_service():
    return not sys.stdout.isatty()

async def detect_bt_reconnection(recorder):
    """
    Monitor bluetooth devices for reconnection events.
    When a device reconnects, only stop recording if already recording.
    """
    device_states = {}  # Path -> was_connected state
    reconnection_cooldown = 0
    first_run = True
    
    log("Starting Bluetooth reconnection monitor for stopping recordings")
    
    while True:
        try:
            current_time = time.time()
            
            # Discover input devices that might be bluetooth/wireless
            all_input_paths = set(evdev.list_devices())
            
            # First run - just populate the initial state without triggering anything
            if first_run:
                for path in all_input_paths:
                    try:
                        device = evdev.InputDevice(path)
                        name = device.name.lower()
                        
                        # Check if it's a bluetooth/wireless device by name
                        if ('bluetooth' in name or 'bt' in name or 
                            'wireless' in name or 'remote' in name or
                            'shutter' in name):
                            device_states[path] = True
                            log(f"Found bluetooth device to monitor: {device.name}")
                        
                        # Close the device
                        device.close()
                    except Exception:
                        pass
                
                first_run = False
                log(f"Initially monitoring {len(device_states)} bluetooth devices")
                await asyncio.sleep(2)
                continue
            
            # Check for devices that disappeared (quietly, no logging)
            for path in list(device_states.keys()):
                if path not in all_input_paths:
                    device_states[path] = False
            
            # Check for devices that reappeared
            for path in all_input_paths:
                # Device exists in our states but was previously disconnected
                if path in device_states and not device_states[path]:
                    device_states[path] = True
                    
                    # Only trigger to STOP recording if currently recording
                    # This avoids starting recording with a reconnection
                    if recorder.is_recording and current_time > reconnection_cooldown:
                        log("Bluetooth device reconnected - stopping recording")
                        await asyncio.sleep(0.5)  # Brief delay to allow connection to stabilize
                        await recorder.stop()  # Only stop, don't toggle
                        reconnection_cooldown = current_time + 3  # 3 second cooldown
                
                # New bluetooth device we haven't seen before (quiet monitoring)
                elif path not in device_states:
                    try:
                        device = evdev.InputDevice(path)
                        name = device.name.lower()
                        
                        # Check if it's a bluetooth/wireless device
                        if ('bluetooth' in name or 'bt' in name or 
                            'wireless' in name or 'remote' in name or
                            'shutter' in name):
                            device_states[path] = True
                        
                        # Close the device
                        device.close()
                    except Exception:
                        pass
            
        except Exception as e:
            log(f"Error in bluetooth reconnection monitor: {str(e)}")
            
        await asyncio.sleep(1)

async def main():
    # Initialize Kasa bulb with better error handling
    try:
        kasa_dev = await find_kasa_bulb()
        if kasa_dev:
            if await test_bulb_connection(kasa_dev):
                log(f"Successfully connected to {Config.BULB_NAME}")
            else:
                log("Failed to control bulb, continuing without light control")
                kasa_dev = None
        else:
            log("No Kasa bulb found, continuing without light control")
    except Exception as e:
        log(f"Error setting up Kasa bulb: {str(e)}")
        kasa_dev = None
    
    # Initialize recorder
    recorder = Recorder(kasa_dev)
    
    # Keep track of input devices
    current_devices = {}
    
    # Start bluetooth reconnection monitor as a background task
    bt_monitor_task = asyncio.create_task(detect_bt_reconnection(recorder))
    
    log("Ready to record. Waiting for wireless button input...")
    
    try:
        # Only set up keyboard input if not running as a service
        keyboard = None
        if not is_running_as_service():
            keyboard = NonBlockingInput()
            log("Keyboard input enabled. Press SPACE to start/stop recording.")

        with keyboard if keyboard else nullcontext():
            while True:
                # Check for new input devices
                try:
                    for device in find_input_devices():
                        if device.path not in current_devices:
                            log(f"New input device connected: {device.name}")
                            current_devices[device.path] = device
                except Exception as e:
                    log(f"Error finding input devices: {str(e)}")
                
                # Check for disconnected devices
                disconnected = []
                for path, device in list(current_devices.items()):
                    try:
                        _ = device.name
                    except:
                        disconnected.append(path)
                        try:
                            device.close()
                        except:
                            pass
                
                for path in disconnected:
                    log(f"Input device disconnected: {current_devices[path].name}")
                    del current_devices[path]
                
                # Handle input devices
                if current_devices:
                    try:
                        r, _, _ = select(current_devices.values(), [], [], 0)
                    except (OSError, IOError):  # This will catch disconnected devices
                        # Clear invalid devices
                        for path in list(current_devices.keys()):
                            try:
                                current_devices[path].close()
                            except:
                                pass
                            log(f"Removed invalid device at {path}")
                            del current_devices[path]
                        continue
                        
                    for ready_device in r:
                        try:
                            for event in ready_device.read():
                                if event.type == ecodes.EV_KEY and event.code == Config.TRIGGER_KEY_CODE:
                                    if event.value == 1:  # Key press
                                        log(f"Remote button pressed (code: {event.code})")
                                        await recorder.toggle()
                        except (OSError, IOError):
                            # Remove the disconnected device
                            for path, device in list(current_devices.items()):
                                if device == ready_device:
                                    try:
                                        device.close()
                                    except:
                                        pass
                                    log(f"Removed disconnected device at {path}")
                                    del current_devices[path]
                                    break
                
                # Handle keyboard input only if enabled
                if keyboard:
                    key = keyboard.check_input()
                    if key == ' ':
                        log("Spacebar pressed")
                        await recorder.toggle()
                
                await asyncio.sleep(0.1)

    except KeyboardInterrupt:
        log("KeyboardInterrupt received")
    except Exception as e:
        log(f"An error occurred: {str(e)}")
    finally:
        # Cancel the bluetooth monitor task
        bt_monitor_task.cancel()
            
        # Stop recording if active
        await recorder.stop()
        
        # Close all input devices
        for device in current_devices.values():
            try:
                device.close()
            except:
                pass
                
        log("Script terminated")

if __name__ == "__main__":
    log("Script started")
    asyncio.run(main())