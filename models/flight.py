from dataclasses import dataclass
import math
import time
from typing import Optional

from utils.geometry import (
    calculate_haversine_distance,
    calculate_slant_range,
    calculate_elevation_angle,
    heading_to_cardinal,
)

@dataclass
class FlightData:
    """
    Core Flight Data model shared across API service and Slint UI layer.
    Includes 3D visual geometry calculations (slant range, elevation angle, viewability)
    and route/airline information merged directly into this single model.
    """
    icao24: str
    airline_name: str = "Unknown Airline"
    callsign: str = "N/A"
    origin_country: str = "Unknown Country Origin"
    lat: float = 0.0
    lon: float = 0.0
    altitude_ft: int = 0
    speed_mph: int = 0
    heading: float = 0.0
    on_ground: bool = False
    distance_miles: float = 0.0
    slant_distance_miles: float = 0.0
    elevation_angle: float = 0.0

    # Route & Metadata Attributes
    aircraft_type: str = "Unknown Aircraft"
    origin_code: str = "Unknown Origin"
    origin_city: str = ""
    dest_code: str = "Unknown Destination"
    dest_city: str = ""
    progress_percent: float = 0.50

    # Optional coordinates for calculating dynamic progress
    origin_lat: Optional[float] = None
    origin_lon: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None

    def populate_route(self, route_info: Optional[dict] = None) -> None:
        """Populates origin, destination, aircraft type, airline name, and progress from route dict."""
        if not route_info or not isinstance(route_info, dict):
            return

        # 1. Populate airline name if resolved from local DAT / API
        if route_info.get("airline_name"):
            self.airline_name = str(route_info["airline_name"])

        # 2. Handle structured flight schedule response (FlightAware/VRS fallback format)
        if "flights" in route_info and isinstance(route_info["flights"], list) and route_info["flights"]:
            flt = route_info["flights"][0]
            orig = flt.get("origin", {}) or {}
            dest = flt.get("destination", {}) or {}
            ac_type = flt.get("aircraft_type") or flt.get("type")

            dep_code = orig.get("code_iata") or orig.get("code_icao") or orig.get("code") or "NEARBY"
            arr_code = dest.get("code_iata") or dest.get("code_icao") or dest.get("code") or "IN RANGE"
            dep_city = orig.get("city") or orig.get("name") or "Nearby Sky"
            arr_city = dest.get("city") or dest.get("name") or "Tracking"

            if ac_type:
                self.aircraft_type = f"{ac_type} ({self.origin_country})"

            self.origin_code = str(dep_code).upper()
            self.origin_city = str(dep_city)
            self.dest_code = str(arr_code).upper()
            self.dest_city = str(arr_city)

            # Optional route coordinates
            self.origin_lat = orig.get("latitude")
            self.origin_lon = orig.get("longitude")
            self.dest_lat = dest.get("latitude")
            self.dest_lon = dest.get("longitude")

            # Dynamic progress calculation based on coordinates
            if (
                self.origin_lat is not None and self.origin_lon is not None and
                self.dest_lat is not None and self.dest_lon is not None
            ):
                total_dist = calculate_haversine_distance(
                    self.origin_lat, self.origin_lon,
                    self.dest_lat, self.dest_lon
                )
                if total_dist > 10.0:
                    flown_dist = calculate_haversine_distance(
                        self.origin_lat, self.origin_lon,
                        self.lat, self.lon
                    )
                    self.progress_percent = max(0.05, min(0.95, round(flown_dist / total_dist, 2)))
            return

        # 3. Handle raw single route dictionary
        origin = route_info.get("origin", {}) or {}
        destination = route_info.get("destination", {}) or {}
        airline = route_info.get("airline", {}) or {}

        if airline.get("name"):
            self.airline_name = airline.get("name")
            self.aircraft_type = f"{airline.get('name')} ({self.origin_country})"

        if origin:
            self.origin_code = str(origin.get("iata_code") or origin.get("icao_code") or "NEARBY").upper()
            self.origin_city = str(origin.get("municipality") or origin.get("name") or "Nearby Sky")

        if destination:
            self.dest_code = str(destination.get("iata_code") or destination.get("icao_code") or "IN RANGE").upper()
            self.dest_city = str(destination.get("municipality") or destination.get("name") or "Tracking")

        if "departure_time" in route_info and "arrival_time" in route_info:
            current_time = time.time()
            departure_time = route_info["departure_time"]
            arrival_time = route_info["arrival_time"]
            if departure_time < current_time < arrival_time:
                self.progress_percent = (current_time - departure_time) / (arrival_time - departure_time)
            elif current_time < departure_time:
                self.progress_percent = 0.0
            else:
                self.progress_percent = 1.0

    @classmethod
    def from_api_state(cls, state: list, user_lat: float, user_lon: float) -> Optional['FlightData']:
        """Parses a raw OpenSky state vector array into a FlightData dataclass with viewability metrics."""
        if not state or len(state) < 14:
            return None
        
        ac_lat = state[6]
        ac_lon = state[5]
        
        if ac_lat is None or ac_lon is None:
            return None

        icao24 = str(state[0] or "").strip()
        callsign = str(state[1] or "N/A").strip() or "N/A"
        origin_country = str(state[2] or "Unknown").strip()
        
        # Altitude: prefer geo_altitude (index 13), fallback to baro_altitude (index 7)
        alt_meters = state[13] if state[13] is not None else state[7]
        altitude_ft = int(alt_meters * 3.28084) if alt_meters is not None else 0

        # Velocity: meters per second to mph
        velocity_ms = state[9]
        speed_mph = int(velocity_ms * 2.23694) if velocity_ms is not None else 0

        heading = float(state[10]) if state[10] is not None else 0.0
        on_ground = bool(state[8]) if state[8] is not None else False

        # Ground distance (miles)
        distance = calculate_haversine_distance(user_lat, user_lon, ac_lat, ac_lon)

        # 3D Slant Range Distance (miles)
        slant_distance = calculate_slant_range(distance, altitude_ft)

        # Elevation Angle above horizon (degrees)
        elevation_angle = calculate_elevation_angle(distance, altitude_ft)

        return cls(
            icao24=icao24,
            callsign=callsign,
            origin_country=origin_country,
            lat=ac_lat,
            lon=ac_lon,
            altitude_ft=altitude_ft,
            speed_mph=speed_mph,
            heading=heading,
            on_ground=on_ground,
            distance_miles=round(distance, 2),
            slant_distance_miles=round(slant_distance, 2),
            elevation_angle=round(elevation_angle, 1)
        )

    def is_viewable(
        self, 
        max_ground_dist: float = 15.0, 
        min_elevation: float = 12.0, 
        max_slant_dist: float = 18.0
    ) -> bool:
        """Determines if aircraft is physically viewable from the ground by an outdoor observer."""
        if self.on_ground or self.altitude_ft < 500:
            return False
        if self.distance_miles > max_ground_dist:
            return False
        if self.elevation_angle < min_elevation:
            return False
        if self.slant_distance_miles > max_slant_dist:
            return False
        return True

    def to_slint_dict(self, user_city: str = "") -> dict:
        """Converts the FlightData object into a dict matching Slint's FlightData struct."""
        orig_city = self.origin_city if self.origin_city else (user_city or "Nearby Sky")
        dst_city = self.dest_city if self.dest_city else f"Dist: {self.distance_miles} mi (Elev: {self.elevation_angle}°)"

        return {
            "callsign": str(self.callsign) if self.callsign else "N/A",
            "airline_name": str(self.airline_name) if self.airline_name else "",
            "aircraft_type": str(self.aircraft_type) if self.aircraft_type else f"Overhead ({self.origin_country})",
            "origin_code": str(self.origin_code) if self.origin_code else "",
            "origin_city": str(orig_city),
            "dest_code": str(self.dest_code) if self.dest_code else "",
            "dest_city": str(dst_city),
            "altitude": f"{self.altitude_ft:,} ft" if self.altitude_ft else "N/A",
            "speed": f"{self.speed_mph} mph" if self.speed_mph else "N/A",
            "progress_percent": float(self.progress_percent),
            "distance_miles": float(self.distance_miles),
            "elevation_angle": float(self.elevation_angle),
            "heading": float(self.heading),
            "heading_text": str(heading_to_cardinal(self.heading)),
            "icao24": str(self.icao24) if self.icao24 else "",
            "temperature_text": "55 °F",
        }
