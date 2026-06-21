from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .basemap import load_or_download_basemap
from .cache import map_cache_path
from .config import (
    BACKGROUND_COLOR,
    BASE_DIR,
    DEFAULT_ACTIVE_ROUTE_COUNT,
    DISTRICT_COLORS,
    HEATMAP_ROUTE_ALPHA,
    HEATMAP_ROUTE_SHADOW_ALPHA,
    HEATMAP_ROUTE_WIDTH,
    MAX_ROUTE_WIDTH,
    MIN_ROUTE_WIDTH,
    ROAD_COLOR,
    ROUTE_ALPHA,
    ROUTE_COUNT_STEP,
    ROUTE_SECONDARY_ALPHA,
    ROUTE_SECONDARY_COLOR,
    ROUTE_SHADOW_ALPHA,
    ROUTE_SHADOW_COLOR,
    ROUTE_TWO_YEARS_ALPHA,
    ROUTE_TWO_YEARS_SHADOW_ALPHA,
    STATION_ALPHA,
    STATION_INACTIVE_ALPHA,
    TEXT_COLOR,
    WHITE,
)
from .data import darker_color, heatmap_color, route_district, value_bounds
from .geo import (
    cumulative_lonlat_distances,
    map_bounds_for_points,
    point_at_distance,
    project_polyline,
    transform_from_bounds,
)
from .models import RouteAnimation, Station
from .osm_network import background_edge_lonlat
from .ui import (
    HEATMAP_SCOPE_BUTTON_LABELS,
    draw_attribution,
    draw_heatmap_scope_panel,
    draw_heatmap_scope_selector,
    draw_info_panel,
    draw_menu_button,
    draw_pause_badge,
    draw_pause_button,
    draw_route_controls,
    draw_stage_badge,
    draw_toggle_stage_button,
    draw_weekday_weekend_panel,
    menu_button_rect,
    panel_width_for_window,
    pause_button_rect,
    heatmap_scope_selector_rect,
    route_filter_control_rect,
    route_count_control_rect,
    scale_px,
    scaled_font,
    split_adjustment_control_rect,
    split_heatmap_scope_selector_rects,
    toggle_stage_button_rect,
    ui_scale,
)


# Silnik animacji: przygotowanie warstw mapy + ruch rowerzystow.

Color = tuple[int, int, int]
StationScreenPoint = tuple[int, int, float, Color, Color]
SCALE_TICK_INTERVAL_KM = 0.5
MIN_MAP_VIEW_ZOOM = 1.0
MAX_MAP_VIEW_ZOOM = 6.0
MAP_ZOOM_STEP = 1.22
CONTEXT_AREA_FILL_COLOR = (46, 196, 182, 15)
CONTEXT_AREA_OUTLINE_COLOR = (79, 124, 120, 230)
CONTEXT_AREA_LINE_WIDTH = 1.8
CONTEXT_AREA_DASH_LENGTH = 10
CONTEXT_AREA_GAP_LENGTH = 7
CONTEXT_AREA_FILES = (
    ("City of London", BASE_DIR / "cache" / "city_of_london_2512.geojson"),
    ("Hyde Park", BASE_DIR / "cache" / "32ef910d891d107e6bff288b4eacaf8f0d03413c.json"),
)


ContextArea = tuple[str, tuple[tuple[tuple[float, float], ...], ...]]


def as_screen_polylines(polylines: list[list[tuple[float, float]]], transform: Any) -> list[list[tuple[int, int]]]:
    screen_polylines = []
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        world_polyline = project_polyline(polyline)
        screen_polylines.append([transform(point) for point in world_polyline])
    return screen_polylines


def geometry_outer_rings_lonlat(geometry: dict[str, Any]) -> list[tuple[tuple[float, float], ...]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if geometry_type == "Polygon":
        candidate_rings = [coordinates[0]] if coordinates else []
    elif geometry_type == "MultiPolygon":
        candidate_rings = [polygon[0] for polygon in coordinates if polygon]
    else:
        candidate_rings = []

    rings = []
    for ring in candidate_rings:
        points = []
        for coordinate in ring:
            if len(coordinate) < 2:
                continue
            points.append((float(coordinate[0]), float(coordinate[1])))
        if len(points) >= 3:
            rings.append(tuple(points))
    return rings


def context_area_geometry(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict):
            geometry = first_item.get("geojson") or first_item.get("geometry")
            return geometry if isinstance(geometry, dict) else None
    if not isinstance(data, dict):
        return None
    if "coordinates" in data and "type" in data:
        return data
    if isinstance(data.get("geometry"), dict):
        return data["geometry"]
    features = data.get("features")
    if isinstance(features, list) and features and isinstance(features[0], dict):
        geometry = features[0].get("geometry")
        return geometry if isinstance(geometry, dict) else None
    return None


@lru_cache(maxsize=1)
def load_context_areas() -> tuple[ContextArea, ...]:
    areas = []
    for area_name, area_path in CONTEXT_AREA_FILES:
        if not area_path.exists():
            continue
        try:
            geometry = context_area_geometry(json.loads(area_path.read_text()))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if geometry is None:
            continue
        rings = geometry_outer_rings_lonlat(geometry)
        if rings:
            areas.append((area_name, tuple(rings)))
    return tuple(areas)


def context_area_screen_rings(transform: Any) -> list[list[tuple[int, int]]]:
    screen_rings = []
    for _, rings in load_context_areas():
        for ring in rings:
            screen_ring = [transform(point) for point in project_polyline(list(ring))]
            if len(screen_ring) >= 3:
                screen_rings.append(screen_ring)
    return screen_rings


def draw_dashed_line(
    pygame: Any,
    surface: Any,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int, int],
    width: int,
    dash_length: int,
    gap_length: int,
) -> None:
    start_x, start_y = start
    end_x, end_y = end
    segment_x = end_x - start_x
    segment_y = end_y - start_y
    segment_length = math.hypot(segment_x, segment_y)
    if segment_length <= 0:
        return

    unit_x = segment_x / segment_length
    unit_y = segment_y / segment_length
    step = max(1, dash_length + gap_length)
    distance = 0.0
    while distance < segment_length:
        dash_end = min(distance + dash_length, segment_length)
        dash_start_point = (
            int(round(start_x + unit_x * distance)),
            int(round(start_y + unit_y * distance)),
        )
        dash_end_point = (
            int(round(start_x + unit_x * dash_end)),
            int(round(start_y + unit_y * dash_end)),
        )
        pygame.draw.line(surface, color, dash_start_point, dash_end_point, width)
        distance += step


def draw_dashed_polygon_outline(
    pygame: Any,
    surface: Any,
    points: list[tuple[int, int]],
    color: tuple[int, int, int, int],
    width: int,
    dash_length: int,
    gap_length: int,
) -> None:
    if len(points) < 3:
        return
    closed_points = points + [points[0]]
    for start, end in zip(closed_points, closed_points[1:]):
        draw_dashed_line(pygame, surface, start, end, color, width, dash_length, gap_length)


def draw_context_area_fills(pygame: Any, surface: Any, screen_rings: list[list[tuple[int, int]]]) -> None:
    if not screen_rings:
        return
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 0))
    for points in screen_rings:
        pygame.draw.polygon(overlay, CONTEXT_AREA_FILL_COLOR, points)
    surface.blit(overlay, (0, 0))


def draw_context_area_boundaries(
    pygame: Any,
    surface: Any,
    screen_rings: list[list[tuple[int, int]]],
    scale: float,
) -> None:
    if not screen_rings:
        return
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 0))
    line_width = max(1, int(round(CONTEXT_AREA_LINE_WIDTH * scale)))
    dash_length = scale_px(CONTEXT_AREA_DASH_LENGTH, scale, 7)
    gap_length = scale_px(CONTEXT_AREA_GAP_LENGTH, scale, 5)
    for points in screen_rings:
        draw_dashed_polygon_outline(
            pygame,
            overlay,
            points,
            CONTEXT_AREA_OUTLINE_COLOR,
            line_width,
            dash_length,
            gap_length,
        )
    surface.blit(overlay, (0, 0))


def score_bounds(station_screen: list[StationScreenPoint]) -> tuple[float, float]:
    if not station_screen:
        return 0.0, 1.0
    scores = [max(0.0, float(point[2])) for point in station_screen]
    min_score = min(scores)
    max_score = max(scores)
    if max_score <= min_score:
        max_score = min_score + 1.0
    return min_score, max_score


