import hashlib
from pathlib import Path

from .models import Station


# Nazwy plikow cache zalezne od stacji, zakresu mapy i zoomu.


def graph_cache_path(cache_dir: Path, bbox: tuple[float, float, float, float], stations: list[Station]) -> Path:
    key_data = {
        "bbox": tuple(round(value, 5) for value in bbox),
        "stations": [station.name for station in stations],
        "network_type": "bike",
    }
    digest = hashlib.sha1(repr(key_data).encode("utf-8")).hexdigest()[:12]
    return cache_dir / f"london_bike_graph_{digest}.graphml"


def map_cache_path(
    cache_dir: Path,
    bounds: tuple[float, float, float, float],
    width: int,
    height: int,
    zoom: int | None,
) -> Path:
    key_data = {
        "bounds_3857": tuple(round(value, 1) for value in bounds),
        "width": width,
        "height": height,
        "zoom": zoom or "auto",
        "source": "CartoDB.Positron",
    }
    digest = hashlib.sha1(repr(key_data).encode("utf-8")).hexdigest()[:12]
    return cache_dir / "basemaps" / f"cartodb_positron_{digest}.png"


def routes_cache_path(
    cache_dir: Path,
    stations: list[Station],
    route_length: int,
    graph_cache_name: str,
    cache_label: str = "",
) -> Path:
    key_data = {
        "stations": [station.name for station in stations],
        "route_length": route_length,
        "graph": graph_cache_name,
        "label": cache_label,
        "version": "simple-routing-v2",
    }
    digest = hashlib.sha1(repr(key_data).encode("utf-8")).hexdigest()[:12]
    return cache_dir / "routes" / f"routes_{digest}.json"
