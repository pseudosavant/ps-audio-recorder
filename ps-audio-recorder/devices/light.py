import os
import json
import asyncio
from kasa import SmartBulb, Discover, LightState
from utils.logging import log
from config import Config, BulbState, HSV

def save_bulb_info(ip_address):
    try:
        os.makedirs(os.path.dirname(Config.BULB_CACHE_FILE), exist_ok=True)
        with open(Config.BULB_CACHE_FILE, 'w') as f:
            json.dump({'ip': ip_address}, f)
        log(f"Saved bulb IP: {ip_address}")
    except Exception as e:
        log(f"Error saving bulb cache: {str(e)}")

def load_last_bulb_ip():
    try:
        if os.path.exists(Config.BULB_CACHE_FILE):
            with open(Config.BULB_CACHE_FILE, 'r') as f:
                ip = json.load(f).get('ip')
                log(f"Loaded cached bulb IP: {ip}")
                return ip
    except Exception as e:
        log(f"Error loading bulb cache: {str(e)}")
    return None

def clear_cached_bulb_ip():
    try:
        if os.path.exists(Config.BULB_CACHE_FILE):
            os.remove(Config.BULB_CACHE_FILE)
            log("Cleared stale bulb IP cache")
    except Exception as e:
        log(f"Error clearing bulb cache: {e}")

async def get_bulb_state(bulb: SmartBulb) -> BulbState:
    """Capture current state of the bulb"""
    try:
        await bulb.update()
        
        # Get basic state info
        is_on = bulb.is_on
        brightness = bulb.brightness
        
        # Get HSV if supported
        hsv = None
        if bulb.is_color:
            try:
                hsv = HSV(*bulb.hsv)
            except:
                log("Could not get HSV values")
        
        state = BulbState(
            is_on=is_on,
            brightness=brightness,
            hsv=hsv
        )
        log(f"Captured bulb state: on={is_on}, brightness={brightness}, hsv={hsv}")
        return state
    except Exception as e:
        log(f"Error getting bulb state: {str(e)}")
        return BulbState(is_on=False, brightness=100, hsv=None)

async def set_recording_state(bulb: SmartBulb, start=True, original_state=None):
    """On start: turn on + set HSV; On stop: turn off.
    Returns a placeholder BulbState on start so caller logic that checks for a
    truthy 'original_state' will still invoke this on stop."""
    try:
        if start:
            log("Setting recording light ON (no state capture).")
            if not bulb.is_on:
                await bulb.turn_on()
                await asyncio.sleep(Config.POWER_COMMAND_DELAY)
            await bulb.set_hsv(
                Config.RECORDING_HUE,
                Config.RECORDING_SATURATION,
                Config.RECORDING_BRIGHTNESS
            )
            log(f"Recording light set: hue={Config.RECORDING_HUE}, sat={Config.RECORDING_SATURATION}, val={Config.RECORDING_BRIGHTNESS}")
            # Return placeholder so stopping logic in caller still triggers
            return BulbState(is_on=True, brightness=Config.RECORDING_BRIGHTNESS,
                             hsv=HSV(Config.RECORDING_HUE, Config.RECORDING_SATURATION, Config.RECORDING_BRIGHTNESS))
        else:
            log("Turning recording light OFF.")
            try:
                await bulb.update()
            except Exception:
                pass
            try:
                await bulb.turn_off()
                await asyncio.sleep(0.1)
                log("Recording light turned off.")
            except Exception as off_err:
                log(f"Failed turning off recording light: {off_err}")
            return None
    except Exception as e:
        log(f"Error controlling light: {str(e)}")
    return None

async def find_kasa_bulb():
    """Find the dedicated recording bulb by alias with robust error handling."""
    last_ip = load_last_bulb_ip()
    if last_ip:
        try:
            log(f"Attempting to connect to cached bulb IP: {last_ip}")
            bulb = SmartBulb(last_ip)
            await bulb.update()
            if bulb.alias and bulb.alias.lower() == Config.BULB_NAME.lower():
                log(f"Successfully connected to cached bulb: {bulb.alias}")
                return bulb
            else:
                log(f"Cached IP alias mismatch (got '{bulb.alias}'), will rediscover.")
                clear_cached_bulb_ip()
        except Exception as e:
            log(f"Failed to connect to cached IP: {e}")
            clear_cached_bulb_ip()

    # Discovery phase
    try:
        timeout = getattr(Config, "BULB_DISCOVERY_TIMEOUT", 8)
        log(f"Starting bulb discovery (timeout={timeout}s)...")
        devices = await Discover.discover(timeout=timeout)
        # Iterate devices safely
        for addr, dev in devices.items():
            try:
                await dev.update()
                log(f"Found device: {dev.alias} at {addr}")
                if dev.alias and dev.alias.lower() == Config.BULB_NAME.lower():
                    save_bulb_info(addr)
                    bulb = SmartBulb(addr)
                    await bulb.update()
                    log(f"Found and cached matching bulb: {bulb.alias}")
                    return bulb
            except Exception as dev_err:
                log(f"Skipping device at {addr} due to error: {dev_err}")
    except Exception as e:
        log(f"Error during bulb discovery: {e}")

    log(f"Did not find bulb with alias '{Config.BULB_NAME}'")
    return None

async def test_bulb_connection(bulb):
    """Test if we can control the bulb"""
    try:
        if not bulb:
            return False
            
        await bulb.update()
        # Just test basic properties
        _ = bulb.is_on
        _ = bulb.brightness
        
        # Log capabilities
        log(f"Bulb capabilities: dimmable={bulb.is_dimmable}, color={bulb.is_color}")
        
        log("Bulb connection test successful")
        return True
    except Exception as e:
        log(f"Bulb connection test failed: {str(e)}")
        return False