def radius_from_score(score: float, min_score: float, max_score: float, min_radius: int, max_radius: int) -> int:
    low = math.log1p(max(0.0, min_score))
    high = math.log1p(max(0.0, max_score))
    value = math.log1p(max(0.0, score))
    if high <= low:
        return min_radius
    normalized = (value - low) / (high - low)
    normalized = max(0.0, min(1.0, normalized))
    radius = min_radius + normalized * (max_radius - min_radius)
    return int(round(radius))


def draw_stations(
    pygame: Any,
    screen: Any,
    active_station_screen: list[StationScreenPoint],
    inactive_station_screen: list[StationScreenPoint],
    scale: float = 1.0,
) -> None:
    min_score, max_score = score_bounds(active_station_screen + inactive_station_screen)

    if inactive_station_screen:
        inactive_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        inactive_layer.fill((0, 0, 0, 0))
        for x, y, station_score, fill_color, outline_color in inactive_station_screen:
            station_radius = radius_from_score(
                station_score,
                min_score,
                max_score,
                scale_px(2, scale, 2),
                scale_px(8, scale, 5),
            )

            point = (x, y)
            pygame.draw.circle(inactive_layer, (*fill_color, STATION_INACTIVE_ALPHA), point, station_radius)
            pygame.draw.circle(
                inactive_layer,
                (*outline_color, min(255, STATION_INACTIVE_ALPHA + 35)),
                point,
                station_radius,
                scale_px(1, scale, 1),
            )
        screen.blit(inactive_layer, (0, 0))

    if not active_station_screen:
        return

    active_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    active_layer.fill((0, 0, 0, 0))
    for x, y, station_score, fill_color, outline_color in active_station_screen:
        station_radius = radius_from_score(
            station_score,
            min_score,
            max_score,
            scale_px(3, scale, 2),
            scale_px(11, scale, 7),
        )

        point = (x, y)
        pygame.draw.circle(active_layer, (*WHITE, 190), point, station_radius + scale_px(1, scale, 1))
        pygame.draw.circle(active_layer, (*fill_color, STATION_ALPHA), point, station_radius)
        pygame.draw.circle(
            active_layer,
            (*outline_color, min(255, STATION_ALPHA + 35)),
            point,
            station_radius,
            scale_px(1, scale, 1),
        )
    screen.blit(active_layer, (0, 0))


def prepare_routes(routes: list[RouteAnimation], transform: Any, speed_mps: float) -> list[dict[str, Any]]:
    prepared_routes = []
    for route_index, route in enumerate(routes):
        world = project_polyline(route.points_lonlat)
        distances = cumulative_lonlat_distances(route.points_lonlat)
        total_distance_m = distances[-1]
        simulated_trip_seconds = total_distance_m / max(speed_mps, 1e-9)
        prepared_routes.append(
            {
                "route": route,
                "world": world,
                "screen": [transform(point) for point in world],
                "distances": distances,
                "total_distance_m": total_distance_m,
                "phase_seconds": route_index * simulated_trip_seconds * 0.38,
            }
        )
    return prepared_routes


def draw_cyclists(
    pygame: Any,
    screen: Any,
    transform: Any,
    prepared_routes: list[dict[str, Any]],
    simulated_seconds: float,
    speed_mps: float,
    scale: float = 1.0,
    marker_scale: float = 1.0,
) -> None:
    cyclist_scale = scale * marker_scale

    ordered_routes = sorted(
        prepared_routes,
        key=lambda prepared_route: prepared_route["route"].station_network_weight,
    )
    for prepared_route in ordered_routes:
        route = prepared_route["route"]
        total_distance_m = prepared_route["total_distance_m"]
        simulated_trip_seconds = total_distance_m / max(speed_mps, 1e-9)
        loop_seconds = simulated_trip_seconds + 3.0
        loop_position = (simulated_seconds + prepared_route["phase_seconds"]) % loop_seconds
        current_distance = min(loop_position * speed_mps, total_distance_m)
        cyclist_world = point_at_distance(prepared_route["world"], prepared_route["distances"], current_distance)
        cyclist_screen = transform(cyclist_world)
        pygame.draw.circle(screen, WHITE, cyclist_screen, scale_px(7, cyclist_scale, 5))
        pygame.draw.circle(screen, route.bike_color, cyclist_screen, scale_px(4, cyclist_scale, 3))
        pygame.draw.circle(screen, WHITE, cyclist_screen, scale_px(2, cyclist_scale, 1))


def clamp_map_view_center(
    map_width: int,
    height: int,
    zoom: float,
    center: tuple[float, float],
) -> tuple[float, float]:
    half_width = map_width / (2 * zoom)
    half_height = height / (2 * zoom)
    min_x = half_width
    max_x = map_width - half_width
    min_y = half_height
    max_y = height - half_height
    return (
        max(min_x, min(max_x, center[0])),
        max(min_y, min(max_y, center[1])),
    )


def map_source_rect(
    pygame: Any,
    map_width: int,
    height: int,
    zoom: float,
    center: tuple[float, float],
) -> Any:
    source_width = max(1, min(map_width, int(round(map_width / zoom))))
    source_height = max(1, min(height, int(round(height / zoom))))
    left = int(round(center[0] - source_width / 2))
    top = int(round(center[1] - source_height / 2))
    left = max(0, min(map_width - source_width, left))
    top = max(0, min(height - source_height, top))
    return pygame.Rect(left, top, source_width, source_height)


def zoom_map_view_at(
    map_width: int,
    height: int,
    zoom: float,
    center: tuple[float, float],
    cursor: tuple[int, int],
    factor: float,
) -> tuple[float, tuple[float, float]]:
    next_zoom = max(MIN_MAP_VIEW_ZOOM, min(MAX_MAP_VIEW_ZOOM, zoom * factor))
    if math.isclose(next_zoom, zoom, rel_tol=1e-4):
        return zoom, center

    old_left = center[0] - map_width / (2 * zoom)
    old_top = center[1] - height / (2 * zoom)
    focus_x = old_left + cursor[0] / zoom
    focus_y = old_top + cursor[1] / zoom

    next_left = focus_x - cursor[0] / next_zoom
    next_top = focus_y - cursor[1] / next_zoom
    next_center = (
        next_left + map_width / (2 * next_zoom),
        next_top + height / (2 * next_zoom),
    )
    return next_zoom, clamp_map_view_center(map_width, height, next_zoom, next_center)


def render_map_view(
    pygame: Any,
    static_map: Any,
    source_rect: Any,
    map_width: int,
    height: int,
    source_scale_x: float = 1.0,
    source_scale_y: float = 1.0,
) -> Any:
    if (
        math.isclose(source_scale_x, 1.0)
        and math.isclose(source_scale_y, 1.0)
        and source_rect.topleft == (0, 0)
        and source_rect.size == (map_width, height)
    ):
        return static_map

    view = pygame.Surface((map_width, height)).convert()
    view.fill(BACKGROUND_COLOR)
    scaled_rect = pygame.Rect(
        int(round(source_rect.x * source_scale_x)),
        int(round(source_rect.y * source_scale_y)),
        max(1, int(round(source_rect.width * source_scale_x))),
        max(1, int(round(source_rect.height * source_scale_y))),
    )
    scaled_rect.width = min(static_map.get_width() - scaled_rect.x, scaled_rect.width)
    scaled_rect.height = min(static_map.get_height() - scaled_rect.y, scaled_rect.height)
    if scaled_rect.width <= 0 or scaled_rect.height <= 0:
        return view

    view.blit(pygame.transform.smoothscale(static_map.subsurface(scaled_rect), (map_width, height)), (0, 0))
    return view


def viewport_transformer(
    base_transform: Any,
    source_rect: Any,
    map_width: int,
    height: int,
) -> tuple[Any, float]:
    view_scale_x = map_width / max(source_rect.width, 1)
    view_scale_y = height / max(source_rect.height, 1)

    def transform(point: tuple[float, float]) -> tuple[int, int]:
        x, y = base_transform(point)
        return (
            int(round((x - source_rect.x) * view_scale_x)),
            int(round((y - source_rect.y) * view_scale_y)),
        )

    return transform, view_scale_x


def mercator_latitude_from_y(y: float) -> float:
    radius = 6_378_137.0
    return math.degrees(math.atan(math.sinh(y / radius)))


