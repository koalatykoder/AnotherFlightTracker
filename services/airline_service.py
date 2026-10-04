import sqlite3
import re
import urllib.request
from pathlib import Path
from typing import Optional, List

from config.settings import DB_PATH, LOGOS_DIR

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_cdn_urls(iata: Optional[str], icao: Optional[str]) -> List[str]:
    """Prioritized list of high-res CDN endpoints for on-demand logo fetching."""
    urls = []
    if icao and len(icao) == 3:
        urls.append(f"https://cdn.flightradar24.com/assets/airlines/logotypes/{icao.lower()}.png")
        urls.append(f"https://www.flightaware.com/images/airline_logos/180px/{icao.upper()}.png")
    if iata and len(iata) == 2:
        urls.append(f"https://images.kiwi.com/airlines/128x128/{iata.upper()}.png")
    return urls


def ensure_logo_cached(iata: Optional[str], icao: Optional[str], logo_filename: Optional[str]) -> Optional[str]:
    """Checks local storage for logo. If missing, downloads and caches it on demand."""
    if not logo_filename:
        return None

    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    local_path = LOGOS_DIR / logo_filename

    # Return immediately if already cached on disk
    if local_path.exists() and local_path.stat().st_size > 500:
        return str(local_path)

    # Lazily fetch from CDN only on cache miss
    for url in get_cdn_urls(iata, icao):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) > 500:
                        with open(local_path, "wb") as f:
                            f.write(data)
                        return str(local_path)
        except Exception:
            continue

    return None


def get_airline_info(flight_number: str) -> dict:
    """
    Fast SQLite lookup with transparent on-demand logo caching.
    Supports commercial IATA/ICAO flight numbers and general aviation tail registrations.
    """
    cleaned = flight_number.strip().replace(" ", "").upper()

    # Early exit for US (e.g. N415DL) and Canadian (e.g. C-GFAJ) N-number/registration tail numbers
    if re.match(r"^N\d+[A-Z0-9]*$", cleaned) or re.match(r"^C-[A-Z]{4}$", cleaned):
        return {
            "flight_number": flight_number,
            "airline_name": "General Aviation / Private",
            "name": "General Aviation / Private",
            "iata": None,
            "icao": None,
            "country": "United States" if cleaned.startswith("N") else "Canada",
            "logo_path": None,
        }

    match = re.match(r"^([A-Z0-9]{2,3})\d*$", cleaned)
    if not match:
        return {"error": "Invalid flight number format", "airline_name": "Unknown Airline", "logo_path": None}

    prefix = match.group(1)

    if not DB_PATH.exists():
        print(f"[Airline Service] Warning: {DB_PATH} not found.")
        return {"error": "Database not found", "airline_name": "Unknown Airline", "logo_path": None}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    row = None
    if len(prefix) == 3:
        cursor.execute("SELECT name, iata, icao, country FROM airlines WHERE icao = ?", (prefix,))
        row = cursor.fetchone()
        # Fallback check if 3-char prefix was a 2-char IATA code + flight digit
        if not row:
            cursor.execute("SELECT name, iata, icao, country FROM airlines WHERE iata = ?", (prefix[:2],))
            row = cursor.fetchone()
    else:
        cursor.execute("SELECT name, iata, icao, country FROM airlines WHERE iata = ?", (prefix,))
        row = cursor.fetchone()

    conn.close()

    if not row:
        return {"error": f"Airline prefix '{prefix}' not found", "airline_name": "Unknown Airline", "logo_path": None}

    name, iata, icao, country = row
    filename = f"{iata}.png" if iata else (f"{icao}.png" if icao else None)

    # Resolve logo path (instant disk load or lazy HTTP fetch)
    logo_path = ensure_logo_cached(iata, icao, filename)

    return {
        "flight_number": flight_number,
        "airline_name": name,
        "name": name,
        "iata": iata,
        "icao": icao,
        "country": country,
        "logo_path": logo_path,
    }
