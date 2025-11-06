#!/usr/bin/env python3
"""
Lightweight Hubspace API implementation using only urllib3 and json.
Minimal dependencies for embedded systems.
"""

import json
import time
import urllib.parse
import base64
import hashlib
import secrets
import re
from typing import Dict, Optional, Tuple, Any

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("urllib3 not available")
    exit(1)

class HubspaceLite:
    """Lightweight Hubspace API client with minimal dependencies"""
class HubspaceClient:
    def __init__(self, username: str, password: str, account_id: str = None):
        self.username = username
        self.password = password
        self.account_id = account_id  # Account ID for API calls
        # Create session with cookie support 
        self.session = urllib3.PoolManager()
        self.cookies = {}  # Manual cookie management for urllib3
        self.token = None
        
        # OAuth endpoints (corrected for working hubspaceng implementation)
        self.oauth_base = "https://accounts.hubspaceconnect.com/auth/realms/thd"
        self.api_base = "https://api2.afero.net/v1"
        
        # Critical: Use the same user agent as working hubspaceng library
        self.user_agent = "Dart/2.15 (dart:io)"
        
        # Initialize empty containers for devices and accounts
        self.devices = {}
        self.accounts = {}
        
    def _extract_cookies(self, response_headers):
        """Extract cookies from response headers"""
        if 'set-cookie' in response_headers:
            cookie_header = response_headers['set-cookie']
            # Complex cookie parsing - handle multiple cookies in one header
            # Split by comma, but be careful about commas within cookie values
            cookie_parts = []
            current = ""
            paren_count = 0
            
            for char in cookie_header:
                if char == ',' and paren_count == 0:
                    cookie_parts.append(current.strip())
                    current = ""
                else:
                    current += char
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
            
            if current.strip():
                cookie_parts.append(current.strip())
            
            # Parse each cookie
            for cookie_part in cookie_parts:
                if '=' in cookie_part:
                    # Split on first = only
                    name_value = cookie_part.split(';')[0]  # Remove attributes first
                    if '=' in name_value:
                        name, value = name_value.split('=', 1)
                        name = name.strip()
                        value = value.strip()
                        self.cookies[name] = value
    
    def _get_cookie_header(self):
        """Format cookies for Cookie header"""
        if not self.cookies:
            return None
        return '; '.join([f"{name}={value}" for name, value in self.cookies.items()])
        
    def _generate_pkce(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        # Generate random 128-character string
        self.code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(96)).decode('utf-8').rstrip('=')
        
        # Create SHA256 challenge
        digest = hashlib.sha256(self.code_verifier.encode('utf-8')).digest()
        challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
        
        return self.code_verifier, challenge
    
    def _make_request(self, method: str, url: str, headers: Dict = None, data: Dict = None, 
                     params: Dict = None, json_data: Dict = None, allow_redirects: bool = True) -> Tuple[int, str, Dict]:
        """Make HTTP request and return status, text, headers"""
        
        if headers is None:
            headers = {}
        
        # Add critical headers from working hubspaceng implementation
        headers.setdefault('User-Agent', self.user_agent)
        headers.setdefault('accept-encoding', 'gzip')
        
        # Add cookies if we have any
        cookie_header = self._get_cookie_header()
        if cookie_header:
            headers['Cookie'] = cookie_header
        
        # Add auth header if we have token
        if hasattr(self, 'access_token') and self.access_token and 'Authorization' not in headers:
            headers['Authorization'] = self.access_token
        
        try:
            # Build URL with query parameters
            if params:
                param_str = urllib.parse.urlencode(params)
                url = f"{url}?{param_str}"
            
            if method.upper() == 'GET':
                resp = self.session.request('GET', url, headers=headers, redirect=allow_redirects)
            elif method.upper() in ['POST', 'PUT']:
                if json_data:
                    headers['Content-Type'] = 'application/json'
                    body = json.dumps(json_data)
                elif data:
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'  
                    body = urllib.parse.urlencode(data)
                else:
                    body = None
                
                resp = self.session.request(method.upper(), url, headers=headers, body=body, redirect=allow_redirects)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Extract cookies from response for session management
            response_headers = dict(resp.headers)
            self._extract_cookies(response_headers)
            
            return resp.status, resp.data.decode('utf-8'), response_headers
            
        except Exception as e:
            print(f"Request failed: {e}")
            return 0, "", {}
    
    def login(self) -> bool:
        """Authenticate with Hubspace using the exact working flow from hubspaceng"""
        print("Starting Hubspace authentication...")
        
        try:
            # Phase 1: Get session code (following hubspaceng pattern exactly)
            print("Phase 1 - OIDC Session Code...")
            code_verifier, code_challenge = self._generate_pkce()
            
            auth_url = f"{self.oauth_base}/protocol/openid-connect/auth"
            auth_params = {
                'client_id': 'hubspace_android',
                'redirect_uri': 'hubspace-app://loginredirect',
                'response_type': 'code',
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256',
                'scope': 'openid offline_access'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'accept-encoding': 'gzip'
            }
            
            status, text, _ = self._make_request('GET', auth_url, headers=headers, params=auth_params, allow_redirects=False)
            print(f"Auth page status: {status}, length: {len(text)}")
            
            if status != 200:
                print(f"Failed to get auth page: {status}")
                print(f"Response: {text[:200]}...")
                return False
            
            # Extract session parameters using the exact regex from hubspaceng
            session_code_match = re.search(r'session_code=([^&]+)', text)
            execution_match = re.search(r'execution=([^&]+)', text)
            tab_id_match = re.search(r'tab_id=([^&]+)', text)
            
            if not all([session_code_match, execution_match, tab_id_match]):
                print("Failed to extract session parameters")
                print(f"Response snippet: {text[:500]}...")
                return False
            
            session_code = session_code_match.group(1)
            execution = execution_match.group(1)
            tab_id = tab_id_match.group(1)
            
            print(f"Session parameters extracted successfully")
            
            # Phase 2: Submit credentials (following hubspaceng pattern exactly)
            print("Phase 2 - Login Action...")
            login_url = f"{self.oauth_base}/login-actions/authenticate"
            login_data = {
                'username': self.username,
                'password': self.password,
                'credentialId': ''
            }
            login_params = {
                'session_code': session_code,
                'execution': execution,
                'client_id': 'hubspace_android',
                'tab_id': tab_id
            }
            
            # Use headers exactly like hubspaceng
            login_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'accept-encoding': 'gzip'
            }
            
            status, text, resp_headers = self._make_request('POST', login_url, headers=login_headers, 
                                                     data=login_data, params=login_params, allow_redirects=False)
            print(f"Login status: {status}")
            
            if status != 302:  # Expecting redirect
                print(f"Login failed: {status}")
                print(f"Response: {text[:200]}...")
                return False
            
            # Extract code from location header
            location = resp_headers.get('location') or resp_headers.get('Location')
            if not location:
                print("No location header in login response")
                return False
            
            code_match = re.search(r'&code=([^&]+)$', location)
            if not code_match:
                print(f"No code in location: {location}")
                return False
            
            code = code_match.group(1)
            print(f"Authorization code extracted")
            
            # Phase 3: Get access token (following hubspaceng pattern exactly)
            print("Phase 3 - Get Access Token...")
            token_url = f"{self.oauth_base}/protocol/openid-connect/token"
            token_data = {
                'client_id': 'hubspace_android',
                'grant_type': 'authorization_code',
                'redirect_uri': 'hubspace-app://loginredirect',
                'code': code,
                'code_verifier': self.code_verifier
            }
            
            token_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'accept-encoding': 'gzip'
            }
            
            status, text, _ = self._make_request('POST', token_url, headers=token_headers, 
                                               data=token_data, allow_redirects=False)
            print(f"Token status: {status}")
            
            if status != 200:
                print(f"Token request failed: {status}")
                print(f"Response: {text[:200]}...")
                return False
            
            try:
                token_response = json.loads(text)
                access_token = token_response.get('access_token')
                token_type = token_response.get('token_type', 'Bearer')
                
                if access_token:
                    self.access_token = f"{token_type} {access_token}"
                    self.refresh_token = token_response.get('refresh_token')
                    expires_in = int(token_response.get('expires_in', 3600))
                    self.token_expires = time.time() + expires_in
                    
                    print(f"Authentication successful! Token expires in {expires_in}s")
                    return True
                else:
                    print("No access token in response")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"Invalid JSON in token response: {e}")
                return False
                
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def _refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            return self.login()  # Re-authenticate
        
        try:
            token_url = f"{self.oauth_base}/protocol/openid-connect/token"
            refresh_data = {
                'grant_type': 'refresh_token',
                'client_id': 'hubspace_android',
                'refresh_token': self.refresh_token
            }
            
            status, text, headers = self._make_request('POST', token_url, data=refresh_data)
            if status != 200:
                print(f"Token refresh failed: {status}")
                return self.login()  # Fallback to re-auth
            
            token_resp = json.loads(text)
            self.access_token = token_resp['access_token']
            expires_in = token_resp.get('expires_in', 3600)
            self.token_expires = time.time() + expires_in
            
            print("Token refreshed")
            return True
            
        except Exception as e:
            print(f"Token refresh error: {e}")
            return self.login()  # Fallback to re-auth
    
    def _ensure_auth(self) -> bool:
        """Ensure we have a valid access token"""
        # Check if token is expired (with 60s buffer)
        if time.time() > (self.token_expires - 60):
            return self._refresh_access_token()
        return self.access_token is not None
    
    def get_devices(self) -> bool:
        """Simplified device discovery - we use known device_id from config"""
        if not self._ensure_auth():
            return False
        
        # Since we're testing device control, let's try to actually get device info
        # But for now, let's just mark the known device as available 
        # This avoids the 404 discovery issue while testing control
        
        # We'll populate this with the known device_id when we initialize
        # For now, just return True since device_id is passed separately
        print(f"Device discovery bypassed (using known device_id)")
        return True
    
    def control_device(self, device_id: str, commands: Dict) -> bool:
        """Send control commands to device using the correct Hubspace API format"""
        if not self._ensure_auth():
            return False
        
        try:
            # Use the correct API endpoint format from hubspaceng
            control_url = f"{self.api_base}/accounts/{self.account_id}/metadevices/{device_id}/state"
            
            # Convert our commands to the Hubspace API format
            values = []
            for function_class, value in commands.items():
                values.append({
                    "functionClass": function_class,
                    "lastUpdateTime": int(time.time() * 1000),  # Current time in milliseconds
                    "value": value
                })
            
            payload = {
                "metadeviceId": device_id,
                "values": values
            }
            
            # Critical: Use the exact headers from working hubspaceng library
            headers = {
                "user-agent": self.user_agent,
                "host": "semantics2.afero.net",  # This is the key!
                "accept-encoding": "gzip",
                "content-type": "application/json; charset=utf-8",
            }
            
            status, response, _ = self._make_request('PUT', control_url, 
                                                   headers=headers,
                                                   json_data=payload)
            
            if status == 200:
                print(f"Device control successful")
                return True
            else:
                print(f"Device control failed: {status}")
                print(f"Response: {response[:200]}...")
                return False
                
        except Exception as e:
            print(f"Failed to control device: {e}")
            return False
    
    def control_light(self, device_id: str, power: bool = None, brightness: int = None) -> bool:
        """Convenience method to control light power and brightness"""
        commands = {}
        
        if power is not None:
            commands['power'] = 'on' if power else 'off'  # Use function class name and state names
        
        if brightness is not None:
            commands['brightness'] = brightness  # Use function class name
        
        if not commands:
            print("No commands specified")
            return False
            
        return self.control_device(device_id, commands)
    
    def turn_on(self, device_id: str, brightness: int = None, color: Dict = None) -> bool:
        """Turn device on with optional brightness and color"""
        commands = {"power": "on"}
        
        if brightness is not None:
            commands["brightness"] = max(1, min(100, brightness))
        
        if color is not None:
            # Color format: {"hue": 0-360, "saturation": 0-100, "brightness": 0-100}
            commands.update(color)
        
        return self.control_device(device_id, commands)
    
    def turn_off(self, device_id: str) -> bool:
        """Turn device off"""
        return self.control_device(device_id, {"power": "off"})
    
    def set_brightness(self, device_id: str, brightness: int) -> bool:
        """Set device brightness (1-100)"""
        brightness = max(1, min(100, brightness))
        return self.control_device(device_id, {"brightness": brightness})
    
    def set_color(self, device_id: str, hue: int, saturation: int = 100, brightness: int = None) -> bool:
        """Set device color using HSB values"""
        commands = {
            "hue": max(0, min(360, hue)),
            "saturation": max(0, min(100, saturation))
        }
        
        if brightness is not None:
            commands["brightness"] = max(1, min(100, brightness))
        
        return self.control_device(device_id, commands)
    
    def get_device_status(self, device_id: str) -> Optional[Dict]:
        """Get current device status"""
        if not self._ensure_auth():
            return None
        
        try:
            headers = {
                "user-agent": self.user_agent,
                "Accept": "application/json",
                "accept-encoding": "gzip",
                "host": "semantics2.afero.net"
            }
            
            status, text, response_headers = self._make_request('GET', f"{self.api_base}/accounts/{self.account_id}/metadevices/{device_id}/state", headers=headers)
            if status == 200:
                return json.loads(text)
            else:
                print(f"Failed to get device status: {status}")
                return None
                
        except Exception as e:
            print(f"Error getting device status: {e}")
            return None

# Example usage
if __name__ == "__main__":
    # Test the lightweight implementation
    print("Testing Hubspace Lite API")
    
    # Load credentials
    try:
        with open("creds.json", "r") as f:
            creds = json.load(f)
        
        client = HubspaceLite(creds["username"], creds["password"])
        
        # Test login
        if client.login():
            print("Login successful")
            
            # Get devices
            if client.get_devices():
                print(f"Devices found: {list(client.devices.keys())}")
                
                # Test with first device
                if client.devices:
                    device_id = list(client.devices.keys())[0]
                    device_name = client.devices[device_id].get('friendlyName', 'Unknown')
                    print(f"Testing with device: {device_name} ({device_id})")
                    
                    # Test controls
                    client.turn_on(device_id, brightness=50)
                    time.sleep(2)
                    client.set_color(device_id, hue=120, saturation=100)  # Green
                    time.sleep(2)
                    client.turn_off(device_id)
            else:
                print("Failed to get devices")
        else:
            print("Login failed")
            
    except FileNotFoundError:
        print("creds.json not found")
    except Exception as e:
        print(f"Test error: {e}")