def scale_bar_pixel_length(
    map_bounds: tuple[float, float, float, float],
    map_width: int,
    view_scale: float = 1.0,
) -> int:
    left, bottom, right, top = map_bounds
    center_lat = mercator_latitude_from_y((bottom + top) / 2)
    projected_meters_per_pixel = (right - left) / max(map_width * view_scale, 1)
    ground_meters_per_pixel = projected_meters_per_pixel * max(math.cos(math.radians(center_lat)), 0.1)
    return max(1, int(round(1000 / max(ground_meters_per_pixel, 1e-9))))


def draw_scale_bar(
    pygame: Any,
    screen: Any,
    font: Any,
    map_bounds: tuple[float, float, float, float],
    map_width: int,
    height: int,
    average_route_km: float | None = None,
    scale: float = 1.0,
    view_scale: float = 1.0,
) -> None:
    bar_width = scale_bar_pixel_length(map_bounds, map_width, view_scale)
    max_bar_width = map_width - scale_px(72, scale, 48)
    if bar_width > max_bar_width:
        return
    if average_route_km is None or average_route_km <= 0:
        return

    padding_x = scale_px(12, scale, 9)
    padding_y = scale_px(8, scale, 6)
    tick_height = scale_px(8, scale, 6)
    tick_label_gap = scale_px(5, scale, 4)
    margin_x = scale_px(42, scale, 30)
    bottom_margin = scale_px(46, scale, 34)
    average_label_image = font.render(f"Śr. trasa na mapie: {average_route_km:.2f} km", True, TEXT_COLOR)
    average_bar_width = int(round(bar_width * average_route_km))
    if average_bar_width > max_bar_width:
        average_bar_width = max_bar_width

    tick_sample_image = font.render("0,5 km", True, TEXT_COLOR)
    panel_width = max(average_bar_width, average_label_image.get_width(), tick_sample_image.get_width() * 4) + padding_x * 2
    panel_height = average_label_image.get_height() + tick_height * 2 + tick_label_gap + tick_sample_image.get_height() + padding_y * 3
    panel_x = min(margin_x, max(scale_px(8, scale, 4), map_width - panel_width - scale_px(8, scale, 4)))
    panel_y = max(scale_px(8, scale, 4), height - bottom_margin - panel_height)
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)

    panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    panel.fill((255, 255, 255, 215))
    pygame.draw.rect(
        panel,
        (180, 188, 194, 230),
        panel.get_rect(),
        scale_px(1, scale, 1),
        border_radius=scale_px(6, scale, 4),
    )

    average_label_x = (panel_width - average_label_image.get_width()) // 2
    panel.blit(average_label_image, (average_label_x, padding_y))
    bar_color = (35, 42, 50)
    line_width = scale_px(2, scale, 1)
    average_bar_x = (panel_width - average_bar_width) // 2
    average_bar_y = padding_y * 2 + average_label_image.get_height() + tick_height // 2
    draw_segmented_scale_line(
        pygame,
        panel,
        average_bar_x,
        average_bar_y,
        average_bar_width,
        average_route_km,
        tick_height,
        tick_label_gap,
        bar_color,
        line_width,
        font,
        scale,
    )

    screen.blit(panel, panel_rect.topleft)


def draw_segmented_scale_line(
    pygame: Any,
    panel: Any,
    bar_x: int,
    bar_y: int,
    bar_width: int,
    distance_km: float,
    tick_height: int,
    tick_label_gap: int,
    bar_color: tuple[int, int, int],
    line_width: int,
    font: Any,
    scale: float,
) -> None:
    pygame.draw.line(panel, bar_color, (bar_x, bar_y), (bar_x + bar_width, bar_y), line_width)
    tick_marks = scale_tick_marks(bar_width, distance_km)
    for tick_offset, _ in tick_marks:
        tick_x = bar_x + tick_offset
        pygame.draw.line(
            panel,
            bar_color,
            (tick_x, bar_y - tick_height),
            (tick_x, bar_y + tick_height),
            scale_px(1, scale, 1),
        )

    label_y = bar_y + tick_height + tick_label_gap
    min_label_gap = scale_px(8, scale, 6)
    selected_labels: list[tuple[int, int, Any]] = []
    for tick_index, (tick_offset, tick_distance_km) in enumerate(tick_marks):
        is_final_tick = tick_index == len(tick_marks) - 1
        label_text = format_scale_distance_label(tick_distance_km, include_unit=is_final_tick)
        label_image = font.render(label_text, True, bar_color)
        label_x = bar_x + tick_offset - label_image.get_width() // 2
        label_x = max(0, min(panel.get_width() - label_image.get_width(), label_x))
        label_right = label_x + label_image.get_width()

        if is_final_tick:
            while selected_labels and label_x < selected_labels[-1][1] + min_label_gap:
                selected_labels.pop()
            selected_labels.append((label_x, label_right, label_image))
        elif not selected_labels or label_x >= selected_labels[-1][1] + min_label_gap:
            selected_labels.append((label_x, label_right, label_image))

    for label_x, _, label_image in selected_labels:
        panel.blit(label_image, (label_x, label_y))


def format_scale_distance_label(distance_km: float, include_unit: bool = False) -> str:
    if include_unit:
        return f"{distance_km:.2f} km"

    rounded_distance = round(distance_km, 1)
    if math.isclose(rounded_distance, round(rounded_distance), abs_tol=0.01):
        label = f"{round(rounded_distance):.0f}"
    else:
        label = f"{rounded_distance:.1f}"
    return label


def scale_tick_marks(
    bar_width: int,
    distance_km: float,
    tick_interval_km: float = SCALE_TICK_INTERVAL_KM,
) -> list[tuple[int, float]]:
    if bar_width <= 0 or distance_km <= 0:
        return [(0, 0.0)]

    marks = []
    tick_count = int(math.floor(distance_km / tick_interval_km))
    for tick_index in range(tick_count + 1):
        tick_distance_km = tick_index * tick_interval_km
        marks.append((round(bar_width * tick_distance_km / distance_km), tick_distance_km))

    if marks[-1][0] != bar_width:
        marks.append((bar_width, distance_km))

    return marks


def average_prepared_route_km(prepared_routes: list[dict[str, Any]]) -> float:
    if not prepared_routes:
        return 0.0
    total_route_m = 0.0
    for prepared_route in prepared_routes:
        total_route_m += float(prepared_route["total_distance_m"])
    return total_route_m / 1000 / len(prepared_routes)


def station_layers(
    stations: list[Station],
    station_screen: list[tuple[int, int]],
    active_station_names: set[str],
    score_lookup: dict[str, float] | None,
    color_mode: str = "district",
) -> tuple[list[StationScreenPoint], list[StationScreenPoint]]:
    active = []
    inactive = []
    color_min = 0.0
    color_max = 1.0
    if color_mode == "heatmap":
        station_scores = []
        for station in stations:
            score = 0.0
            if score_lookup is not None:
                score = float(score_lookup.get(station.name, 0.0))
            station_scores.append(score if score > 0 else 0.05)
        color_min, color_max = value_bounds(station_scores)

    for station, point in zip(stations, station_screen):
        score = 1.0
        if score_lookup is not None:
            score = float(score_lookup.get(station.name, 0.0))
            if score <= 0:
                score = 0.05
        if color_mode == "heatmap":
            fill_color = heatmap_color(score, color_min, color_max)
            outline_color = darker_color(fill_color)
        else:
            fill_color, outline_color = DISTRICT_COLORS.get(route_district([station]), DISTRICT_COLORS["Centrum"])
        entry = (point[0], point[1], score, fill_color, outline_color)
        if station.name in active_station_names:
            active.append(entry)
        else:
            inactive.append(entry)
    return active, inactive


