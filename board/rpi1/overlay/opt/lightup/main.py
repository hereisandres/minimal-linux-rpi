#!/usr/bin/env python3
"""
Raspberry Pi GPIO Hubspace Light Controller

A modular script to control Hubspace lights using GPIO button presses.
Minimal dependencies - only RPi.GPIO and urllib3.
"""

import time
import json
from typing import Optional, Dict, Any

# Only import RPi.GPIO if running on Raspberry Pi
try:
    import RPi.GPIO as GPIO
    RPI_AVAILABLE = True
except ImportError:
    print("WARNING: RPi.GPIO not available - running in simulation mode")
    RPI_AVAILABLE = False
    import sys
    import select

# Lightweight Hubspace API
from hubspace_lite import HubspaceClient

class HubspaceController:
    """Modular Hubspace light controller"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.device_id = None
        
        # Connection objects
        self.api = None
        self.connected = False
        
    def initialize(self) -> bool:
        """Initialize connection to Hubspace API"""
        try:
            print("Initializing Hubspace connection...")
            
            # Load configuration
            with open(self.config_file, "r") as f:
                config = json.load(f)
            
            # Extract configuration
            self.account_id = config["account_id"]
            self.device_id = config["device_id"]
            username = config["username"]
            password = config["password"]
            
            # Create API client
            print("Authenticating with Hubspace...")
            self.api = HubspaceClient(username, password, self.account_id)
            
            # Login
            if not self.api.login():
                print("Failed to authenticate")
                return False
            
            # Skip device discovery for now - we know our device_id
            # TODO: Implement proper device discovery once control API works
            print(f"Using configured device: {self.device_id}")
            
            # We can skip the device existence check for now since we know it from config
            device_name = "Configured Device"  # Will get real name once API works
            print(f"Connected to device: {device_name}")
            
            # Skip initial status check for now - will test this in the control methods
            print("   Status: Ready for testing")
            
            self.connected = True
            return True
            
        except Exception as e:
            print(f"Failed to initialize Hubspace: {e}")
            self.connected = False
            return False
    
    def control_light(self, action: str, brightness: Optional[int] = None, 
                     color: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Control the Hubspace light
        
        Args:
            action: "on", "off", "toggle", "brightness", "color"
            brightness: Optional brightness 1-100
            color: Optional color dict {"hue": 0-360, "saturation": 0-100}
            
        Returns:
            Dict with success, power, brightness, and message
        """
        if not self.connected or not self.api:
            return {
                "success": False,
                "power": False,
                "brightness": 0,
                "message": "Not connected to Hubspace"
            }
        
        try:
            print(f"Light control: {action}" + 
                 (f" at {brightness}%" if brightness else "") +
                 (f" color {color}" if color else ""))
            
            # Use the HubspaceClient.control_light method directly
            success = False
            
            if action == "on":
                success = self.api.control_light(self.device_id, power=True, brightness=brightness)
                
            elif action == "off":
                success = self.api.control_light(self.device_id, power=False)
                
            elif action == "toggle":
                # For toggle, check current state and switch accordingly
                current_status = self.api.get_device_status(self.device_id)
                if current_status and 'values' in current_status:
                    # Parse the values array to find current power state
                    current_power_value = 'off'
                    for item in current_status['values']:
                        if item.get('functionClass') == 'power':
                            current_power_value = item.get('value', 'off')
                            break
                    
                    current_power = current_power_value == 'on'
                    # Toggle: if currently on, turn off; if off, turn on
                    if current_power:
                        success = self.api.control_light(self.device_id, power=False)
                    else:
                        success = self.api.control_light(self.device_id, power=True, brightness=brightness or 100)
                else:
                    # If we can't get status, default to turning on
                    print("Warning: Could not get current status, defaulting to turn on")
                    success = self.api.control_light(self.device_id, power=True, brightness=brightness or 100)
                
            elif action == "brightness" and brightness is not None:
                success = self.api.control_light(self.device_id, power=True, brightness=brightness)
                
            elif action == "color" and color is not None:
                # Color control not implemented yet
                success = False
                
            else:
                return {
                    "success": False,
                    "power": False,
                    "brightness": 0,
                    "message": f"Invalid action: {action}"
                }
            
            if success:
                message = f"Light {action.upper()}"
                if brightness:
                    message += f" at {brightness}%"
                print(f"SUCCESS: {message}")
                
                return {
                    "success": True,
                    "power": action in ["on", "toggle", "brightness"],
                    "brightness": brightness or (100 if action in ["on", "toggle"] else 0),
                    "message": message
                }
            else:
                return {
                    "success": False,
                    "power": False,
                    "brightness": 0,
                    "message": f"Command failed: {action}"
                }
            
        except Exception as e:
            print(f"ERROR: Light control failed: {e}")
            return {
                "success": False,
                "power": False,
                "brightness": 0,
                "message": f"Error: {str(e)}"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current light status"""
        if not self.connected or not self.api:
            return {
                "success": False,
                "power": False,
                "brightness": 0,
                "message": "Not connected"
            }
        
        try:
            status = self.api.get_device_status(self.device_id)
            if status and 'values' in status:
                # Parse the values array to find power and brightness
                power_value = 'off'
                brightness_value = 0
                
                for item in status['values']:
                    if item.get('functionClass') == 'power':
                        power_value = item.get('value', 'off')
                    elif item.get('functionClass') == 'brightness':
                        brightness_value = item.get('value', 0)
                
                power = power_value == 'on'
                brightness = int(brightness_value)
                
                return {
                    "success": True,
                    "power": power,
                    "brightness": brightness,
                    "message": f"Light {'ON' if power else 'OFF'} at {brightness}%"
                }
            else:
                return {
                    "success": False,
                    "power": False,
                    "brightness": 0,
                    "message": "Failed to get status"
                }
        except Exception as e:
            return {
                "success": False,
                "power": False,
                "brightness": 0,
                "message": str(e)
            }

class GPIOButtonController:
    """GPIO button handler for Raspberry Pi"""
    
    def __init__(self):
        self.button_pins = {}
        self.last_press_time = {}
        self.debounce_delay = 0.2  # 200ms debounce
        
        # Simulation mode variables
        if not RPI_AVAILABLE:
            self.sim_last_input_time = 0
            self.sim_debounce_delay = 0.5  # Longer debounce for keyboard
        
    def setup_button(self, pin: int, button_name: str):
        """Setup a GPIO button with pull-up resistor"""
        if not RPI_AVAILABLE:
            print(f"Simulated button setup: Pin {pin} = {button_name}")
            return
            
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.button_pins[pin] = button_name
            self.last_press_time[pin] = 0
            print(f"Button setup: Pin {pin} = {button_name}")
        except Exception as e:
            print(f"Failed to setup button {pin}: {e}")
    
    def is_button_pressed(self, pin: int) -> bool:
        """Check if button is pressed with debouncing"""
        if not RPI_AVAILABLE:
            # Simulation mode - check for keyboard input
            current_time = time.time()
            
            # Check if enough time has passed since last input
            if (current_time - self.sim_last_input_time) < self.sim_debounce_delay:
                return False
            
            # Check for keyboard input without blocking
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                try:
                    key = sys.stdin.read(1).strip().lower()
                    
                    # Map keys to pins
                    key_to_pin = {
                        '1': 18,  # BUTTON_TOGGLE
                        '2': 19,  # BUTTON_DIM  
                        '3': 20   # BUTTON_STATUS
                    }
                    
                    if key in key_to_pin and key_to_pin[key] == pin:
                        self.sim_last_input_time = current_time
                        return True
                        
                except:
                    pass  # Ignore input errors
                    
            return False
            
        # Real GPIO mode
        current_time = time.time()
        
        # Check if enough time has passed since last press
        if (current_time - self.last_press_time[pin]) < self.debounce_delay:
            return False
        
        # Check if button is pressed (LOW because of pull-up)
        if GPIO.input(pin) == GPIO.LOW:
            self.last_press_time[pin] = current_time
            return True
        
        return False
    
    def cleanup(self):
        """Clean up GPIO"""
        if RPI_AVAILABLE:
            GPIO.cleanup()
            print("GPIO cleanup complete")

# Configuration removed - now loaded from config.json

# GPIO pin assignments
BUTTON_TOGGLE = 18    # GPIO 18 - Toggle light on/off
BUTTON_DIM = 19       # GPIO 19 - Toggle between 50% and 100% brightness
BUTTON_STATUS = 20    # GPIO 20 - Print current status

def main():
    """Main application loop"""
    print("Raspberry Pi Hubspace Light Controller")
    print("=========================================")
    
    # Initialize Hubspace controller
    hubspace = HubspaceController()
    
    # Initialize connection
    if not hubspace.initialize():
        print("Failed to connect to Hubspace. Check credentials and network.")
        return
    
    # Setup GPIO buttons
    gpio = GPIOButtonController()
    gpio.setup_button(BUTTON_TOGGLE, "Toggle Power")
    gpio.setup_button(BUTTON_DIM, "Toggle Brightness")
    gpio.setup_button(BUTTON_STATUS, "Get Status")
    
    print("\nButton Controls:")
    print(f"   Pin {BUTTON_TOGGLE}: Toggle light on/off")
    print(f"   Pin {BUTTON_DIM}: Toggle brightness (50%/100%)")
    print(f"   Pin {BUTTON_STATUS}: Show current status")
    
    if not RPI_AVAILABLE:
        print("\nSimulation Mode:")
        print("   Press '1' = Toggle light on/off")
        print("   Press '2' = Toggle brightness (50%/100%)")
        print("   Press '3' = Show current status")
        print("   Press 'q' then Enter = Quit")
    
    print("\nReady! Press buttons or Ctrl+C to exit")
    
    brightness_mode = 100  # Start with 100% brightness
    
    try:
        while True:
            # Check toggle button
            if gpio.is_button_pressed(BUTTON_TOGGLE):
                print("\nToggle button pressed")
                result = hubspace.control_light("toggle")
                print(f"   Result: {result['message']}")
            
            # Check brightness button
            if gpio.is_button_pressed(BUTTON_DIM):
                print("\nBrightness button pressed")
                # Toggle between 50% and 100%
                brightness_mode = 50 if brightness_mode == 100 else 100
                result = hubspace.control_light("on", brightness_mode)
                print(f"   Result: {result['message']}")
            
            # Check status button
            if gpio.is_button_pressed(BUTTON_STATUS):
                print("\nStatus button pressed")
                result = hubspace.get_status()
                print(f"   Status: {result['message']}")
            
            # Small delay to prevent excessive CPU usage
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        gpio.cleanup()

if __name__ == "__main__":
    # Example of how to use the modular functions
    print("Example usage:")
    print("=============")
    
    # You can use the HubspaceController independently:
    def example_usage():
        hubspace = HubspaceController()
        
        if hubspace.initialize():
            # Turn light on
            result = hubspace.control_light("on", 75)
            print(f"Turn on: {result}")
            
            # Get status
            status = hubspace.get_status()
            print(f"Status: {status}")
            
            # Turn off
            result = hubspace.control_light("off")
            print(f"Turn off: {result}")
    
    # Run the main application
    main()