from pathlib import Path

# Base project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Subdirectories
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
LOGOS_DIR = ASSETS_DIR / "logos"
UI_DIR = BASE_DIR / "ui"

# Configuration & Cache files
WIFI_CONFIG_FILE = CONFIG_DIR / "wifi_config.json"
FLIGHTAWARE_CONFIG_FILE = CONFIG_DIR / "flightaware_config.json"
LOCATION_CACHE_FILE = CONFIG_DIR / "location_cache.json"

# Data & Asset files
DB_PATH = DATA_DIR / "flights.db"
AIRLINES_DAT_PATH = DATA_DIR / "airlines.dat"
SLINT_APP_FILE = BASE_DIR / "app.slint"
