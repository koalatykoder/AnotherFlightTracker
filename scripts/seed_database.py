import csv
import sqlite3
import sys
from pathlib import Path
import urllib.request

# Add parent directory to sys.path to allow running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DB_PATH, LOGOS_DIR

OPENFLIGHTS_URL = (
    "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"
)


def get_logo_urls(iata: str, icao: str) -> list[str]:
    """
    Returns prioritized high-res logo CDN URLs (128px-256px).
    Tries ICAO first, then IATA, with multiple CDN fallbacks.
    """
    urls = []
    
    # 1. FlightRadar24 High-Res Logotypes (ICAO)
    if icao and len(icao) == 3:
        urls.append(f"https://cdn.flightradar24.com/assets/airlines/logotypes/{icao.lower()}.png")
    
    # 2. FlightAware High-Res Tail Fin / Logo CDN (ICAO)
    if icao and len(icao) == 3:
        urls.append(f"https://www.flightaware.com/images/airline_logos/180px/{icao.upper()}.png")

    # 3. Kiwi/Skypicker CDN (IATA)
    if iata and len(iata) == 2:
        urls.append(f"https://images.kiwi.com/airlines/128x128/{iata.upper()}.png")

    return urls


def download_image(urls: list[str], destination: Path) -> bool:
    """Attempts to download an image trying multiple CDNs until one succeeds."""
    if destination.exists() and destination.stat().st_size > 500:
        return True  # Already downloaded

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) > 500:
                        with open(destination, "wb") as f:
                            f.write(data)
                        return True
        except Exception:
            continue

    return False


def seed_database_and_download_all_logos():
    """Reads airlines.dat, populates SQLite, and bulk-downloads all available logos."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching OpenFlights raw dataset...")
    req = urllib.request.Request(
        OPENFLIGHTS_URL, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as resp:
        lines = [line.decode("utf-8") for line in resp.readlines()]

    reader = csv.reader(lines)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS airlines (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            alias TEXT,
            iata TEXT,
            icao TEXT,
            callsign TEXT,
            country TEXT,
            active TEXT,
            logo_filename TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_iata ON airlines(iata);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_icao ON airlines(icao);")

    records = []
    rows = list(reader)
    total = len(rows)

    print(f"Processing {total} airline records and initiating logo downloads...\n")

    downloaded_count = 0
    skipped_count = 0

    for idx, row in enumerate(rows, 1):
        if len(row) < 8:
            continue

        airline_id = int(row[0]) if row[0] != "\\N" else None
        name = row[1]
        alias = row[2] if row[2] != "\\N" else None
        iata = row[3].upper() if row[3] not in ("\\N", "-", "") else None
        icao = row[4].upper() if row[4] not in ("\\N", "-", "") else None
        callsign = row[5] if row[5] != "\\N" else None
        country = row[6] if row[6] != "\\N" else None
        active = row[7]

        # Determine target filename (favor IATA, fallback to ICAO)
        filename = f"{iata}.png" if iata else (f"{icao}.png" if icao else None)
        logo_saved = False

        if filename:
            dest_path = LOGOS_DIR / filename
            candidate_urls = get_logo_urls(iata, icao)
            
            if candidate_urls:
                logo_saved = download_image(candidate_urls, dest_path)
                if logo_saved:
                    downloaded_count += 1
                else:
                    skipped_count += 1

        records.append((
            airline_id, name, alias, iata, icao, callsign, country, active,
            filename if logo_saved else None
        ))

        # Progress reporting
        if idx % 50 == 0 or idx == total:
            print(f"Progress: [{idx}/{total}] processed | Logos saved: {downloaded_count}")

    # Seed SQLite
    cursor.executemany("""
        INSERT OR REPLACE INTO airlines 
        (id, name, alias, iata, icao, callsign, country, active, logo_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, records)

    conn.commit()
    conn.close()

    print("\n==========================================")
    print(f"✅ Seeding Complete!")
    print(f"• Total Airlines in DB: {len(records)}")
    print(f"• Logos Saved to '{LOGOS_DIR.name}/': {downloaded_count}")
    print(f"==========================================")


if __name__ == "__main__":
    seed_database_and_download_all_logos()
