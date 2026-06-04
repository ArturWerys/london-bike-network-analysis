import argparse
from pathlib import Path

from .config import (
    DATA_DIR,
    DEFAULT_MAX_ROUTES,
    DEFAULT_RENDER_SCALE,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_STATION_COUNT,
    MAX_RENDER_SCALE,
    WINDOW_SCREEN_RATIO,
)


# Argumenty terminala: ile stacji, jak dlugie trasy, predkosc i cache.


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Animate cyclists moving at constant speed between many "
            "London Santander Cycles stations along shortest OSM bike routes."
        )
    )
    parser.add_argument(
        "--stations",
        nargs="*",
        default=None,
        metavar="STATION",
        help=(
            "Optional station names from Data/stations_df.parquet. "
            "If omitted, top stations are selected from Data/edges_df.parquet."
        ),
    )
    parser.add_argument(
        "--station-count",
        type=int,
        default=DEFAULT_STATION_COUNT,
        help=f"Number of stations used when --stations is omitted. Default: {DEFAULT_STATION_COUNT} top stations.",
    )
    parser.add_argument(
        "--max-routes",
        type=int,
        default=DEFAULT_MAX_ROUTES,
        help="Maximum number of routes shown on the map. Top routes by network traffic are kept.",
    )
    parser.add_argument(
        "--list-stations",
        metavar="TEXT",
        help="Print station names containing TEXT and exit.",
    )
    parser.add_argument(
        "--speed-kmh",
        type=float,
        default=12.0,
        help="Simulated cyclist speed in km/h.",
    )
    parser.add_argument(
        "--time-scale",
        type=float,
        default=85.0,
        help="Animation acceleration. 85 means one real second equals 85 simulated seconds.",
    )
    parser.add_argument(
        "--buffer-meters",
        type=float,
        default=1200.0,
        help="OSM download buffer around the selected stations.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help=(
            f"Pygame window width. If omitted, the window targets {DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT} "
            f"and fits within {int(WINDOW_SCREEN_RATIO * 100)}%% of the screen width."
        ),
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help=(
            f"Pygame window height. If omitted, the window targets {DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT} "
            f"and fits within {int(WINDOW_SCREEN_RATIO * 100)}%% of the screen height."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=DATA_DIR / "osm_route_cache",
        type=Path,
        help="Directory for cached OSMnx graph files.",
    )
    parser.add_argument(
        "--refresh-osm",
        action="store_true",
        help="Ignore cached graph and download the OSM bike network again.",
    )
    parser.add_argument(
        "--refresh-map",
        action="store_true",
        help="Ignore cached map image and download map tiles again.",
    )
    parser.add_argument(
        "--refresh-routes",
        action="store_true",
        help="Ignore cached route geometry and calculate routes again.",
    )
    parser.add_argument(
        "--map-zoom",
        type=int,
        default=13,
        help="CartoDB Positron tile zoom.",
    )
    parser.add_argument(
        "--render-scale",
        type=float,
        default=DEFAULT_RENDER_SCALE,
        help=(
            "Static map quality multiplier. Higher values make routes/stations sharper "
            f"but use more memory. Default: {DEFAULT_RENDER_SCALE}; maximum: {MAX_RENDER_SCALE}."
        ),
    )
    parser.add_argument(
        "--max-real-seconds",
        type=float,
        default=None,
        help="Close the animation automatically after this many real seconds.",
    )
    parser.add_argument(
        "--mode",
        choices=["two_years", "weekday_weekend"],
        default=None,
        help="Run a specific mode. If omitted, a short menu is shown at startup.",
    )
    return parser.parse_args()
