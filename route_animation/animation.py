import math
from pathlib import Path
from typing import Any

from .basemap import load_or_download_basemap
from .cache import map_cache_path
from .config import (
    BACKGROUND_COLOR,
    ROAD_COLOR,
    ROUTE_ALPHA,
    ROUTE_SECONDARY_ALPHA,
    ROUTE_SECONDARY_COLOR,
    ROUTE_SHADOW_ALPHA,
    ROUTE_SHADOW_COLOR,
    ROUTE_TRANSITION_ALPHA,
    ROUTE_TWO_YEARS_ALPHA,
    ROUTE_TWO_YEARS_SHADOW_ALPHA,
    SIDE_PANEL_WIDTH,
    STATION_COLOR,
    STATION_INACTIVE_ALPHA,
    STATION_INACTIVE_COLOR,
    STATION_INACTIVE_OUTLINE,
    STATION_OUTLINE,
    WHITE,
)
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
    pause_button_rect,
    toggle_stage_button_rect,
)


# Silnik animacji: przygotowanie warstw mapy + ruch rowerzystow.


def as_screen_polylines(polylines: list[list[tuple[float, float]]], transform: Any) -> list[list[tuple[int, int]]]:
    screen_polylines = []
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        world_polyline = project_polyline(polyline)
        screen_polylines.append([transform(point) for point in world_polyline])
    return screen_polylines


def cluster_station_points(station_screen: list[tuple[int, int, float]]) -> list[tuple[int, int, int, float]]:
    if len(station_screen) > 500:
        cell_size = 18
    elif len(station_screen) > 150:
        cell_size = 14
    else:
        cell_size = 1

    buckets: dict[tuple[int, int], list[tuple[int, int, float]]] = {}
    for x, y, score in station_screen:
        key = (x // cell_size, y // cell_size)
        buckets.setdefault(key, []).append((x, y, score))

    clusters = []
    for points in buckets.values():
        x_sum = 0
        y_sum = 0
        score_sum = 0.0
        for x, y, score in points:
            x_sum += x
            y_sum += y
            score_sum += score
        clusters.append((round(x_sum / len(points)), round(y_sum / len(points)), len(points), score_sum))
    return clusters


def score_bounds(station_screen: list[tuple[int, int, float]]) -> tuple[float, float]:
    if not station_screen:
        return 0.0, 1.0
    scores = [max(0.0, float(score)) for _, _, score in station_screen]
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
    active_station_screen: list[tuple[int, int, float]],
    inactive_station_screen: list[tuple[int, int, float]],
) -> None:
    min_score, max_score = score_bounds(active_station_screen + inactive_station_screen)

    inactive_clusters = cluster_station_points(inactive_station_screen)
    if inactive_clusters:
        inactive_layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        for x, y, station_count, cluster_score in inactive_clusters:
            station_radius = radius_from_score(cluster_score, min_score, max_score, 2, 8)
            if station_count > 1:
                station_radius = min(10, station_radius + 1)

            point = (x, y)
            pygame.draw.circle(inactive_layer, (*STATION_INACTIVE_COLOR, STATION_INACTIVE_ALPHA), point, station_radius)
            pygame.draw.circle(
                inactive_layer,
                (*STATION_INACTIVE_OUTLINE, min(255, STATION_INACTIVE_ALPHA + 35)),
                point,
                station_radius,
                1,
            )
        screen.blit(inactive_layer, (0, 0))

    for x, y, station_count, cluster_score in cluster_station_points(active_station_screen):
        station_radius = radius_from_score(cluster_score, min_score, max_score, 3, 11)
        if station_count > 1:
            station_radius = min(13, station_radius + 1)

        point = (x, y)
        pygame.draw.circle(screen, WHITE, point, station_radius + 1)
        pygame.draw.circle(screen, STATION_COLOR, point, station_radius)
        pygame.draw.circle(screen, STATION_OUTLINE, point, station_radius, 1)


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
        pygame.draw.circle(screen, WHITE, cyclist_screen, 10)
        pygame.draw.circle(screen, route.bike_color, cyclist_screen, 7)
        pygame.draw.circle(screen, WHITE, cyclist_screen, 2)


