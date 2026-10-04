from datetime import timedelta
from pathlib import Path
import slint

from config.settings import SLINT_APP_FILE
from services.wifi_service import WifiConfig
from services.location_service import get_device_location
from services.flight_service import fetch_nearby_flights
from services.airline_service import get_airline_info

ui = slint.load_file(SLINT_APP_FILE)

class FlightTrackerApp(ui.MainWindow):
    def __init__(self):
        super().__init__()
        
        # 1. Initialize Wi-Fi singleton & sync UI state
        self.wifi_config = WifiConfig.get_instance()
        self.WifiSettings.wifi_ssid = self.wifi_config.ssid
        self.WifiSettings.wifi_password = self.wifi_config.password

        # 2. Resolve location at startup using current Wi-Fi connection
        self.location = get_device_location()

        # 3. Immediately fetch flights so the UI isn't blank on first load
        self.update_telemetry()

        # 4. Start Slint timer to poll flight API every 10 seconds
        self.timer = slint.Timer()
        self.timer.start(
            slint.TimerMode.Repeated,
            timedelta(seconds=10),
            self.update_telemetry
        )

    @slint.callback("WifiSettings", name="wifi_updated")
    def handle_wifi_update(self, new_ssid: str, new_password: str):
        print(f"[Main App] Received Wi-Fi update request: SSID = '{new_ssid}'")
        self.wifi_config.update_wifi(new_ssid, new_password)
        self.WifiSettings.wifi_ssid = self.wifi_config.ssid
        self.WifiSettings.wifi_password = self.wifi_config.password
        
        # Re-query location & telemetry using new connection details
        self.location = get_device_location(force_refresh=True)
        self.update_telemetry()

    def update_telemetry(self):
            self.flights = fetch_nearby_flights(self.location["lat"], self.location["lon"])
            
            if self.flights:
                ac = self.flights[0]
                flight_dict = ac.to_slint_dict(user_city=self.location["city"])

                callsign = flight_dict.get("callsign", "")
                airline_info = get_airline_info(callsign)

                # Ensure airline name is populated as a string
                if "airline_name" in airline_info and airline_info["airline_name"]:
                    flight_dict["airline_name"] = str(airline_info["airline_name"])

                # Handle Image type strictly for Slint
                logo_path = airline_info.get("logo_path")
                if logo_path and Path(logo_path).exists():
                    try:
                        flight_dict["airline_logo"] = slint.Image.load_from_path(str(logo_path))
                    except Exception as e:
                        print(f"[Main App] Error loading image '{logo_path}': {e}")
                        flight_dict["airline_logo"] = slint.Image()
                else:
                    flight_dict["airline_logo"] = slint.Image()

                self.Telemetry.has_active_flight = True
                self.Telemetry.active_flight = flight_dict
            else:
                self.Telemetry.has_active_flight = False

if __name__ == "__main__":
    app = FlightTrackerApp()
    app.run()