def build_base_map(
    ctx: Any,
    pygame: Any,
    graph: Any | None,
    cache_dir: Path,
    refresh_map: bool,
    map_zoom: int | None,
    map_width: int,
    height: int,
    map_bounds: tuple[float, float, float, float],
    transform: Any,
    scale: float = 1.0,
) -> Any:
    basemap_surface = load_or_download_basemap(
        ctx=ctx,
        pygame=pygame,
        cache_path=map_cache_path(cache_dir, map_bounds, map_width, height, map_zoom),
        bounds=map_bounds,
        width=map_width,
        height=height,
        zoom=map_zoom,
        refresh_map=refresh_map,
    )

    surface = pygame.Surface((map_width, height)).convert()
    surface.fill(BACKGROUND_COLOR)
    if basemap_surface is not None:
        surface.blit(basemap_surface, (0, 0))
        soft_overlay = pygame.Surface((map_width, height), pygame.SRCALPHA)
        soft_overlay.fill((255, 255, 255, 20))
        surface.blit(soft_overlay, (0, 0))

    context_screen_rings = context_area_screen_rings(transform)
    draw_context_area_fills(pygame, surface, context_screen_rings)

    if graph is not None:
        road_width = max(scale_px(1, scale, 1), 2 if map_width >= 1400 else 1)
        for polyline in as_screen_polylines(background_edge_lonlat(graph), transform):
            if len(polyline) >= 2:
                pygame.draw.lines(surface, ROAD_COLOR, False, polyline, road_width)

    draw_context_area_boundaries(pygame, surface, context_screen_rings, scale)
    return surface


def static_render_dimensions(width: int, height: int, render_scale: float) -> tuple[int, int, float]:
    quality_scale = max(1.0, float(render_scale))
    render_width = max(width, int(round(width * quality_scale)))
    render_height = max(height, int(round(height * quality_scale)))
    return render_width, render_height, quality_scale


def downscale_static_scene(pygame: Any, surface: Any, width: int, height: int) -> Any:
    if surface.get_size() == (width, height):
        return surface
    return pygame.transform.smoothscale(surface, (width, height)).convert()


def draw_routes_layer(
    pygame: Any,
    map_width: int,
    height: int,
    prepared_routes: list[dict[str, Any]],
    *,
    alpha: int = ROUTE_ALPHA,
    use_shadow: bool = True,
    fixed_color: tuple[int, int, int] | None = None,
    width_override: int | None = None,
    shadow_alpha: int = ROUTE_SHADOW_ALPHA,
    scale: float = 1.0,
    transform: Any | None = None,
) -> Any:
    base_route_width = width_override if width_override is not None else (2 if len(prepared_routes) > 80 else 3)
    route_width = scale_px(base_route_width, scale, 2)
    route_layer = pygame.Surface((map_width, height), pygame.SRCALPHA)
    route_layer.fill((0, 0, 0, 0))
    shadow_color = (*ROUTE_SHADOW_COLOR, shadow_alpha)

    for prepared_route in prepared_routes:
        route = prepared_route["route"]
        if transform is None:
            screen_points = prepared_route["screen"]
        else:
            screen_points = [transform(point) for point in prepared_route["world"]]
        if len(screen_points) < 2:
            continue
        base_color = fixed_color if fixed_color is not None else route.route_color
        route_color = (*base_color, alpha)
        if use_shadow:
            pygame.draw.lines(route_layer, shadow_color, False, screen_points, route_width + scale_px(2, scale, 1))
        pygame.draw.lines(route_layer, route_color, False, screen_points, route_width)
    return route_layer


