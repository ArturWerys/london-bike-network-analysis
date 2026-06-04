from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .basemap import load_or_download_basemap
from .cache import map_cache_path
from .config import (
    BACKGROUND_COLOR,
    DISTRICT_COLORS,
    ROAD_COLOR,
    ROUTE_ALPHA,
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
from .data import route_district
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
    draw_attribution,
    draw_info_panel,
    draw_menu_button,
    draw_pause_badge,
    draw_pause_button,
    draw_stage_badge,
    draw_toggle_stage_button,
    draw_weekday_weekend_panel,
    menu_button_rect,
    panel_width_for_window,
    pause_button_rect,
    scale_px,
    scaled_font,
    toggle_stage_button_rect,
    ui_scale,
)


# Silnik animacji: przygotowanie warstw mapy + ruch rowerzystow.

Color = tuple[int, int, int]
StationScreenPoint = tuple[int, int, float, Color, Color]
StationCluster = tuple[int, int, int, float, Color, Color]


def as_screen_polylines(polylines: list[list[tuple[float, float]]], transform: Any) -> list[list[tuple[int, int]]]:
    screen_polylines = []
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        world_polyline = project_polyline(polyline)
        screen_polylines.append([transform(point) for point in world_polyline])
    return screen_polylines


def cluster_station_points(
    station_screen: list[StationScreenPoint],
    scale: float = 1.0,
) -> list[StationCluster]:
    if len(station_screen) > 500:
        cell_size = scale_px(18, scale, 12)
    elif len(station_screen) > 150:
        cell_size = scale_px(14, scale, 10)
    else:
        cell_size = 1

    buckets: dict[tuple[int, int], list[StationScreenPoint]] = {}
    for x, y, score, fill_color, outline_color in station_screen:
        key = (x // cell_size, y // cell_size)
        buckets.setdefault(key, []).append((x, y, score, fill_color, outline_color))

    clusters = []
    for points in buckets.values():
        x_sum = 0
        y_sum = 0
        score_sum = 0.0
        color_counts: dict[tuple[Color, Color], int] = {}
        for x, y, score, fill_color, outline_color in points:
            x_sum += x
            y_sum += y
            score_sum += score
            color_key = (fill_color, outline_color)
            color_counts[color_key] = color_counts.get(color_key, 0) + 1
        fill_color, outline_color = max(color_counts.items(), key=lambda item: item[1])[0]
        clusters.append(
            (round(x_sum / len(points)), round(y_sum / len(points)), len(points), score_sum, fill_color, outline_color)
        )
    return clusters


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

    inactive_clusters = cluster_station_points(inactive_station_screen, scale)
    if inactive_clusters:
        inactive_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        for x, y, station_count, cluster_score, fill_color, outline_color in inactive_clusters:
            station_radius = radius_from_score(
                cluster_score,
                min_score,
                max_score,
                scale_px(2, scale, 2),
                scale_px(8, scale, 5),
            )
            if station_count > 1:
                station_radius = min(scale_px(10, scale, 7), station_radius + scale_px(1, scale, 1))

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

    active_clusters = cluster_station_points(active_station_screen, scale)
    if not active_clusters:
        return

    active_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    for x, y, station_count, cluster_score, fill_color, outline_color in active_clusters:
        station_radius = radius_from_score(
            cluster_score,
            min_score,
            max_score,
            scale_px(3, scale, 2),
            scale_px(11, scale, 7),
        )
        if station_count > 1:
            station_radius = min(scale_px(13, scale, 8), station_radius + scale_px(1, scale, 1))

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
) -> None:
    for prepared_route in prepared_routes:
        route = prepared_route["route"]
        total_distance_m = prepared_route["total_distance_m"]
        simulated_trip_seconds = total_distance_m / max(speed_mps, 1e-9)
        loop_seconds = simulated_trip_seconds + 3.0
        loop_position = (simulated_seconds + prepared_route["phase_seconds"]) % loop_seconds
        current_distance = min(loop_position * speed_mps, total_distance_m)
        cyclist_world = point_at_distance(prepared_route["world"], prepared_route["distances"], current_distance)
        cyclist_screen = transform(cyclist_world)
        pygame.draw.circle(screen, WHITE, cyclist_screen, scale_px(10, scale, 7))
        pygame.draw.circle(screen, route.bike_color, cyclist_screen, scale_px(7, scale, 5))
        pygame.draw.circle(screen, WHITE, cyclist_screen, scale_px(2, scale, 2))


def mercator_latitude_from_y(y: float) -> float:
    radius = 6_378_137.0
    return math.degrees(math.atan(math.sinh(y / radius)))


