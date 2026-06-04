from pathlib import Path


# Ten plik trzyma stale: sciezki, kolory i domyslne parametry animacji.

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "Data"
STATIONS_FILE = DATA_DIR / "stations_df.parquet"
EDGES_FILE = DATA_DIR / "edges_df.parquet"
TRIPS_FILE = DATA_DIR / "final_trip_data.parquet"

# Domyslnie bierzemy wszystkie stacje z pliku danych.
DEFAULT_STATION_COUNT = 801
DEFAULT_MAX_ROUTES = 60
DEFAULT_WINDOW_WIDTH = 2560
DEFAULT_WINDOW_HEIGHT = 1440
WINDOW_SCREEN_RATIO = 0.94
MIN_WINDOW_WIDTH = 960
MIN_WINDOW_HEIGHT = 540
UI_REFERENCE_WIDTH = 1920
UI_REFERENCE_HEIGHT = 1080
UI_MIN_SCALE = 0.86
UI_MAX_SCALE = 1.25
DEFAULT_RENDER_SCALE = 1.35
MAX_RENDER_SCALE = 2.0
MAP_HORIZONTAL_PADDING_FRACTION = 0.04
MAP_VERTICAL_PADDING_FRACTION = 0.02
SIDE_PANEL_WIDTH = 360

BACKGROUND_COLOR = (245, 242, 235)
ROAD_COLOR = (204, 210, 214)
ROUTE_SHADOW_COLOR = (34, 44, 54)
ROUTE_ALPHA = 115
ROUTE_SHADOW_ALPHA = 45
ROUTE_SECONDARY_COLOR = (106, 120, 145)
ROUTE_SECONDARY_ALPHA = 34
ROUTE_TWO_YEARS_ALPHA = 88
ROUTE_TWO_YEARS_SHADOW_ALPHA = 28
STATION_COLOR = (226, 142, 74)
STATION_OUTLINE = (156, 103, 62)
STATION_ALPHA = 185
STATION_INACTIVE_COLOR = (160, 168, 176)
STATION_INACTIVE_OUTLINE = (122, 130, 138)
STATION_INACTIVE_ALPHA = 45
TEXT_COLOR = (35, 42, 50)
WHITE = (255, 255, 255)

COMPARISON_STATION_COUNT = 100
COMPARISON_MAX_ROUTES = 60

DISTRICT_ORDER = [
    "Centrum",
    "Polnoc",
    "Polnocny Wschod",
    "Wschod",
    "Poludniowy Wschod",
    "Poludnie",
    "Poludniowy Zachod",
    "Zachod",
    "Polnocny Zachod",
]
DISTRICT_COLORS = {
    "Centrum": ((42, 130, 128), (16, 90, 92)),
    "Polnoc": ((58, 113, 193), (31, 72, 145)),
    "Polnocny Wschod": ((72, 151, 184), (36, 101, 132)),
    "Wschod": ((74, 156, 102), (38, 106, 66)),
    "Poludniowy Wschod": ((151, 170, 63), (104, 119, 39)),
    "Poludnie": ((218, 151, 55), (157, 97, 32)),
    "Poludniowy Zachod": ((204, 104, 62), (143, 65, 36)),
    "Zachod": ((190, 83, 116), (128, 47, 78)),
    "Polnocny Zachod": ((132, 96, 183), (84, 58, 132)),
}