def station_layers(
    stations: list[Station],
    station_screen: list[tuple[int, int]],
    active_station_names: set[str],
    score_lookup: dict[str, float] | None,
) -> tuple[list[tuple[int, int, float]], list[tuple[int, int, float]]]:
    active = []
    inactive = []
    for station, point in zip(stations, station_screen):
        score = 1.0
        if score_lookup is not None:
            score = float(score_lookup.get(station.name, 0.0))
            if score <= 0:
                score = 0.05
        entry = (point[0], point[1], score)
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
            pygame.draw.lines(surface, ROAD_COLOR, False, polyline, 1)
    return surface


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
) -> Any:
    route_width = width_override if width_override is not None else (2 if len(prepared_routes) > 80 else 3)
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
            pygame.draw.lines(route_layer, shadow_color, False, screen_points, route_width + 2)
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
    station_scores: dict[str, float] | None = None,
    max_real_seconds: float | None = None,
) -> str:
    pygame.display.set_caption("London bike route animation")
    clock = pygame.time.Clock()
    panel_width = min(SIDE_PANEL_WIDTH, max(260, width // 3))
    map_width = width - panel_width
    panel_x = map_width

    font = pygame.font.SysFont("segoeui", 18) or pygame.font.Font(None, 18)
    small_font = pygame.font.SysFont("segoeui", 15) or pygame.font.Font(None, 15)
    title_font = pygame.font.SysFont("segoeui", 24, bold=True) or pygame.font.Font(None, 24)

    station_points = [project_polyline([(station.lon, station.lat)])[0] for station in stations]
    all_route_points = [point for route in routes for point in project_polyline(route.points_lonlat)]
    map_bounds = map_bounds_for_points(all_route_points + station_points, map_width, height)
    transform = transform_from_bounds(map_bounds, map_width, height)

    station_screen = [transform(point) for point in station_points]
    active_station_names = {station.name for route in routes for station in route.stations}
    active_station_screen, inactive_station_screen = station_layers(
        stations,
        station_screen,
        active_station_names,
        station_scores,
    )

    speed_mps = speed_kmh / 3.6
    prepared_routes = prepare_routes(routes, transform, speed_mps)

    static_map = build_base_map(
        ctx=ctx,
        pygame=pygame,
        graph=graph,
        cache_dir=cache_dir,
        refresh_map=refresh_map,
        map_zoom=map_zoom,
        map_width=map_width,
        height=height,
        map_bounds=map_bounds,
        transform=transform,
    )
    static_map.blit(
        draw_routes_layer(
            pygame,
            map_width,
            height,
            prepared_routes,
            alpha=ROUTE_TWO_YEARS_ALPHA,
            shadow_alpha=ROUTE_TWO_YEARS_SHADOW_ALPHA,
        ),
        (0, 0),
    )
    draw_stations(
        pygame,
        static_map,
        active_station_screen=active_station_screen,
        inactive_station_screen=inactive_station_screen,
    )

    elapsed_real_seconds = 0.0
    animation_real_seconds = 0.0
    paused = False
    exit_action = "quit"
    running = True

    while running:
        dt = clock.tick(60) / 1000
        elapsed_real_seconds += dt

        pause_button = pause_button_rect(pygame, panel_x, panel_width, height)
        menu_button = menu_button_rect(pygame, panel_x, panel_width, height)
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
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pause_button.collidepoint(event.pos):
                    paused = not paused
                elif menu_button.collidepoint(event.pos):
                    exit_action = "menu"
                    running = False

        if not paused:
            animation_real_seconds += dt
        simulated_seconds = animation_real_seconds * time_scale

        screen.blit(static_map, (0, 0))
        draw_cyclists(
            pygame=pygame,
            screen=screen,
            transform=transform,
            prepared_routes=prepared_routes,
            simulated_seconds=simulated_seconds,
            speed_mps=speed_mps,
        )
        draw_info_panel(
            pygame=pygame,
            screen=screen,
            font=font,
            title_font=title_font,
            routes=routes,
            prepared_routes=prepared_routes,
            stations=stations,
            speed_kmh=speed_kmh,
            time_scale=time_scale,
            panel_x=panel_x,
            panel_width=panel_width,
            height=height,
        )
        draw_menu_button(pygame, screen, font, panel_x, panel_width, height)
        draw_pause_button(pygame, screen, font, paused, panel_x, panel_width, height)
        if paused:
            draw_pause_badge(pygame, screen, title_font, map_width)
        draw_attribution(pygame, screen, small_font, map_width, height)

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
    speed_kmh: float,
    time_scale: float,
    width: int,
    height: int,
    cache_dir: Path,
    refresh_map: bool,
    map_zoom: int | None,
    weekday_station_scores: dict[str, float],
    weekend_station_scores: dict[str, float],
    max_real_seconds: float | None = None,
) -> str:
    pygame.display.set_caption("London bike route animation - weekday/weekend toggle")
    clock = pygame.time.Clock()
    panel_width = min(SIDE_PANEL_WIDTH, max(260, width // 3))
    map_width = width - panel_width
    panel_x = map_width

    font = pygame.font.SysFont("segoeui", 18) or pygame.font.Font(None, 18)
    small_font = pygame.font.SysFont("segoeui", 15) or pygame.font.Font(None, 15)
    title_font = pygame.font.SysFont("segoeui", 24, bold=True) or pygame.font.Font(None, 24)

    station_lookup = {station.name: station for station in weekday_stations + weekend_stations}
    stations = list(station_lookup.values())
    station_points = [project_polyline([(station.lon, station.lat)])[0] for station in stations]
    all_route_points = [
        point for route in (weekday_routes + weekend_routes) for point in project_polyline(route.points_lonlat)
    ]
    map_bounds = map_bounds_for_points(all_route_points + station_points, map_width, height)
    transform = transform_from_bounds(map_bounds, map_width, height)
    station_screen = [transform(point) for point in station_points]

    weekday_active_station_names = {station.name for route in weekday_routes for station in route.stations}
    weekend_active_station_names = {station.name for route in weekend_routes for station in route.stations}

    weekday_active_screen, weekday_inactive_screen = station_layers(
        stations,
        station_screen,
        weekday_active_station_names,
        weekday_station_scores,
    )
    weekend_active_screen, weekend_inactive_screen = station_layers(
        stations,
        station_screen,
        weekend_active_station_names,
        weekend_station_scores,
    )

    speed_mps = speed_kmh / 3.6
    prepared_weekday = prepare_routes(weekday_routes, transform, speed_mps)
    prepared_weekend = prepare_routes(weekend_routes, transform, speed_mps)

    base_map = build_base_map(
        ctx=ctx,
        pygame=pygame,
        graph=graph,
        cache_dir=cache_dir,
        refresh_map=refresh_map,
        map_zoom=map_zoom,
        map_width=map_width,
        height=height,
        map_bounds=map_bounds,
        transform=transform,
    )

    weekday_scene = base_map.copy()
    weekday_scene.blit(
        draw_routes_layer(
            pygame,
            map_width,
            height,
            prepared_weekend,
            alpha=max(ROUTE_SECONDARY_ALPHA, ROUTE_TRANSITION_ALPHA),
            use_shadow=False,
            fixed_color=ROUTE_SECONDARY_COLOR,
            width_override=3,
        ),
        (0, 0),
    )
    weekday_scene.blit(draw_routes_layer(pygame, map_width, height, prepared_weekday), (0, 0))
    draw_stations(
        pygame,
        weekday_scene,
        active_station_screen=weekday_active_screen,
        inactive_station_screen=weekday_inactive_screen,
    )

    weekend_scene = base_map.copy()
    weekend_scene.blit(
        draw_routes_layer(
            pygame,
            map_width,
            height,
            prepared_weekday,
            alpha=max(ROUTE_SECONDARY_ALPHA, ROUTE_TRANSITION_ALPHA),
            use_shadow=False,
            fixed_color=ROUTE_SECONDARY_COLOR,
            width_override=3,
        ),
        (0, 0),
    )
    weekend_scene.blit(draw_routes_layer(pygame, map_width, height, prepared_weekend), (0, 0))
    draw_stations(
        pygame,
        weekend_scene,
        active_station_screen=weekend_active_screen,
        inactive_station_screen=weekend_inactive_screen,
    )

    active_stage = "weekday"
    elapsed_real_seconds = 0.0
    animation_real_seconds = 0.0
    paused = False
    exit_action = "quit"
    running = True

    while running:
        dt = clock.tick(60) / 1000
        elapsed_real_seconds += dt

        pause_button = pause_button_rect(pygame, panel_x, panel_width, height)
        menu_button = menu_button_rect(pygame, panel_x, panel_width, height)
        toggle_button = toggle_stage_button_rect(pygame, panel_x, panel_width, height)

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
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pause_button.collidepoint(event.pos):
                    paused = not paused
                elif menu_button.collidepoint(event.pos):
                    exit_action = "menu"
                    running = False
                elif toggle_button.collidepoint(event.pos):
                    active_stage = "weekend" if active_stage == "weekday" else "weekday"

        if not paused:
            animation_real_seconds += dt

        if active_stage == "weekday":
            screen.blit(weekday_scene, (0, 0))
            prepared_routes = prepared_weekday
            stage_title = "Dni robocze"
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
        )

        draw_weekday_weekend_panel(
            pygame=pygame,
            screen=screen,
            font=font,
            title_font=title_font,
            weekday_routes=weekday_routes,
            weekend_routes=weekend_routes,
            weekday_stations=weekday_stations,
            weekend_stations=weekend_stations,
            active_stage=active_stage,
            speed_kmh=speed_kmh,
            time_scale=time_scale,
            panel_x=panel_x,
            panel_width=panel_width,
            height=height,
        )
        draw_toggle_stage_button(pygame, screen, font, panel_x, panel_width, height, active_stage)
        draw_menu_button(pygame, screen, font, panel_x, panel_width, height)
        draw_pause_button(pygame, screen, font, paused, panel_x, panel_width, height)
        if paused:
            draw_pause_badge(pygame, screen, title_font, map_width)
        draw_stage_badge(pygame, screen, title_font, map_width, stage_title)
        draw_attribution(pygame, screen, small_font, map_width, height)

        pygame.display.flip()
        if max_real_seconds is not None and elapsed_real_seconds >= max_real_seconds:
            running = False

    return exit_action
