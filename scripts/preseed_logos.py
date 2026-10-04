import sqlite3
import sys
import urllib.request
from pathlib import Path

# Add parent directory to sys.path to allow running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DB_PATH, LOGOS_DIR

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Top ~30 major global and domestic commercial airlines (IATA / ICAO)
TOP_AIRLINES = [
    # Major US Carriers
    ("UA", "UAL"),  # United
    ("AA", "AAL"),  # American
    ("DL", "DAL"),  # Delta
    ("WN", "SWA"),  # Southwest
    ("AS", "ASA"),  # Alaska
    ("B6", "JBU"),  # JetBlue
    ("NK", "NKS"),  # Spirit
    ("F9", "FFT"),  # Frontier
    ("HA", "HAL"),  # Hawaiian
    ("G4", "AAY"),  # Allegiant
    # Canadian & European
    ("AC", "ACA"),  # Air Canada
    ("WS", "WJA"),  # WestJet
    ("BA", "BAW"),  # British Airways
    ("LH", "DLH"),  # Lufthansa
    ("AF", "AFR"),  # Air France
    ("KL", "KLM"),  # KLM
    ("IB", "IBE"),  # Iberia
    ("EI", "EIN"),  # Aer Lingus
    ("FR", "RYR"),  # Ryanair
    ("U2", "EZY"),  # easyJet
    # Middle East & Asia-Pacific
    ("EK", "UAE"),  # Emirates
    ("QR", "QTR"),  # Qatar Airways
    ("EY", "ETD"),  # Etihad
    ("SQ", "SIA"),  # Singapore Airlines
    ("CX", "CPA"),  # Cathay Pacific
    ("NH", "ANA"),  # ANA
    ("JL", "JAL"),  # Japan Airlines
    ("QF", "QFA"),  # Qantas
    ("NZ", "ANZ"),  # Air New Zealand
    ("VA", "VOZ"),  # Virgin Australia
]


def get_cdn_urls(iata: str, icao: str) -> list[str]:
    """Prioritized CDN endpoints for downloading high-res logos (128px-180px)."""
    urls = []
    if icao and len(icao) == 3:
        urls.append(f"https://cdn.flightradar24.com/assets/airlines/logotypes/{icao.lower()}.png")
        urls.append(f"https://www.flightaware.com/images/airline_logos/180px/{icao.upper()}.png")
    if iata and len(iata) == 2:
        urls.append(f"https://images.kiwi.com/airlines/128x128/{iata.upper()}.png")
    return urls


def download_logo(iata: str, icao: str) -> bool:
    """Attempts to download a logo to disk using CDN fallbacks."""
    filename = f"{iata}.png" if iata else f"{icao}.png"
    target_path = LOGOS_DIR / filename

    # Skip if already downloaded and valid
    if target_path.exists() and target_path.stat().st_size > 500:
        return True

    for url in get_cdn_urls(iata, icao):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=4) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) > 500:
                        with open(target_path, "wb") as f:
                            f.write(data)
                        return True
        except Exception:
            continue

    return False


def preseed_top_logos():
    """Iterates through top airlines and downloads missing logos into assets/logos/."""
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        print(f"Error: Database file '{DB_PATH.name}' not found. Seed the database first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Pre-seeding logos for {len(TOP_AIRLINES)} major commercial carriers...")
    cached_count = 0
    failed_count = 0

    for iata, icao in TOP_AIRLINES:
        # Verify carrier exists in local SQLite database
        cursor.execute(
            "SELECT name FROM airlines WHERE iata = ? OR icao = ?", (iata, icao)
        )
        row = cursor.fetchone()
        airline_name = row[0] if row else "Unknown Carrier"

        success = download_logo(iata, icao)
        if success:
            cached_count += 1
            print(f"  [OK] {iata}/{icao} - {airline_name}")
        else:
            failed_count += 1
            print(f"  [FAIL] Could not fetch logo for {iata}/{icao} ({airline_name})")

    conn.close()

    total_bytes = sum(f.stat().st_size for f in LOGOS_DIR.glob("*.png"))
    size_mb = total_bytes / (1024 * 1024)

    print("\n" + "=" * 45)
    print("Pre-seeding Complete!")
    print(f"• Logos cached: {cached_count}/{len(TOP_AIRLINES)}")
    print(f"• Folder size: {size_mb:.2f} MB ({LOGOS_DIR})")
    print("=" * 45)


if __name__ == "__main__":
    preseed_top_logos()
