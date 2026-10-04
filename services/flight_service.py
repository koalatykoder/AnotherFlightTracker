from typing import List

from models.flight import FlightData
from utils.geometry import calculate_bounding_box
from services.wifi_service import WifiConfig
from services.route_service import fetch_flight_route

def fetch_nearby_flights(
    lat: float,
    lon: float,
    radius_miles: float = 15.0,
    filter_viewable: bool = True,
) -> List[FlightData]:
    """
    Fetches overhead aircraft state vectors from OpenSky Network inside a bounding box,
    filters for physically viewable flights, and returns them sorted by proximity with route data populated.
    """
    box = calculate_bounding_box(lat, lon, radius_miles)
    url = (
        f"https://opensky-network.org/api/states/all?"
        f"lamin={box['lamin']:.4f}&lamax={box['lamax']:.4f}&"
        f"lomin={box['lomin']:.4f}&lomax={box['lomax']:.4f}"
    )

    wifi_config = WifiConfig.get_instance()
    flights: List[FlightData] = []

    try:
        session = wifi_config.get_session()
        response = session.get(url, timeout=5)
        if response.status_code == 200:
            raw_states = response.json().get("states", []) or []
            for state in raw_states:
                flight = FlightData.from_api_state(state, lat, lon)
                if flight:
                    if filter_viewable and not flight.is_viewable(max_ground_dist=radius_miles):
                        continue
                    flights.append(flight)

            # Sort flights by ground distance (closest first)
            flights.sort(key=lambda f: f.distance_miles)

            # Populate route information for the top 5 closest viewable flights
            for flight in flights[:5]:
                route = fetch_flight_route(flight.callsign, flight.icao24)
                if route:
                    flight.populate_route(route)

            if flights:
                closest = flights[0]
                print(
                    f"[Flight API] Found {len(flights)} viewable flight(s). "
                    f"Closest: {closest.callsign} ({closest.airline_name} - {closest.origin_code} -> {closest.dest_code}, "
                    f"{closest.distance_miles} mi away, elev: {closest.elevation_angle}°, alt: {closest.altitude_ft:,} ft)"
                )
            else:
                print(f"[Flight API] No viewable airborne flights found in {radius_miles}-mile range.")
    except Exception as e:
        print(f"[Flight API - Wi-Fi: {wifi_config.ssid}] Fetch error: {e}")

    return flights
