import argparse
from pathlib import Path

from .config import (
    DATA_DIR,
    DEFAULT_MAX_ROUTES,
    DEFAULT_ROUTE_LENGTH,
    DEFAULT_STATION_COUNT,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
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
        help="Number of stations used when --stations is omitted. Default: all 801 stations.",
    )
    parser.add_argument(
        "--route-length",
        type=int,
        default=DEFAULT_ROUTE_LENGTH,
        help="Legacy parameter kept for cache compatibility (not used in top-pairs route mode).",
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
        default=16.0,
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
    parser.add_argument("--width", type=int, default=DEFAULT_WINDOW_WIDTH, help="Pygame window width.")
    parser.add_argument("--height", type=int, default=DEFAULT_WINDOW_HEIGHT, help="Pygame window height.")
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
