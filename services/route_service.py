import json
import os
import time
from typing import Optional

from config.settings import FLIGHTAWARE_CONFIG_FILE
from services.wifi_service import WifiConfig
from services.airline_service import get_airline_info

ROUTE_CACHE: dict = {}
CACHE_TTL_SECONDS = 7200          # 2 Hours – flight number stable within a day
ABSENCE_EVICTION_SECONDS = 1200   # 20 Minutes – drop entries for planes no longer overhead


def get_flightaware_api_key() -> str:
    """Retrieves FlightAware AeroAPI key from environment variable or config/flightaware_config.json."""
    env_key = os.getenv("FLIGHTAWARE_API_KEY", "").strip()
    if env_key:
        return env_key
    if FLIGHTAWARE_CONFIG_FILE.exists():
        try:
            with open(FLIGHTAWARE_CONFIG_FILE, "r") as f:
                data = json.load(f)
                return str(data.get("api_key", "")).strip()
        except Exception:
            pass
    return ""


def cleanup_route_cache():
    """Purges expired entries (TTL > 2h) or entries not seen in > 20 mins."""
    now = time.time()
    expired_keys = [
        key for key, item in ROUTE_CACHE.items()
        if item and (
            (now - item.get("timestamp", 0) > CACHE_TTL_SECONDS) or
            (now - item.get("last_seen", 0) > ABSENCE_EVICTION_SECONDS)
        )
    ]
    for k in expired_keys:
        ROUTE_CACHE.pop(k, None)


def fetch_flightaware_route(callsign: str, api_key: str) -> Optional[dict]:
    """
    Queries FlightAware AeroAPI v4 for active flight schedule/route info.
    Endpoint: GET /flights/{ident}
    Returns the raw JSON response dict on success (keyed on 'flights'), or None.
    """
    clean_callsign = str(callsign or "").strip()
    if not clean_callsign or not api_key:
        return None

    wifi_config = WifiConfig.get_instance()
    url = f"https://aeroapi.flightaware.com/aeroapi/flights/{clean_callsign}"
    headers = {
        "x-apikey": api_key,
        "Accept": "application/json; charset=UTF-8",
    }

    try:
        session = wifi_config.get_session()
        response = session.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            flights = data.get("flights", [])
            if flights and isinstance(flights, list):
                flt = flights[0]
                orig = (flt.get("origin") or {}).get("code_iata") or \
                       (flt.get("origin") or {}).get("code_icao") or "N/A"
                dest = (flt.get("destination") or {}).get("code_iata") or \
                       (flt.get("destination") or {}).get("code_icao") or "N/A"
                print(f"[FlightAware API] Resolved active route for {clean_callsign}: {orig} -> {dest}")
                return data  # populate_route() reads the top-level "flights" key
        elif response.status_code == 401:
            print(f"[FlightAware API] Unauthorized – check your API key.")
        elif response.status_code == 429:
            print(f"[FlightAware API] Rate limit hit for '{clean_callsign}'.")
        else:
            print(f"[FlightAware API] HTTP {response.status_code} for '{clean_callsign}'.")
    except Exception as e:
        print(f"[FlightAware API] Exception for '{clean_callsign}': {e}")
    return None


