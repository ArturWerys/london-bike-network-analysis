from pathlib import Path


# Ten plik trzyma stale: sciezki, kolory i domyslne parametry animacji.

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "Data"
STATIONS_FILE = DATA_DIR / "stations_df.parquet"
EDGES_FILE = DATA_DIR / "edges_df.parquet"
TRIPS_FILE = DATA_DIR / "final_trip_data.parquet"

# Domyslnie bierzemy wszystkie stacje z pliku danych.
DEFAULT_STATION_COUNT = 801
DEFAULT_ROUTE_LENGTH = 10
DEFAULT_MAX_ROUTES = 35
DEFAULT_WINDOW_WIDTH = 1920
DEFAULT_WINDOW_HEIGHT = 1080
SIDE_PANEL_WIDTH = 360

BACKGROUND_COLOR = (245, 242, 235)
ROAD_COLOR = (204, 210, 214)
ROUTE_SHADOW_COLOR = (34, 44, 54)
ROUTE_ALPHA = 115
ROUTE_SHADOW_ALPHA = 45
ROUTE_SECONDARY_COLOR = (106, 120, 145)
ROUTE_SECONDARY_ALPHA = 62
ROUTE_TWO_YEARS_ALPHA = 88
ROUTE_TWO_YEARS_SHADOW_ALPHA = 28
ROUTE_TRANSITION_ALPHA = 92
STATION_COLOR = (226, 92, 67)
STATION_OUTLINE = (122, 62, 51)
STATION_INACTIVE_COLOR = (160, 168, 176)
STATION_INACTIVE_OUTLINE = (122, 130, 138)
STATION_INACTIVE_ALPHA = 120
TEXT_COLOR = (35, 42, 50)
WHITE = (255, 255, 255)

# W tej wersji po kazdej trasie jedzie jeden rowerzysta.
CYCLISTS_PER_ROUTE = 1
COMPARISON_STATION_COUNT = 80
COMPARISON_MAX_ROUTES = 30

DISTRICT_ORDER = ["Centrum", "Polnoc", "Wschod", "Poludnie", "Zachod"]
DISTRICT_COLORS = {
    "Centrum": ((42, 130, 128), (16, 90, 92)),
    "Polnoc": ((64, 112, 181), (36, 75, 132)),
    "Wschod": ((86, 151, 92), (50, 105, 61)),
    "Poludnie": ((216, 139, 49), (154, 91, 31)),
    "Zachod": ((184, 83, 101), (124, 52, 68)),
}
