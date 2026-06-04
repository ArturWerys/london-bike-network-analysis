import bisect
import math
from typing import Any

from .config import MAP_HORIZONTAL_PADDING_FRACTION, MAP_VERTICAL_PADDING_FRACTION
from .models import Station


# Geometria: przeliczenia lon/lat, odleglosci i dopasowanie mapy do ekranu.


def bbox_around_stations(stations: list[Station], buffer_meters: float) -> tuple[float, float, float, float]:
    lat_values = [station.lat for station in stations]
    lon_values = [station.lon for station in stations]
    mean_lat = math.radians(sum(lat_values) / len(lat_values))

    lat_margin = buffer_meters / 111_320
    lon_margin = buffer_meters / (111_320 * max(math.cos(mean_lat), 0.1))

    left = min(lon_values) - lon_margin
    bottom = min(lat_values) - lat_margin
    right = max(lon_values) + lon_margin
    top = max(lat_values) + lat_margin
    return left, bottom, right, top


def lonlat_to_mercator(lon: float, lat: float) -> tuple[float, float]:
    radius = 6_378_137.0
    x = radius * math.radians(lon)
    y = radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def project_polyline(polyline: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [lonlat_to_mercator(lon, lat) for lon, lat in polyline]


def haversine_distance_m(start: tuple[float, float], end: tuple[float, float]) -> float:
    start_lon, start_lat = start
    end_lon, end_lat = end
    radius = 6_371_000.0

    phi1 = math.radians(start_lat)
    phi2 = math.radians(end_lat)
    delta_phi = math.radians(end_lat - start_lat)
    delta_lambda = math.radians(end_lon - start_lon)
    haversine = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )

    return 2 * radius * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def cumulative_lonlat_distances(points_lonlat: list[tuple[float, float]]) -> list[float]:
    distances = [0.0]
    for start, end in zip(points_lonlat, points_lonlat[1:]):
        distances.append(distances[-1] + haversine_distance_m(start, end))
    return distances


def point_at_distance(
    points: list[tuple[float, float]],
    distances: list[float],
    target_distance: float,
) -> tuple[float, float]:
    if target_distance <= 0:
        return points[0]
    if target_distance >= distances[-1]:
        return points[-1]

    index = bisect.bisect_left(distances, target_distance)
    start_distance = distances[index - 1]
    end_distance = distances[index]
    ratio = (target_distance - start_distance) / max(end_distance - start_distance, 1e-9)
    start_x, start_y = points[index - 1]
    end_x, end_y = points[index]
    return (
        start_x + ratio * (end_x - start_x),
        start_y + ratio * (end_y - start_y),
    )


def map_bounds_for_points(
    world_points: list[tuple[float, float]],
    width: int,
    height: int,
    horizontal_padding_fraction: float = MAP_HORIZONTAL_PADDING_FRACTION,
    vertical_padding_fraction: float = MAP_VERTICAL_PADDING_FRACTION,
) -> tuple[float, float, float, float]:
    min_x = min(point[0] for point in world_points)
    max_x = max(point[0] for point in world_points)
    min_y = min(point[1] for point in world_points)
    max_y = max(point[1] for point in world_points)

    world_width = max(max_x - min_x, 1.0)
    world_height = max(max_y - min_y, 1.0)
    min_x -= world_width * horizontal_padding_fraction
    max_x += world_width * horizontal_padding_fraction
    min_y -= world_height * vertical_padding_fraction
    max_y += world_height * vertical_padding_fraction

    world_width = max_x - min_x
    world_height = max_y - min_y
    target_aspect = width / height
    current_aspect = world_width / world_height

    if current_aspect < target_aspect:
        extra_width = world_height * target_aspect - world_width
        min_x -= extra_width / 2
        max_x += extra_width / 2
    else:
        extra_height = world_width / target_aspect - world_height
        min_y -= extra_height / 2
        max_y += extra_height / 2

    return min_x, min_y, max_x, max_y


def transform_from_bounds(bounds: tuple[float, float, float, float], width: int, height: int) -> Any:
    left, bottom, right, top = bounds
    world_width = max(right - left, 1.0)
    world_height = max(top - bottom, 1.0)

    def transform(point: tuple[float, float]) -> tuple[int, int]:
        x, y = point
        screen_x = (x - left) / world_width * width
        screen_y = height - (y - bottom) / world_height * height
        return int(round(screen_x)), int(round(screen_y))

    return transform


def crop_osm_image_to_bounds(
    image: Any,
    image_extent: tuple[float, float, float, float],
    target_bounds: tuple[float, float, float, float],
) -> Any:
    image_left, image_right, image_bottom, image_top = image_extent
    target_left, target_bottom, target_right, target_top = target_bounds
    image_height, image_width = image.shape[:2]

    col_left = int(max(0, math.floor((target_left - image_left) / (image_right - image_left) * image_width)))
    col_right = int(min(image_width, math.ceil((target_right - image_left) / (image_right - image_left) * image_width)))
    row_top = int(max(0, math.floor((image_top - target_top) / (image_top - image_bottom) * image_height)))
    row_bottom = int(min(image_height, math.ceil((image_top - target_bottom) / (image_top - image_bottom) * image_height)))

    return image[row_top:row_bottom, col_left:col_right, :3].copy()