def scale_bar_pixel_length(map_bounds: tuple[float, float, float, float], map_width: int) -> int:
    left, bottom, right, top = map_bounds
    center_lat = mercator_latitude_from_y((bottom + top) / 2)
    projected_meters_per_pixel = (right - left) / max(map_width, 1)
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
) -> None:
    bar_width = scale_bar_pixel_length(map_bounds, map_width)
    max_bar_width = map_width - scale_px(72, scale, 48)
    if bar_width > max_bar_width:
        return
    if average_route_km is None or average_route_km <= 0:
        return

    padding_x = scale_px(12, scale, 9)
    padding_y = scale_px(8, scale, 6)
    tick_height = scale_px(8, scale, 6)
    margin_x = scale_px(42, scale, 30)
    bottom_margin = scale_px(46, scale, 34)
    average_label_image = font.render(f"Śr. trasa na mapie: {average_route_km:.2f} km", True, TEXT_COLOR)
    average_bar_width = int(round(bar_width * average_route_km))
    if average_bar_width > max_bar_width:
        average_bar_width = max_bar_width

    panel_width = max(average_bar_width, average_label_image.get_width()) + padding_x * 2
    panel_height = average_label_image.get_height() + tick_height * 2 + padding_y * 3
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
        bar_color,
        line_width,
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
    bar_color: tuple[int, int, int],
    line_width: int,
    scale: float,
) -> None:
    pygame.draw.line(panel, bar_color, (bar_x, bar_y), (bar_x + bar_width, bar_y), line_width)
    tick_positions = scale_tick_positions(bar_width, distance_km)
    for tick_offset in tick_positions:
        tick_x = bar_x + tick_offset
        pygame.draw.line(
            panel,
            bar_color,
            (tick_x, bar_y - tick_height),
            (tick_x, bar_y + tick_height),
            scale_px(1, scale, 1),
        )


