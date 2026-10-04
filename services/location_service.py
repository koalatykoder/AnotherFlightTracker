import json
from pathlib import Path

from config.settings import LOCATION_CACHE_FILE
from services.wifi_service import WifiConfig

def get_device_location(force_refresh: bool = False) -> dict:
    """
    Returns (lat, lon, city) dict.
    Checks local JSON cache first; falls back to IP geolocation API using active Wi-Fi connection.
    """
    if LOCATION_CACHE_FILE.exists() and not force_refresh:
        try:
            with open(LOCATION_CACHE_FILE, "r") as f:
                data = json.load(f)
                print(f"[Location] Loaded from cache: {data['city']} ({data['lat']}, {data['lon']})")
                return data
        except Exception as e:
            print(f"[Location] Cache read error: {e}")

    # Fetch from IP geolocation endpoint using Wi-Fi connection singleton
    wifi_config = WifiConfig.get_instance()
    print(f"[Location] Querying IP geolocation API over Wi-Fi network '{wifi_config.ssid}'...")
    try:
        session = wifi_config.get_session()
        response = session.get("http://ip-api.com/json/", timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            location = {
                "lat": res_data["lat"],
                "lon": res_data["lon"],
                "city": f"{res_data['city']}, {res_data['countryCode']}"
            }
            # Cache the result locally in config/
            LOCATION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOCATION_CACHE_FILE, "w") as f:
                json.dump(location, f, indent=2)
            print(f"[Location] Resolved and cached: {location['city']}")
            return location
    except Exception as e:
        print(f"[Location] API lookup failed: {e}")

    # Fallback default if completely offline
    return {"lat": 39.8361, "lon": -105.0372, "city": "Denver, US"}
