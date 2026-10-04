import json
from pathlib import Path
import subprocess
import sys
import requests

from config.settings import WIFI_CONFIG_FILE
from utils.security import encrypt_password, decrypt_password

class WifiConfig:
    """
    Singleton object managing Wi-Fi connection details for the app.
    Interacts with NetworkManager (`nmcli`) on Linux/Raspberry Pi OS to connect to Wi-Fi.
    Encrypted password storage in config/wifi_config.json.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WifiConfig, cls).__new__(cls)
            cls._instance._init_config()
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = WifiConfig()
        return cls._instance

    def _init_config(self):
        self.ssid = "Home_WiFi"
        self.password = ""
        self.connected = True
        self.load()

    def load(self):
        if WIFI_CONFIG_FILE.exists():
            try:
                with open(WIFI_CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.ssid = data.get("ssid", "Home_WiFi")
                    raw_password = data.get("password", "")
                    self.password = decrypt_password(raw_password)
                    print(f"[WifiConfig Singleton] Loaded Wi-Fi configuration: SSID='{self.ssid}'")
            except Exception as e:
                print(f"[WifiConfig Singleton] Error loading config: {e}")

    def save(self):
        try:
            WIFI_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            encrypted_pw = encrypt_password(self.password)
            with open(WIFI_CONFIG_FILE, "w") as f:
                json.dump({"ssid": self.ssid, "password": encrypted_pw}, f, indent=2)
            print(f"[WifiConfig Singleton] Persisted Wi-Fi connection details: SSID='{self.ssid}' (password encrypted)")
        except Exception as e:
            print(f"[WifiConfig Singleton] Error saving config: {e}")

    def update_wifi(self, ssid: str, password: str = ""):
        cleaned_ssid = ssid.strip()
        if cleaned_ssid:
            self.ssid = cleaned_ssid
            self.password = password
            self.save()
            print(f"[WifiConfig Singleton] Connection updated to SSID: '{self.ssid}'")
            
            # Connect via OS NetworkManager if running on Linux / Raspberry Pi
            self._connect_network_manager()

    def _connect_network_manager(self):
        if sys.platform.startswith("linux"):
            print(f"[NetworkManager] Attempting nmcli Wi-Fi connection to SSID '{self.ssid}'...")
            try:
                cmd = ["nmcli", "dev", "wifi", "connect", self.ssid]
                if self.password.strip():
                    cmd.extend(["password", self.password.strip()])

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    self.connected = True
                    print(f"[NetworkManager] Successfully connected to Wi-Fi '{self.ssid}'!")
                    print(f"STDOUT: {result.stdout.strip()}")
                else:
                    self.connected = False
                    print(f"[NetworkManager] Failed to connect to '{self.ssid}'. Error code: {result.returncode}")
                    print(f"STDERR: {result.stderr.strip()}")
            except FileNotFoundError:
                print("[NetworkManager] 'nmcli' binary not found on this Linux system. Ensure NetworkManager is installed.")
            except Exception as e:
                print(f"[NetworkManager] Exception during nmcli connection: {e}")
        else:
            print(f"[WifiConfig] System platform is '{sys.platform}' (non-Linux). Skipping OS nmcli command execution.")

    def get_session(self) -> requests.Session:
        """
        Returns a requests.Session configured with Wi-Fi connection metadata headers.
        Used by location_service and flight_service for all REST calls.
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": "FlightTrackerApp/1.0",
            "X-WiFi-Connection": self.ssid,
        })
        return session