def compose_static_route_scene(
    pygame: Any,
    base_map: Any,
    map_width: int,
    height: int,
    prepared_routes: list[dict[str, Any]],
    active_route_count: int,
    route_alpha: int,
    route_shadow_alpha: int,
    route_width: int,
    active_station_screen: list[StationScreenPoint],
    inactive_station_screen: list[StationScreenPoint],
    scale: float,
) -> Any:
    scene = pygame.Surface(base_map.get_size()).convert()
    scene.fill(BACKGROUND_COLOR)
    scene.blit(base_map, (0, 0))
    active_route_count = max(0, min(active_route_count, len(prepared_routes)))
    muted_routes = prepared_routes[active_route_count:]
    active_routes = prepared_routes[:active_route_count]

    if muted_routes:
        scene.blit(
            draw_routes_layer(
                pygame,
                map_width,
                height,
                muted_routes,
                alpha=max(18, route_alpha // 7),
                use_shadow=False,
                width_override=max(MIN_ROUTE_WIDTH, route_width - 2),
                scale=scale,
            ),
            (0, 0),
        )

    if active_routes:
        scene.blit(
            draw_routes_layer(
                pygame,
                map_width,
                height,
                active_routes,
                alpha=route_alpha,
                shadow_alpha=route_shadow_alpha,
                width_override=route_width,
                scale=scale,
            ),
            (0, 0),
        )

    draw_stations(
        pygame,
        scene,
        active_station_screen=active_station_screen,
        inactive_station_screen=inactive_station_screen,
        scale=scale,
    )
    return scene


def run_animation(
    ctx: Any,
    pygame: Any,
    screen: Any,
    graph: Any | None,
    stations: list[Station],
    routes: list[RouteAnimation],
    speed_kmh: float,
    time_scale: float,
    width: int,
    height: int,
    cache_dir: Path,
    refresh_map: bool,
    map_zoom: int | None,
    all_stations: list[Station] | None = None,
    render_scale: float = 1.0,
    station_scores: dict[str, float] | None = None,
    color_mode: str = "district",
    max_real_seconds: float | None = None,
) -> str:
    pygame.display.set_caption("London bike route animation")
    clock = pygame.time.Clock()
    scale = ui_scale(width, height)
    panel_width = panel_width_for_window(width, scale)
    map_width = width - panel_width
    panel_x = map_width

    font = scaled_font(pygame, 18, scale, min_size=15)
    small_font = scaled_font(pygame, 15, scale, min_size=12)
    title_font = scaled_font(pygame, 24, scale, bold=True, min_size=20)

    display_station_lookup = {}
    for station in (all_stations or []) + stations:
        display_station_lookup[station.name] = station
    display_stations = list(display_station_lookup.values())

    station_points = [project_polyline([(station.lon, station.lat)])[0] for station in display_stations]
    all_route_points = [point for route in routes for point in project_polyline(route.points_lonlat)]
    map_bounds = map_bounds_for_points(all_route_points + station_points, map_width, height)
    transform = transform_from_bounds(map_bounds, map_width, height)
    render_map_width, render_height, quality_scale = static_render_dimensions(map_width, height, render_scale)
    static_transform = transform_from_bounds(map_bounds, render_map_width, render_height)

    static_station_screen = [static_transform(point) for point in station_points]
    active_station_names = {station.name for route in routes for station in route.stations}
    static_active_station_screen, static_inactive_station_screen = station_layers(
        display_stations,
        static_station_screen,
        active_station_names,
        station_scores,
        color_mode=color_mode,
    )

    speed_mps = speed_kmh / 3.6
    prepared_routes = prepare_routes(routes, transform, speed_mps)
    static_prepared_routes = prepare_routes(routes, static_transform, speed_mps)
    route_weights = [int(route.station_network_weight) for route in routes]
    min_route_weight = 0
    max_route_weight = max(route_weights) if route_weights else 0
    route_weight_threshold = 0
    route_filter_enabled = color_mode == "heatmap" and max_route_weight > 0
    route_layer_alpha = HEATMAP_ROUTE_ALPHA if color_mode == "heatmap" else ROUTE_TWO_YEARS_ALPHA
    route_shadow_alpha = HEATMAP_ROUTE_SHADOW_ALPHA if color_mode == "heatmap" else ROUTE_TWO_YEARS_SHADOW_ALPHA
    fixed_route_width = HEATMAP_ROUTE_WIDTH if color_mode == "heatmap" else (2 if len(routes) > 80 else 3)
    fixed_route_width = max(MIN_ROUTE_WIDTH, min(MAX_ROUTE_WIDTH, fixed_route_width))
    min_active_route_count = 1 if routes else 0
    max_active_route_count = len(routes)
    active_route_count = min(max_active_route_count, max(min_active_route_count, DEFAULT_ACTIVE_ROUTE_COUNT))

    static_base_map = build_base_map(
        ctx=ctx,
        pygame=pygame,
        graph=graph,
        cache_dir=cache_dir,
        refresh_map=refresh_map,
        map_zoom=map_zoom,
        map_width=render_map_width,
        height=render_height,
        map_bounds=map_bounds,
        transform=static_transform,
        scale=scale * quality_scale,
    )

    def filtered_prepared_routes(prepared: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not route_filter_enabled or route_weight_threshold <= 0:
            return prepared
        return [
            prepared_route
            for prepared_route in prepared
            if prepared_route["route"].station_network_weight >= route_weight_threshold
        ]

    def compose_visible_map() -> Any:
        visible_static_prepared_routes = filtered_prepared_routes(static_prepared_routes)
        visible_route_count = (
            len(visible_static_prepared_routes)
            if route_filter_enabled
            else active_route_count
        )
        return compose_static_route_scene(
            pygame,
            static_base_map,
            render_map_width,
            render_height,
            visible_static_prepared_routes,
            visible_route_count,
            route_layer_alpha,
            route_shadow_alpha,
            fixed_route_width,
            static_active_station_screen,
            static_inactive_station_screen,
            scale * quality_scale,
        )

    static_map_source = compose_visible_map()
    visible_static_map = downscale_static_scene(pygame, static_map_source, map_width, height)
    static_scene_dirty = False
    filter_dragging = False

    elapsed_real_seconds = 0.0
    route_simulated_seconds = 0.0
    panel_scroll = 0
    panel_scroll_max = 0
    mousewheel_event = getattr(pygame, "MOUSEWHEEL", None)
    paused = False
    exit_action = "quit"
    running = True

    def set_active_route_count(next_count: int) -> None:
        nonlocal active_route_count, static_scene_dirty
        current_max_route_count = (
            len(filtered_prepared_routes(prepared_routes))
            if route_filter_enabled
            else max_active_route_count
        )
        current_min_route_count = min_active_route_count if current_max_route_count > 0 else 0
        next_count = max(current_min_route_count, min(current_max_route_count, next_count))
        if next_count != active_route_count:
            active_route_count = next_count
            static_scene_dirty = True

    def set_route_weight_threshold_from_x(mouse_x: int) -> None:
        nonlocal route_weight_threshold, static_scene_dirty
        if not route_filter_enabled:
            return
        filter_rect = route_filter_control_rect(pygame, panel_x, panel_width, height, scale)
        padding_x = scale_px(14, scale, 10)
        track_left = filter_rect.x + padding_x
        track_right = filter_rect.right - padding_x
        fraction = (mouse_x - track_left) / max(track_right - track_left, 1)
        fraction = max(0.0, min(1.0, fraction))
        next_threshold = int(round(min_route_weight + (max_route_weight - min_route_weight) * fraction))
        if next_threshold != route_weight_threshold:
            route_weight_threshold = next_threshold
            static_scene_dirty = True

    while running:
        dt = clock.tick(60) / 1000
        elapsed_real_seconds += dt

        pause_button = pause_button_rect(pygame, panel_x, panel_width, height, scale)
        menu_button = menu_button_rect(pygame, panel_x, panel_width, height, scale)
        route_count_minus = route_count_plus = None
        if not route_filter_enabled:
            route_count_button = route_count_control_rect(pygame, panel_x, panel_width, height, scale)
            route_count_minus, _, route_count_plus = split_adjustment_control_rect(route_count_button, scale)
        route_filter_button = route_filter_control_rect(pygame, panel_x, panel_width, height, scale)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in {pygame.K_ESCAPE, pygame.K_q}:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                exit_action = "menu"
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                paused = not paused
            elif mousewheel_event is not None and event.type == mousewheel_event:
                mouse_x, _ = pygame.mouse.get_pos()
                if mouse_x >= panel_x:
                    panel_scroll -= event.y * scale_px(46, scale, 36)
                    panel_scroll = max(0, min(panel_scroll, panel_scroll_max))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in {4, 5}:
                if event.pos[0] >= panel_x:
                    direction = 1 if event.button == 4 else -1
                    panel_scroll -= direction * scale_px(46, scale, 36)
                    panel_scroll = max(0, min(panel_scroll, panel_scroll_max))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if route_filter_enabled and route_filter_button.collidepoint(event.pos):
                    filter_dragging = True
                    set_route_weight_threshold_from_x(event.pos[0])
                elif route_count_minus is not None and route_count_minus.collidepoint(event.pos):
                    set_active_route_count(active_route_count - ROUTE_COUNT_STEP)
                elif route_count_plus is not None and route_count_plus.collidepoint(event.pos):
                    set_active_route_count(active_route_count + ROUTE_COUNT_STEP)
                elif pause_button.collidepoint(event.pos):
                    paused = not paused
                elif menu_button.collidepoint(event.pos):
                    exit_action = "menu"
                    running = False
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                filter_dragging = False
            elif event.type == pygame.MOUSEMOTION and filter_dragging:
                set_route_weight_threshold_from_x(event.pos[0])

        if static_scene_dirty:
            static_map_source = compose_visible_map()
            visible_static_map = downscale_static_scene(pygame, static_map_source, map_width, height)
            static_scene_dirty = False

        if not paused:
            route_simulated_seconds += dt * time_scale
        simulated_seconds = route_simulated_seconds
        visible_prepared_routes = filtered_prepared_routes(prepared_routes)
        visible_active_route_count = (
            len(visible_prepared_routes)
            if route_filter_enabled
            else min(active_route_count, len(visible_prepared_routes))
        )

        screen.fill(BACKGROUND_COLOR)
        screen.blit(visible_static_map, (0, 0))
        draw_cyclists(
            pygame=pygame,
            screen=screen,
            transform=transform,
            prepared_routes=visible_prepared_routes[:visible_active_route_count],
            simulated_seconds=simulated_seconds,
            speed_mps=speed_mps,
            scale=scale,
        )
        draw_scale_bar(
            pygame,
            screen,
            small_font,
            map_bounds,
            map_width,
            height,
            average_route_km=average_prepared_route_km(prepared_routes),
            scale=scale,
        )
        panel_scroll_max = draw_info_panel(
            pygame=pygame,
            screen=screen,
            font=font,
            title_font=title_font,
            routes=routes,
            prepared_routes=prepared_routes,
            stations=display_stations,
            selected_station_count=len(stations),
            active_route_station_count=len(active_station_names),
            speed_kmh=speed_kmh,
            cyclist_count=visible_active_route_count,
            highlighted_route_count=None if route_filter_enabled else visible_active_route_count,
            filtered_route_count=len(visible_prepared_routes),
            route_weight_threshold=route_weight_threshold if route_filter_enabled else None,
            panel_x=panel_x,
            panel_width=panel_width,
            height=height,
            scroll=panel_scroll,
            scale=scale,
            color_mode=color_mode,
            station_scores=station_scores,
            show_route_filter=route_filter_enabled,
        )
        panel_scroll = min(panel_scroll, panel_scroll_max)
        draw_route_controls(
            pygame,
            screen,
            font,
            panel_x,
            panel_width,
            height,
            active_route_count,
            show_filter=route_filter_enabled,
            route_weight_threshold=route_weight_threshold,
            min_route_weight=min_route_weight,
            max_route_weight=max_route_weight,
            visible_route_count=len(visible_prepared_routes),
            total_route_count=len(routes),
            scale=scale,
        )
        draw_menu_button(pygame, screen, font, panel_x, panel_width, height, scale)
        draw_pause_button(pygame, screen, font, paused, panel_x, panel_width, height, scale)
        if paused:
            draw_pause_badge(pygame, screen, title_font, map_width, scale)
        draw_attribution(pygame, screen, small_font, map_width, height, scale)

        pygame.display.flip()
        if max_real_seconds is not None and elapsed_real_seconds >= max_real_seconds:
            running = False

    return exit_action


def run_heatmap_scope_animation(
    ctx: Any,
    pygame: Any,
    screen: Any,
    graph: Any | None,
    scopes: list[dict[str, Any]],
    all_stations: list[Station] | None,
    speed_kmh: float,
    time_scale: float,
    width: int,
    height: int,
    cache_dir: Path,
    refresh_map: bool,
    map_zoom: int | None,
    render_scale: float = 1.0,
    max_real_seconds: float | None = None,
) -> str:
    pygame.display.set_caption("London bike route animation")
    clock = pygame.time.Clock()
    scale = ui_scale(width, height)
    panel_width = panel_width_for_window(width, scale)
    map_width = width - panel_width
    panel_x = map_width

    font = scaled_font(pygame, 18, scale, min_size=15)
    small_font = scaled_font(pygame, 15, scale, min_size=12)
    title_font = scaled_font(pygame, 24, scale, bold=True, min_size=20)

    scope_lookup = {scope["key"]: scope for scope in scopes}
    scope_order = [scope["key"] for scope in scopes]
    if not scope_order:
        raise ValueError("At least one heatmap scope is required.")

    station_lookup = {}
    for station in all_stations or []:
        station_lookup[station.name] = station
    for scope in scopes:
        for station in scope["stations"]:
            station_lookup[station.name] = station
    stations = list(station_lookup.values())

    station_points = [project_polyline([(station.lon, station.lat)])[0] for station in stations]
    all_route_points = [
        point
        for scope in scopes
        for route in scope["routes"]
        for point in project_polyline(route.points_lonlat)
    ]
    map_bounds = map_bounds_for_points(all_route_points + station_points, map_width, height)
    transform = transform_from_bounds(map_bounds, map_width, height)
    render_map_width, render_height, quality_scale = static_render_dimensions(map_width, height, render_scale)
    static_transform = transform_from_bounds(map_bounds, render_map_width, render_height)
    static_station_screen = [static_transform(point) for point in station_points]

    speed_mps = speed_kmh / 3.6
    scope_render_data: dict[str, dict[str, Any]] = {}
    for scope in scopes:
        scope_key = scope["key"]
        routes = scope["routes"]
        active_station_names = {station.name for route in routes for station in route.stations}
        active_screen, inactive_screen = station_layers(
            stations,
            static_station_screen,
            active_station_names,
            scope.get("station_scores"),
            color_mode="heatmap",
        )
        scope_render_data[scope_key] = {
            "prepared": prepare_routes(routes, transform, speed_mps),
            "static_prepared": prepare_routes(routes, static_transform, speed_mps),
            "active_screen": active_screen,
            "inactive_screen": inactive_screen,
            "max_route_weight": max((int(route.station_network_weight) for route in routes), default=0),
        }

    base_map = build_base_map(
        ctx=ctx,
        pygame=pygame,
        graph=graph,
        cache_dir=cache_dir,
        refresh_map=refresh_map,
        map_zoom=map_zoom,
        map_width=render_map_width,
        height=render_height,
        map_bounds=map_bounds,
        transform=static_transform,
        scale=scale * quality_scale,
    )

    min_route_weight = 0
    max_route_weight = max(data["max_route_weight"] for data in scope_render_data.values())
    route_weight_threshold_fraction = 0.0
    route_filter_enabled = max_route_weight > 0
    scenes: dict[str, Any] = {}

    def route_threshold_for_scope(scope_key: str) -> int:
        scope_max_weight = scope_render_data[scope_key]["max_route_weight"]
        return int(round(min_route_weight + (scope_max_weight - min_route_weight) * route_weight_threshold_fraction))

    def filtered_prepared_routes(
        prepared: list[dict[str, Any]],
        threshold: int,
    ) -> list[dict[str, Any]]:
        if threshold <= 0:
            return prepared
        return [
            prepared_route
            for prepared_route in prepared
            if prepared_route["route"].station_network_weight >= threshold
        ]

    def compose_scope_scene(scope_key: str) -> Any:
        render_data = scope_render_data[scope_key]
        visible_static_routes = filtered_prepared_routes(
            render_data["static_prepared"],
            route_threshold_for_scope(scope_key),
        )
        scene = pygame.Surface((render_map_width, render_height)).convert()
        scene.fill(BACKGROUND_COLOR)
        scene.blit(base_map, (0, 0))
        scene.blit(
            draw_routes_layer(
                pygame,
                render_map_width,
                render_height,
                visible_static_routes,
                alpha=HEATMAP_ROUTE_ALPHA,
                shadow_alpha=HEATMAP_ROUTE_SHADOW_ALPHA,
                width_override=HEATMAP_ROUTE_WIDTH,
                scale=scale * quality_scale,
            ),
            (0, 0),
        )
        draw_stations(
            pygame,
            scene,
            active_station_screen=render_data["active_screen"],
            inactive_station_screen=render_data["inactive_screen"],
            scale=scale * quality_scale,
        )
        return downscale_static_scene(pygame, scene, map_width, height)

    for scope_key in scope_order:
        scenes[scope_key] = compose_scope_scene(scope_key)

    active_scope_key = scope_order[0]
    static_scenes_dirty: set[str] = set()
    filter_dragging = False
    elapsed_real_seconds = 0.0
    animation_real_seconds = 0.0
    panel_scroll = 0
    panel_scroll_max = 0
    mousewheel_event = getattr(pygame, "MOUSEWHEEL", None)
    paused = False
    exit_action = "quit"
    running = True

    scope_options = [
        (
            scope["key"],
            scope.get("button_label", HEATMAP_SCOPE_BUTTON_LABELS.get(scope["key"], scope["label"])),
        )
        for scope in scopes
    ]

    def active_threshold() -> int:
        return route_threshold_for_scope(active_scope_key)

    def active_max_route_weight() -> int:
        return scope_render_data[active_scope_key]["max_route_weight"]

    def set_active_route_weight_threshold_from_x(mouse_x: int) -> None:
        nonlocal route_weight_threshold_fraction
        if not route_filter_enabled:
            return

        filter_rect = route_filter_control_rect(
            pygame,
            panel_x,
            panel_width,
            height,
            scale,
            index_from_bottom=4,
        )
        padding_x = scale_px(14, scale, 10)
        track_left = filter_rect.x + padding_x
        track_right = filter_rect.right - padding_x
        next_fraction = (mouse_x - track_left) / max(track_right - track_left, 1)
        next_fraction = max(0.0, min(1.0, next_fraction))

        if not math.isclose(next_fraction, route_weight_threshold_fraction, rel_tol=0.0, abs_tol=1e-4):
            route_weight_threshold_fraction = next_fraction
            static_scenes_dirty.update(scope_order)

    def select_scope_from_position(position: tuple[int, int]) -> bool:
        nonlocal active_scope_key, panel_scroll
        selector = heatmap_scope_selector_rect(pygame, panel_x, panel_width, height, scale)
        if not selector.collidepoint(position):
            return False

        for (scope_key, _), scope_rect in zip(
            scope_options,
            split_heatmap_scope_selector_rects(selector, len(scope_options), scale),
        ):
            if scope_rect.collidepoint(position):
                active_scope_key = scope_key
                panel_scroll = 0
                return True
        return False

    while running:
        dt = clock.tick(60) / 1000
        elapsed_real_seconds += dt

        pause_button = pause_button_rect(pygame, panel_x, panel_width, height, scale)
        menu_button = menu_button_rect(pygame, panel_x, panel_width, height, scale)
        route_filter_button = route_filter_control_rect(
            pygame,
            panel_x,
            panel_width,
            height,
            scale,
            index_from_bottom=4,
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in {pygame.K_ESCAPE, pygame.K_q}:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                exit_action = "menu"
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                paused = not paused
            elif event.type == pygame.KEYDOWN and event.key in {pygame.K_TAB, pygame.K_t}:
                active_index = scope_order.index(active_scope_key)
                active_scope_key = scope_order[(active_index + 1) % len(scope_order)]
                panel_scroll = 0
            elif mousewheel_event is not None and event.type == mousewheel_event:
                mouse_x, _ = pygame.mouse.get_pos()
                if mouse_x >= panel_x:
                    panel_scroll -= event.y * scale_px(46, scale, 36)
                    panel_scroll = max(0, min(panel_scroll, panel_scroll_max))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in {4, 5}:
                if event.pos[0] >= panel_x:
                    direction = 1 if event.button == 4 else -1
                    panel_scroll -= direction * scale_px(46, scale, 36)
                    panel_scroll = max(0, min(panel_scroll, panel_scroll_max))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if route_filter_enabled and route_filter_button.collidepoint(event.pos):
                    filter_dragging = True
                    set_active_route_weight_threshold_from_x(event.pos[0])
                elif select_scope_from_position(event.pos):
                    filter_dragging = False
                elif pause_button.collidepoint(event.pos):
                    paused = not paused
                elif menu_button.collidepoint(event.pos):
                    exit_action = "menu"
                    running = False
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                filter_dragging = False
            elif event.type == pygame.MOUSEMOTION and filter_dragging:
                set_active_route_weight_threshold_from_x(event.pos[0])

        if not paused:
            animation_real_seconds += dt

        if static_scenes_dirty:
            for scope_key in list(static_scenes_dirty):
                scenes[scope_key] = compose_scope_scene(scope_key)
            static_scenes_dirty.clear()

        active_scope = scope_lookup[active_scope_key]
        active_render_data = scope_render_data[active_scope_key]
        active_threshold_value = active_threshold()
        prepared_routes = filtered_prepared_routes(
            active_render_data["prepared"],
            active_threshold_value,
        )
        active_routes = active_scope["routes"]
        active_max_weight = active_max_route_weight()
        simulated_seconds = animation_real_seconds * time_scale

        screen.fill(BACKGROUND_COLOR)
        screen.blit(scenes[active_scope_key], (0, 0))
        draw_cyclists(
            pygame=pygame,
            screen=screen,
            transform=transform,
            prepared_routes=prepared_routes,
            simulated_seconds=simulated_seconds,
            speed_mps=speed_mps,
            scale=scale,
        )
        draw_scale_bar(
            pygame,
            screen,
            small_font,
            map_bounds,
            map_width,
            height,
            average_route_km=average_prepared_route_km(prepared_routes),
            scale=scale,
        )

        panel_scroll_max = draw_heatmap_scope_panel(
            pygame=pygame,
            screen=screen,
            font=font,
            title_font=title_font,
            active_scope_label=active_scope["label"],
            active_stations_label=active_scope.get("stations_label", "Stacje do tras"),
            routes_label=active_scope.get("routes_label", "Trasy"),
            active_routes=active_routes,
            prepared_routes=active_render_data["prepared"],
            active_stations=active_scope["stations"],
            map_station_count=len(stations),
            map_stations=stations,
            station_scores=active_scope.get("station_scores"),
            speed_kmh=speed_kmh,
            cyclist_count=len(prepared_routes),
            filtered_route_count=len(prepared_routes),
            route_weight_threshold=active_threshold_value if route_filter_enabled else None,
            show_route_filter=route_filter_enabled,
            panel_x=panel_x,
            panel_width=panel_width,
            height=height,
            scroll=panel_scroll,
            scale=scale,
        )
        panel_scroll = min(panel_scroll, panel_scroll_max)

        if route_filter_enabled:
            draw_route_controls(
                pygame,
                screen,
                font,
                panel_x,
                panel_width,
                height,
                len(prepared_routes),
                show_filter=True,
                route_weight_threshold=active_threshold_value,
                min_route_weight=min_route_weight,
                max_route_weight=active_max_weight,
                visible_route_count=len(prepared_routes),
                total_route_count=len(active_routes),
                scale=scale,
                filter_index_from_bottom=4,
            )
        draw_heatmap_scope_selector(
            pygame,
            screen,
            font,
            panel_x,
            panel_width,
            height,
            scope_options,
            active_scope_key,
            scale,
        )
        draw_menu_button(pygame, screen, font, panel_x, panel_width, height, scale)
        draw_pause_button(pygame, screen, font, paused, panel_x, panel_width, height, scale)
        stage_badge_text = active_scope["label"]
        if paused:
            stage_badge_text = f"{stage_badge_text}  |  PAUZA"
        draw_stage_badge(pygame, screen, title_font, map_width, stage_badge_text, scale)
        draw_attribution(pygame, screen, small_font, map_width, height, scale)

        pygame.display.flip()
        if max_real_seconds is not None and elapsed_real_seconds >= max_real_seconds:
            running = False

    return exit_action


def run_weekday_weekend_animation(
    ctx: Any,
    pygame: Any,
    screen: Any,
    graph: Any | None,
    weekday_stations: list[Station],
    weekend_stations: list[Station],
    weekday_routes: list[RouteAnimation],
    weekend_routes: list[RouteAnimation],
    all_stations: list[Station] | None,
    speed_kmh: float,
    time_scale: float,
    width: int,
    height: int,
    cache_dir: Path,
    refresh_map: bool,
    map_zoom: int | None,
    weekday_station_scores: dict[str, float],
    weekend_station_scores: dict[str, float],
    render_scale: float = 1.0,
    max_real_seconds: float | None = None,
) -> str:
    pygame.display.set_caption("London bike route animation")
    clock = pygame.time.Clock()
    scale = ui_scale(width, height)
    panel_width = panel_width_for_window(width, scale)
    map_width = width - panel_width
    panel_x = map_width

    font = scaled_font(pygame, 18, scale, min_size=15)
    small_font = scaled_font(pygame, 15, scale, min_size=12)
    title_font = scaled_font(pygame, 24, scale, bold=True, min_size=20)

    station_lookup = {}
    for station in (all_stations or []) + weekday_stations + weekend_stations:
        station_lookup[station.name] = station
    stations = list(station_lookup.values())
    station_points = [project_polyline([(station.lon, station.lat)])[0] for station in stations]
    all_route_points = [
        point for route in (weekday_routes + weekend_routes) for point in project_polyline(route.points_lonlat)
    ]
    map_bounds = map_bounds_for_points(all_route_points + station_points, map_width, height)
    transform = transform_from_bounds(map_bounds, map_width, height)
    render_map_width, render_height, quality_scale = static_render_dimensions(map_width, height, render_scale)
    static_transform = transform_from_bounds(map_bounds, render_map_width, render_height)
    static_station_screen = [static_transform(point) for point in station_points]

    weekday_active_station_names = {station.name for route in weekday_routes for station in route.stations}
    weekend_active_station_names = {station.name for route in weekend_routes for station in route.stations}

    weekday_active_screen, weekday_inactive_screen = station_layers(
        stations,
        static_station_screen,
        weekday_active_station_names,
        weekday_station_scores,
        color_mode="heatmap",
    )
    weekend_active_screen, weekend_inactive_screen = station_layers(
        stations,
        static_station_screen,
        weekend_active_station_names,
        weekend_station_scores,
        color_mode="heatmap",
    )

    speed_mps = speed_kmh / 3.6
    prepared_weekday = prepare_routes(weekday_routes, transform, speed_mps)
    prepared_weekend = prepare_routes(weekend_routes, transform, speed_mps)
    static_prepared_weekday = prepare_routes(weekday_routes, static_transform, speed_mps)
    static_prepared_weekend = prepare_routes(weekend_routes, static_transform, speed_mps)

    base_map = build_base_map(
        ctx=ctx,
        pygame=pygame,
        graph=graph,
        cache_dir=cache_dir,
        refresh_map=refresh_map,
        map_zoom=map_zoom,
        map_width=render_map_width,
        height=render_height,
        map_bounds=map_bounds,
        transform=static_transform,
        scale=scale * quality_scale,
    )

    min_route_weight = 0
    weekday_max_route_weight = max((int(route.station_network_weight) for route in weekday_routes), default=0)
    weekend_max_route_weight = max((int(route.station_network_weight) for route in weekend_routes), default=0)
    weekday_route_weight_threshold = 0
    weekend_route_weight_threshold = 0

    def filtered_prepared_routes(prepared: list[dict[str, Any]], threshold: int) -> list[dict[str, Any]]:
        if threshold <= 0:
            return prepared
        return [
            prepared_route
            for prepared_route in prepared
            if prepared_route["route"].station_network_weight >= threshold
        ]

    def compose_stage_scene(
        active_static_prepared: list[dict[str, Any]],
        secondary_static_prepared: list[dict[str, Any]],
        active_station_screen: list[StationScreenPoint],
        inactive_station_screen: list[StationScreenPoint],
        active_threshold: int,
        secondary_threshold: int,
    ) -> Any:
        visible_active_routes = filtered_prepared_routes(active_static_prepared, active_threshold)
        visible_secondary_routes = filtered_prepared_routes(secondary_static_prepared, secondary_threshold)
        scene = pygame.Surface((render_map_width, render_height)).convert()
        scene.fill(BACKGROUND_COLOR)
        scene.blit(base_map, (0, 0))
        scene.blit(
            draw_routes_layer(
                pygame,
                render_map_width,
                render_height,
                visible_secondary_routes,
                alpha=ROUTE_SECONDARY_ALPHA,
                use_shadow=False,
                fixed_color=ROUTE_SECONDARY_COLOR,
                width_override=3,
                scale=scale * quality_scale,
            ),
            (0, 0),
        )
        scene.blit(
            draw_routes_layer(
                pygame,
                render_map_width,
                render_height,
                visible_active_routes,
                alpha=HEATMAP_ROUTE_ALPHA,
                shadow_alpha=HEATMAP_ROUTE_SHADOW_ALPHA,
                width_override=HEATMAP_ROUTE_WIDTH,
                scale=scale * quality_scale,
            ),
            (0, 0),
        )
        draw_stations(
            pygame,
            scene,
            active_station_screen=active_station_screen,
            inactive_station_screen=inactive_station_screen,
            scale=scale * quality_scale,
        )
        return downscale_static_scene(pygame, scene, map_width, height)

    def compose_comparison_scenes() -> tuple[Any, Any]:
        return (
            compose_stage_scene(
                static_prepared_weekday,
                static_prepared_weekend,
                weekday_active_screen,
                weekday_inactive_screen,
                weekday_route_weight_threshold,
                weekend_route_weight_threshold,
            ),
            compose_stage_scene(
                static_prepared_weekend,
                static_prepared_weekday,
                weekend_active_screen,
                weekend_inactive_screen,
                weekend_route_weight_threshold,
                weekday_route_weight_threshold,
            ),
        )

    weekday_scene, weekend_scene = compose_comparison_scenes()

    active_stage = "weekday"
    route_filter_enabled = max(weekday_max_route_weight, weekend_max_route_weight) > 0
    static_scenes_dirty = False
    filter_dragging = False
    elapsed_real_seconds = 0.0
    animation_real_seconds = 0.0
    panel_scroll = 0
    panel_scroll_max = 0
    mousewheel_event = getattr(pygame, "MOUSEWHEEL", None)
    paused = False
    exit_action = "quit"
    running = True

    def active_route_weight_threshold() -> int:
        if active_stage == "weekday":
            return weekday_route_weight_threshold
        return weekend_route_weight_threshold

    def active_max_route_weight() -> int:
        if active_stage == "weekday":
            return weekday_max_route_weight
        return weekend_max_route_weight

    def set_active_route_weight_threshold_from_x(mouse_x: int) -> None:
        nonlocal weekday_route_weight_threshold, weekend_route_weight_threshold, static_scenes_dirty
        if not route_filter_enabled:
            return

        filter_rect = route_filter_control_rect(
            pygame,
            panel_x,
            panel_width,
            height,
            scale,
            index_from_bottom=4,
        )
        padding_x = scale_px(14, scale, 10)
        track_left = filter_rect.x + padding_x
        track_right = filter_rect.right - padding_x
        fraction = (mouse_x - track_left) / max(track_right - track_left, 1)
        fraction = max(0.0, min(1.0, fraction))
        next_threshold = int(round(min_route_weight + (active_max_route_weight() - min_route_weight) * fraction))

        if active_stage == "weekday" and next_threshold != weekday_route_weight_threshold:
            weekday_route_weight_threshold = next_threshold
            static_scenes_dirty = True
        elif active_stage == "weekend" and next_threshold != weekend_route_weight_threshold:
            weekend_route_weight_threshold = next_threshold
            static_scenes_dirty = True

    while running:
        dt = clock.tick(60) / 1000
        elapsed_real_seconds += dt

        pause_button = pause_button_rect(pygame, panel_x, panel_width, height, scale)
        menu_button = menu_button_rect(pygame, panel_x, panel_width, height, scale)
        toggle_button = toggle_stage_button_rect(pygame, panel_x, panel_width, height, scale)
        route_filter_button = route_filter_control_rect(
            pygame,
            panel_x,
            panel_width,
            height,
            scale,
            index_from_bottom=4,
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in {pygame.K_ESCAPE, pygame.K_q}:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                exit_action = "menu"
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                paused = not paused
            elif event.type == pygame.KEYDOWN and event.key in {pygame.K_TAB, pygame.K_t}:
                active_stage = "weekend" if active_stage == "weekday" else "weekday"
                panel_scroll = 0
            elif mousewheel_event is not None and event.type == mousewheel_event:
                mouse_x, _ = pygame.mouse.get_pos()
                if mouse_x >= panel_x:
                    panel_scroll -= event.y * scale_px(46, scale, 36)
                    panel_scroll = max(0, min(panel_scroll, panel_scroll_max))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in {4, 5}:
                if event.pos[0] >= panel_x:
                    direction = 1 if event.button == 4 else -1
                    panel_scroll -= direction * scale_px(46, scale, 36)
                    panel_scroll = max(0, min(panel_scroll, panel_scroll_max))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if route_filter_enabled and route_filter_button.collidepoint(event.pos):
                    filter_dragging = True
                    set_active_route_weight_threshold_from_x(event.pos[0])
                elif pause_button.collidepoint(event.pos):
                    paused = not paused
                elif menu_button.collidepoint(event.pos):
                    exit_action = "menu"
                    running = False
                elif toggle_button.collidepoint(event.pos):
                    active_stage = "weekend" if active_stage == "weekday" else "weekday"
                    panel_scroll = 0
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                filter_dragging = False
            elif event.type == pygame.MOUSEMOTION and filter_dragging:
                set_active_route_weight_threshold_from_x(event.pos[0])

        if not paused:
            animation_real_seconds += dt

        if static_scenes_dirty:
            weekday_scene, weekend_scene = compose_comparison_scenes()
            static_scenes_dirty = False

        screen.fill(BACKGROUND_COLOR)
        if active_stage == "weekday":
            screen.blit(weekday_scene, (0, 0))
            prepared_routes = filtered_prepared_routes(prepared_weekday, weekday_route_weight_threshold)
            active_routes = weekday_routes
            active_threshold = weekday_route_weight_threshold
            active_max_weight = weekday_max_route_weight
            stage_title = "Dni tygodnia"
        else:
            screen.blit(weekend_scene, (0, 0))
            prepared_routes = filtered_prepared_routes(prepared_weekend, weekend_route_weight_threshold)
            active_routes = weekend_routes
            active_threshold = weekend_route_weight_threshold
            active_max_weight = weekend_max_route_weight
            stage_title = "Weekendy"

        simulated_seconds = animation_real_seconds * time_scale
        draw_cyclists(
            pygame=pygame,
            screen=screen,
            transform=transform,
            prepared_routes=prepared_routes,
            simulated_seconds=simulated_seconds,
            speed_mps=speed_mps,
            scale=scale,
        )
        draw_scale_bar(
            pygame,
            screen,
            small_font,
            map_bounds,
            map_width,
            height,
            average_route_km=average_prepared_route_km(prepared_routes),
            scale=scale,
        )

        panel_scroll_max = draw_weekday_weekend_panel(
            pygame=pygame,
            screen=screen,
            font=font,
            title_font=title_font,
            weekday_routes=weekday_routes,
            weekend_routes=weekend_routes,
            prepared_weekday_routes=prepared_weekday,
            prepared_weekend_routes=prepared_weekend,
            weekday_stations=weekday_stations,
            weekend_stations=weekend_stations,
            map_station_count=len(stations),
            map_stations=stations,
            active_stage=active_stage,
            weekday_station_scores=weekday_station_scores,
            weekend_station_scores=weekend_station_scores,
            cyclist_count=len(prepared_routes),
            filtered_route_count=len(prepared_routes),
            route_weight_threshold=active_threshold if route_filter_enabled else None,
            show_route_filter=route_filter_enabled,
            speed_kmh=speed_kmh,
            time_scale=time_scale,
            panel_x=panel_x,
            panel_width=panel_width,
            height=height,
            scroll=panel_scroll,
            scale=scale,
        )
        panel_scroll = min(panel_scroll, panel_scroll_max)
        if route_filter_enabled:
            draw_route_controls(
                pygame,
                screen,
                font,
                panel_x,
                panel_width,
                height,
                len(prepared_routes),
                show_filter=True,
                route_weight_threshold=active_threshold,
                min_route_weight=min_route_weight,
                max_route_weight=active_max_weight,
                visible_route_count=len(prepared_routes),
                total_route_count=len(active_routes),
                scale=scale,
                filter_index_from_bottom=4,
            )
        draw_toggle_stage_button(pygame, screen, font, panel_x, panel_width, height, active_stage, scale)
        draw_menu_button(pygame, screen, font, panel_x, panel_width, height, scale)
        draw_pause_button(pygame, screen, font, paused, panel_x, panel_width, height, scale)
        if paused:
            draw_pause_badge(pygame, screen, title_font, map_width, scale)
        draw_stage_badge(pygame, screen, title_font, map_width, stage_title, scale)
        draw_attribution(pygame, screen, small_font, map_width, height, scale)

        pygame.display.flip()
        if max_real_seconds is not None and elapsed_real_seconds >= max_real_seconds:
            running = False

    return exit_action