def scale_tick_positions(bar_width: int, distance_km: float, tick_interval_km: float = 0.25) -> list[int]:
    if bar_width <= 0 or distance_km <= 0:
        return [0]

    positions = []
    tick_count = int(math.floor(distance_km / tick_interval_km))
    for tick_index in range(tick_count + 1):
        tick_distance_km = tick_index * tick_interval_km
        positions.append(round(bar_width * tick_distance_km / distance_km))

    if positions[-1] != bar_width:
        positions.append(bar_width)

    return positions


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
) -> tuple[list[StationScreenPoint], list[StationScreenPoint]]:
    active = []
    inactive = []
    for station, point in zip(stations, station_screen):
        score = 1.0
        if score_lookup is not None:
            score = float(score_lookup.get(station.name, 0.0))
            if score <= 0:
                score = 0.05
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
    if basemap_surface is not None:
        surface.blit(basemap_surface, (0, 0))
        soft_overlay = pygame.Surface((map_width, height), pygame.SRCALPHA)
        soft_overlay.fill((255, 255, 255, 34))
        surface.blit(soft_overlay, (0, 0))
        return surface

    surface.fill(BACKGROUND_COLOR)
    if graph is None:
        return surface

    for polyline in as_screen_polylines(background_edge_lonlat(graph), transform):
        if len(polyline) >= 2:
            pygame.draw.lines(surface, ROAD_COLOR, False, polyline, scale_px(1, scale, 1))
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
) -> Any:
    base_route_width = width_override if width_override is not None else (2 if len(prepared_routes) > 80 else 3)
    route_width = scale_px(base_route_width, scale, 2)
    route_layer = pygame.Surface((map_width, height), pygame.SRCALPHA)
    shadow_color = (*ROUTE_SHADOW_COLOR, shadow_alpha)

    for prepared_route in prepared_routes:
        route = prepared_route["route"]
        screen_points = prepared_route["screen"]
        if len(screen_points) < 2:
            continue
        base_color = fixed_color if fixed_color is not None else route.route_color
        route_color = (*base_color, alpha)
        if use_shadow:
            pygame.draw.lines(route_layer, shadow_color, False, screen_points, route_width + scale_px(2, scale, 1))
        pygame.draw.lines(route_layer, route_color, False, screen_points, route_width)
    return route_layer


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
    )

    speed_mps = speed_kmh / 3.6
    prepared_routes = prepare_routes(routes, transform, speed_mps)
    static_prepared_routes = prepare_routes(routes, static_transform, speed_mps)

    static_map = build_base_map(
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
    static_map.blit(
        draw_routes_layer(
            pygame,
            render_map_width,
            render_height,
            static_prepared_routes,
            alpha=ROUTE_TWO_YEARS_ALPHA,
            shadow_alpha=ROUTE_TWO_YEARS_SHADOW_ALPHA,
            scale=scale * quality_scale,
        ),
        (0, 0),
    )
    draw_stations(
        pygame,
        static_map,
        active_station_screen=static_active_station_screen,
        inactive_station_screen=static_inactive_station_screen,
        scale=scale * quality_scale,
    )
    static_map = downscale_static_scene(pygame, static_map, map_width, height)

    elapsed_real_seconds = 0.0
    animation_real_seconds = 0.0
    panel_scroll = 0
    panel_scroll_max = 0
    mousewheel_event = getattr(pygame, "MOUSEWHEEL", None)
    paused = False
    exit_action = "quit"
    running = True

    while running:
        dt = clock.tick(60) / 1000
        elapsed_real_seconds += dt

        pause_button = pause_button_rect(pygame, panel_x, panel_width, height, scale)
        menu_button = menu_button_rect(pygame, panel_x, panel_width, height, scale)
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
                if pause_button.collidepoint(event.pos):
                    paused = not paused
                elif menu_button.collidepoint(event.pos):
                    exit_action = "menu"
                    running = False

        if not paused:
            animation_real_seconds += dt
        simulated_seconds = animation_real_seconds * time_scale

        screen.fill(BACKGROUND_COLOR)
        screen.blit(static_map, (0, 0))
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
            panel_x=panel_x,
            panel_width=panel_width,
            height=height,
            scroll=panel_scroll,
            scale=scale,
        )
        panel_scroll = min(panel_scroll, panel_scroll_max)
        draw_menu_button(pygame, screen, font, panel_x, panel_width, height, scale)
        draw_pause_button(pygame, screen, font, paused, panel_x, panel_width, height, scale)
        if paused:
            draw_pause_badge(pygame, screen, title_font, map_width, scale)
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
    pygame.display.set_caption("London bike route animation - dni tygodnia vs weekendy")
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
    )
    weekend_active_screen, weekend_inactive_screen = station_layers(
        stations,
        static_station_screen,
        weekend_active_station_names,
        weekend_station_scores,
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

    weekday_scene = pygame.Surface((render_map_width, render_height)).convert()
    weekday_scene.blit(base_map, (0, 0))
    weekday_scene.blit(
        draw_routes_layer(
            pygame,
            render_map_width,
            render_height,
            static_prepared_weekend,
            alpha=ROUTE_SECONDARY_ALPHA,
            use_shadow=False,
            fixed_color=ROUTE_SECONDARY_COLOR,
            width_override=3,
            scale=scale * quality_scale,
        ),
        (0, 0),
    )
    weekday_scene.blit(
        draw_routes_layer(
            pygame,
            render_map_width,
            render_height,
            static_prepared_weekday,
            scale=scale * quality_scale,
        ),
        (0, 0),
    )
    draw_stations(
        pygame,
        weekday_scene,
        active_station_screen=weekday_active_screen,
        inactive_station_screen=weekday_inactive_screen,
        scale=scale * quality_scale,
    )
    weekday_scene = downscale_static_scene(pygame, weekday_scene, map_width, height)

    weekend_scene = pygame.Surface((render_map_width, render_height)).convert()
    weekend_scene.blit(base_map, (0, 0))
    weekend_scene.blit(
        draw_routes_layer(
            pygame,
            render_map_width,
            render_height,
            static_prepared_weekday,
            alpha=ROUTE_SECONDARY_ALPHA,
            use_shadow=False,
            fixed_color=ROUTE_SECONDARY_COLOR,
            width_override=3,
            scale=scale * quality_scale,
        ),
        (0, 0),
    )
    weekend_scene.blit(
        draw_routes_layer(
            pygame,
            render_map_width,
            render_height,
            static_prepared_weekend,
            scale=scale * quality_scale,
        ),
        (0, 0),
    )
    draw_stations(
        pygame,
        weekend_scene,
        active_station_screen=weekend_active_screen,
        inactive_station_screen=weekend_inactive_screen,
        scale=scale * quality_scale,
    )
    weekend_scene = downscale_static_scene(pygame, weekend_scene, map_width, height)

    active_stage = "weekday"
    elapsed_real_seconds = 0.0
    animation_real_seconds = 0.0
    panel_scroll = 0
    panel_scroll_max = 0
    mousewheel_event = getattr(pygame, "MOUSEWHEEL", None)
    paused = False
    exit_action = "quit"
    running = True

    while running:
        dt = clock.tick(60) / 1000
        elapsed_real_seconds += dt

        pause_button = pause_button_rect(pygame, panel_x, panel_width, height, scale)
        menu_button = menu_button_rect(pygame, panel_x, panel_width, height, scale)
        toggle_button = toggle_stage_button_rect(pygame, panel_x, panel_width, height, scale)

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
                if pause_button.collidepoint(event.pos):
                    paused = not paused
                elif menu_button.collidepoint(event.pos):
                    exit_action = "menu"
                    running = False
                elif toggle_button.collidepoint(event.pos):
                    active_stage = "weekend" if active_stage == "weekday" else "weekday"
                    panel_scroll = 0

        if not paused:
            animation_real_seconds += dt

        screen.fill(BACKGROUND_COLOR)
        if active_stage == "weekday":
            screen.blit(weekday_scene, (0, 0))
            prepared_routes = prepared_weekday
            stage_title = "Dni tygodnia"
        else:
            screen.blit(weekend_scene, (0, 0))
            prepared_routes = prepared_weekend
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
            active_stage=active_stage,
            speed_kmh=speed_kmh,
            time_scale=time_scale,
            panel_x=panel_x,
            panel_width=panel_width,
            height=height,
            scroll=panel_scroll,
            scale=scale,
        )
        panel_scroll = min(panel_scroll, panel_scroll_max)
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