def fetch_vrs_route(callsign: str) -> Optional[dict]:
    """
    Fallback query to vrs-standing-data.adsb.lol endpoint.
    Constructs URL: https://vrs-standing-data.adsb.lol/routes/{prefix}/{callsign}.json
    Parses the exact 'airports' array schema and converts to FlightAware compatibility format.
    """
    clean_callsign = str(callsign or "").strip().upper()
    if not clean_callsign or clean_callsign == "N/A" or len(clean_callsign) < 3:
        return None

    prefix = clean_callsign[:2]
    url = f"https://vrs-standing-data.adsb.lol/routes/{prefix}/{clean_callsign}.json"
    wifi_config = WifiConfig.get_instance()

    try:
        session = wifi_config.get_session()
        response = session.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            airports = data.get("_airports", [])

            if isinstance(airports, list) and len(airports) >= 2:
                orig_apt = airports[0]
                dest_apt = airports[1]

                orig_iata = orig_apt.get("iata") or "N/A"
                orig_icao = orig_apt.get("icao") or "N/A"
                dest_iata = dest_apt.get("iata") or "N/A"
                dest_icao = dest_apt.get("icao") or "N/A"

                print(f"[VRS Standing Data] Resolved route for {clean_callsign}: {orig_iata}/{orig_icao} -> {dest_iata}/{dest_icao}")

                # Format matching FlightAware's schema expected by populate_route()
                return {
                    "flights": [
                        {
                            "origin": {
                                "code_iata": orig_iata, 
                                "code_icao": orig_icao, 
                                "city": orig_apt.get("location") or "Nearby Sky",
                                "latitude": orig_apt.get("lat"),
                                "longitude": orig_apt.get("lon")
                            },
                            "destination": {
                                "code_iata": dest_iata, 
                                "code_icao": dest_icao, 
                                "city": dest_apt.get("location") or "Tracking",
                                "latitude": dest_apt.get("lat"),
                                "longitude": dest_apt.get("lon")
                            },
                            "aircraft_type": data.get("airline_code") or "Overhead Traffic"
                        }
                    ]
                }
        elif response.status_code != 404:
            print(f"[VRS Standing Data] HTTP {response.status_code} for '{clean_callsign}'.")
    except Exception as e:
        print(f"[VRS Standing Data] Exception for '{clean_callsign}': {e}")

    return None


def fetch_flight_route(callsign: str, icao24: str = "") -> Optional[dict]:
    """
    Resolves route info for a callsign with TTL + absence caching.
    Priority:
      1. In-memory ROUTE_CACHE (keyed by callsign + ICAO24, TTL = 2h)
      2. Primary: FlightAware AeroAPI (if API key is present and valid)
      3. Secondary: vrs-standing-data.adsb.lol single JSON lookup
      4. Airline Lookup: Uses airline_service.get_airline_info() to attach carrier name
    """
    clean_callsign = str(callsign or "").strip()
    if not clean_callsign or clean_callsign == "N/A":
        return None

    cache_key = f"{clean_callsign}_{icao24.lower()}" if icao24 else clean_callsign
    now = time.time()

    # 1. Serve from cache if still fresh
    if cache_key in ROUTE_CACHE:
        item = ROUTE_CACHE[cache_key]
        if "data" in item and (now - item.get("timestamp", 0) <= CACHE_TTL_SECONDS):
            item["last_seen"] = now  # Touch last-seen timestamp
            print(f"[Route Cache] HIT for {cache_key} (age {int(now - item['timestamp'])}s)")
            return item.get("data")

    # Evict stale entries before making a live request
    cleanup_route_cache()

    route_data = None
    fa_key = get_flightaware_api_key()

    # 2. Primary Lookup: FlightAware AeroAPI
    if fa_key:
        route_data = fetch_flightaware_route(clean_callsign, fa_key)

    # 3. Secondary Lookup: vrs-standing-data.adsb.lol (if no FA key or FA lookup failed)
    if not route_data:
        route_data = fetch_vrs_route(clean_callsign)

    # Prepare dictionary if route fetch returned None
    if not route_data:
        route_data = {}

    # 4. Attach carrier name from unified airline service
    airline_info = get_airline_info(clean_callsign)
    if airline_info and "error" not in airline_info:
        route_data["airline_name"] = airline_info.get("name", "Unknown Airline")

    # Store result to avoid hammering endpoints for unknown callsigns
    print(f"[Route Cache] MISS for {cache_key} – storing fresh result (data={'found' if route_data else 'none'})")
    ROUTE_CACHE[cache_key] = {
        "data": route_data,
        "timestamp": now,
        "last_seen": now,
    }

    return route_data
