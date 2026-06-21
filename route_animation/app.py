from __future__ import annotations

import json
import os

from .animation import run_animation, run_heatmap_scope_animation, run_weekday_weekend_animation
from .cache import graph_cache_path, routes_cache_path
from .cli import parse_args
from .config import (
    COMPARISON_MAX_ROUTES,
    COMPARISON_STATION_COUNT,
    DEFAULT_HEATMAP_MAX_ROUTES,
    DEFAULT_HEATMAP_STATION_COUNT,
    DEFAULT_STATION_COUNT,
    DEFAULT_MAX_ROUTES,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MAX_RENDER_SCALE,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    WINDOW_SCREEN_RATIO,
)
from .data import (
    apply_heatmap_route_styles,
    load_station_network_edges,
    load_stations_table,
    print_station_matches,
    route_district,
    route_style,
    selected_stations,
    station_scores_from_edges,
    stations_from_exact_names,
    top_station_pairs_from_edges,
    top_stations_from_network,
    weekday_weekend_summary,
)
from .dependencies import require_pandas_module, require_pygame_module, require_runtime_modules
from .geo import bbox_around_stations
from .models import RouteAnimation, Station
from .osm_network import (
    load_or_download_graph,
    nearest_graph_nodes,
    route_lonlat_points,
    route_nodes_for_stations,
)
from .ui import run_mode_menu, show_loading_screen


# Glowny scenariusz: dane projektu -> graf OSM -> trasy -> animacja pygame.


def desktop_size(pygame) -> tuple[int, int] | None:
    get_desktop_sizes = getattr(pygame.display, "get_desktop_sizes", None)
    if get_desktop_sizes is not None:
        try:
            sizes = get_desktop_sizes()
        except Exception:
            sizes = []

        if sizes:
            width, height = sizes[0]
            if width > 0 and height > 0:
                return int(width), int(height)

    try:
        info = pygame.display.Info()
    except Exception:
        return None

    width = int(getattr(info, "current_w", 0))
    height = int(getattr(info, "current_h", 0))
    if width > 0 and height > 0:
        return width, height

    return None


def window_size_for_screen(
    pygame,
    requested_width: int | None,
    requested_height: int | None,
) -> tuple[int, int]:
    if requested_width is not None and requested_width < 1:
        raise ValueError("--width must be at least 1.")
    if requested_height is not None and requested_height < 1:
        raise ValueError("--height must be at least 1.")

    size = desktop_size(pygame)
    if size is None:
        return (
            requested_width or DEFAULT_WINDOW_WIDTH,
            requested_height or DEFAULT_WINDOW_HEIGHT,
        )

    screen_width, screen_height = size
    max_width = max(1, min(DEFAULT_WINDOW_WIDTH, int(screen_width * WINDOW_SCREEN_RATIO)))
    max_height = max(1, min(DEFAULT_WINDOW_HEIGHT, int(screen_height * WINDOW_SCREEN_RATIO)))

    if requested_width is not None or requested_height is not None:
        aspect_ratio = DEFAULT_WINDOW_WIDTH / DEFAULT_WINDOW_HEIGHT
        width = requested_width
        height = requested_height
        if width is None and height is not None:
            width = round(height * aspect_ratio)
        if height is None and width is not None:
            height = round(width / aspect_ratio)
        return min(width or max_width, screen_width), min(height or max_height, screen_height)

    scale = min(
        max_width / DEFAULT_WINDOW_WIDTH,
        max_height / DEFAULT_WINDOW_HEIGHT,
        1.0,
    )
    width = round(DEFAULT_WINDOW_WIDTH * scale)
    height = round(DEFAULT_WINDOW_HEIGHT * scale)

    if width < MIN_WINDOW_WIDTH and max_width >= MIN_WINDOW_WIDTH:
        width = MIN_WINDOW_WIDTH
        height = round(width * DEFAULT_WINDOW_HEIGHT / DEFAULT_WINDOW_WIDTH)
    if height < MIN_WINDOW_HEIGHT and max_height >= MIN_WINDOW_HEIGHT:
        height = MIN_WINDOW_HEIGHT
        width = round(height * DEFAULT_WINDOW_WIDTH / DEFAULT_WINDOW_HEIGHT)

    return min(width, screen_width), min(height, screen_height)


def choose_mode(selected_mode: str | None, pygame, screen, width: int, height: int) -> str | None:
    if selected_mode is not None:
        return selected_mode

    if os.environ.get("SDL_VIDEODRIVER", "").lower() == "dummy":
        print("No interactive input detected, default mode: two_years_heatmap")
        return "two_years_heatmap"

    return run_mode_menu(screen, pygame, width, height)


def load_routes_from_cache(cache_path, stations) -> list[RouteAnimation] | None:
    if not cache_path.exists():
        return None

    print(f"Loading cached routes: {cache_path}")
    station_by_name = {}
    for station in stations:
        station_by_name[station.name] = station

    try:
        with cache_path.open("r", encoding="utf-8") as file:
            route_rows = json.load(file)
    except json.JSONDecodeError:
        print(f"Route cache is broken, routes will be calculated again: {cache_path}")
        return None

    routes = []
    for route_index, route_row in enumerate(route_rows):
        route_stations = []
        for station_name in route_row["station_names"]:
            route_stations.append(station_by_name[station_name])

        route_nodes = []
        for node in route_row["route_nodes"]:
            route_nodes.append(int(node))

        points_lonlat = []
        for lon, lat in route_row["points_lonlat"]:
            points_lonlat.append((float(lon), float(lat)))

        district_name = route_row.get("district_name")
        if district_name is None:
            district_name = route_district(route_stations)
        current_route_style = route_style(route_index, district_name)

        routes.append(
            RouteAnimation(
                name=str(route_row["name"]),
                stations=route_stations,
                route_nodes=route_nodes,
                points_lonlat=points_lonlat,
                district_name=current_route_style["district_name"],
                route_color=current_route_style["route_color"],
                bike_color=current_route_style["bike_color"],
                station_network_weight=int(route_row["station_network_weight"]),
            )
        )

    return routes


def load_cached_graph_for_render(ox, graph_path: Path, cache_dir: Path, bbox: tuple[float, float, float, float]):
    if graph_path.exists():
        return load_or_download_graph(ox, graph_path, bbox, refresh_osm=False)

    fallback_graph_path = cache_dir / "road_distances" / "london_bike_network.graphml"
    if fallback_graph_path.exists():
        print(f"Specific cached OSM graph not found. Loading fallback graph: {fallback_graph_path}")
        return load_or_download_graph(ox, fallback_graph_path, bbox, refresh_osm=False)

    print("Cached OSM graph not found. Basemap tiles will be used if available.")
    return None


def save_routes_to_cache(cache_path, routes: list[RouteAnimation]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    route_rows = []

    for route in routes:
        station_names = []
        for station in route.stations:
            station_names.append(station.name)

        route_nodes = []
        for node in route.route_nodes:
            route_nodes.append(int(node))

        points_lonlat = []
        for lon, lat in route.points_lonlat:
            points_lonlat.append([float(lon), float(lat)])

        route_color = []
        for color_value in route.route_color:
            route_color.append(int(color_value))

        bike_color = []
        for color_value in route.bike_color:
            bike_color.append(int(color_value))

        route_rows.append(
            {
                "name": route.name,
                "station_names": station_names,
                "route_nodes": route_nodes,
                "points_lonlat": points_lonlat,
                "district_name": route.district_name,
                "route_color": route_color,
                "bike_color": bike_color,
                "station_network_weight": int(route.station_network_weight),
            }
        )

    temporary_path = cache_path.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(route_rows, file)
    temporary_path.replace(cache_path)

    print(f"Saved route cache: {cache_path}")


def build_routes_from_station_pairs(
    ox,
    nx,
    graph,
    station_lookup: dict[str, Station],
    station_node_lookup: dict[str, int],
    station_pairs: list[tuple[str, str, int]],
    route_prefix: str,
) -> list[RouteAnimation]:
    routes = []
    for route_index, (start_name, end_name, pair_weight) in enumerate(station_pairs):
        start_station = station_lookup.get(start_name)
        end_station = station_lookup.get(end_name)
        start_node = station_node_lookup.get(start_name)
        end_node = station_node_lookup.get(end_name)

        if start_station is None or end_station is None:
            continue
        if start_node is None or end_node is None:
            continue

        route_stations = [start_station, end_station]
        district_name = route_district(route_stations)
        current_route_style = route_style(route_index, district_name)
        routing_graph, route_nodes = route_nodes_for_stations(ox, nx, graph, [start_node, end_node])
        route_points_lonlat = route_lonlat_points(routing_graph, route_nodes)

        if len(route_points_lonlat) < 2:
            continue

        routes.append(
            RouteAnimation(
                name=f"{route_prefix} {route_index + 1}",
                stations=route_stations,
                route_nodes=route_nodes,
                points_lonlat=route_points_lonlat,
                district_name=current_route_style["district_name"],
                route_color=current_route_style["route_color"],
                bike_color=current_route_style["bike_color"],
                station_network_weight=int(pair_weight),
            )
        )

    return routes


def print_summary(stations, routes, label: str = "") -> None:
    total_route_nodes = 0
    total_station_network_trips = 0

    for route in routes:
        total_route_nodes += len(route.route_nodes)
        total_station_network_trips += route.station_network_weight

    if label:
        print("")
        print(f"--- {label} ---")
    print(f"Selected stations: {len(stations)}")
    print(f"Generated routes: {len(routes)}")
    print(f"Total OSM route nodes: {total_route_nodes}")
    print(f"Station-network trips across routes: {total_station_network_trips}")


def print_top_preview(label: str, station_names: list[str], max_count: int = 10) -> None:
    print("")
    print(f"Top stations ({label}):")
    for station_name in station_names[:max_count]:
        print(f"  - {station_name}")


def select_routes_for_display(
    routes: list[RouteAnimation],
    max_routes: int,
    label: str,
) -> list[RouteAnimation]:
    if max_routes <= 0 or len(routes) <= max_routes:
        return routes

    sorted_routes = sorted(
        routes,
        key=lambda route: (route.station_network_weight, len(route.points_lonlat)),
        reverse=True,
    )
    selected_routes = sorted_routes[:max_routes]
    print(
        f"Showing {len(selected_routes)} of {len(routes)} routes in {label} mode "
        "(top by network traffic)."
    )
    return selected_routes


def run_two_year_mode(args, pd, pygame, screen, ox, nx, ctx, heatmap: bool = False) -> str:
    stations_df = load_stations_table(pd)
    all_station_names = [str(name) for name in stations_df["station_name"].tolist()]
    all_stations = stations_from_exact_names(stations_df, all_station_names)

    if args.stations:
        if len(args.stations) < 2:
            raise ValueError("--stations must contain at least two station names.")
        stations = selected_stations(pd, args.stations)
    else:
        if args.station_count < 2:
            raise ValueError("--station-count must be at least 2.")
        station_count = args.station_count
        if heatmap and args.station_count == DEFAULT_STATION_COUNT:
            station_count = DEFAULT_HEATMAP_STATION_COUNT
        stations = top_stations_from_network(pd, station_count)

    station_lookup = {}
    for station in stations:
        station_lookup[station.name] = station

    bbox = bbox_around_stations(stations, args.buffer_meters)
    graph_path = graph_cache_path(args.cache_dir, bbox, stations)
    route_cache_label = (
        "two_years_without_discontinuities_undirected_pairs_v1"
        if heatmap
        else "two_years_without_discontinuities_pairs_v2"
    )
    max_routes = args.max_routes
    if heatmap and args.max_routes == DEFAULT_MAX_ROUTES:
        max_routes = DEFAULT_HEATMAP_MAX_ROUTES
    route_cache = routes_cache_path(
        args.cache_dir,
        stations,
        graph_path.name,
        cache_label=route_cache_label,
    )
    force_rebuild_routes = args.refresh_routes or args.refresh_osm
    routes = None if force_rebuild_routes else load_routes_from_cache(route_cache, stations)
    graph = None

    station_score_lookup = None

    if routes is None:
        graph = None if args.refresh_osm else load_cached_graph_for_render(ox, graph_path, args.cache_dir, bbox)
        if graph is None:
            graph = load_or_download_graph(
                ox,
                graph_path,
                bbox,
                args.refresh_osm,
            )

        station_nodes = nearest_graph_nodes(graph, stations)
        station_node_lookup = {}
        for station, node in zip(stations, station_nodes):
            station_node_lookup[station.name] = node

        candidate_limit = max(max_routes * 3, 60)
        edges_df = load_station_network_edges(pd)
        station_scores = station_scores_from_edges(edges_df)
        station_score_lookup = {str(name): float(score) for name, score in station_scores.items()}
        station_pairs = top_station_pairs_from_edges(
            edges_df,
            set(station_lookup),
            candidate_limit,
        )

        routes = build_routes_from_station_pairs(
            ox,
            nx,
            graph,
            station_lookup=station_lookup,
            station_node_lookup=station_node_lookup,
            station_pairs=station_pairs,
            route_prefix="Trasa",
        )
        save_routes_to_cache(route_cache, routes)
    else:
        print("Routes loaded from cache.")
        graph = load_cached_graph_for_render(ox, graph_path, args.cache_dir, bbox)
        edges_df = load_station_network_edges(pd)
        station_scores = station_scores_from_edges(edges_df)
        station_score_lookup = {str(name): float(score) for name, score in station_scores.items()}

    mode_label = "two_years_heatmap" if heatmap else "two_years"
    routes = select_routes_for_display(routes, max_routes, mode_label)
    if heatmap:
        routes = apply_heatmap_route_styles(routes)

    summary_label = "Animacja 2 lata" if heatmap else "Dawna animacja 2 lata"
    print_summary(stations, routes, label=summary_label)

    return run_animation(
        ctx=ctx,
        pygame=pygame,
        screen=screen,
        graph=graph,
        stations=stations,
        routes=routes,
        all_stations=all_stations,
        speed_kmh=args.speed_kmh,
        time_scale=args.time_scale,
        width=args.width,
        height=args.height,
        cache_dir=args.cache_dir,
        refresh_map=args.refresh_map,
        map_zoom=args.map_zoom,
        render_scale=args.render_scale,
        station_scores=station_score_lookup,
        color_mode="heatmap" if heatmap else "district",
        max_real_seconds=args.max_real_seconds,
    )


def run_heatmap_scope_mode(args, pd, pygame, screen, ox, nx, ctx) -> str:
    stations_df = load_stations_table(pd)
    all_station_names = [str(name) for name in stations_df["station_name"].tolist()]
    all_stations = stations_from_exact_names(stations_df, all_station_names)

    if args.station_count < 2:
        raise ValueError("--station-count must be at least 2.")

    station_count = args.station_count
    if args.station_count == DEFAULT_STATION_COUNT:
        station_count = DEFAULT_HEATMAP_STATION_COUNT

    max_routes = args.max_routes
    if args.max_routes == DEFAULT_MAX_ROUTES:
        max_routes = DEFAULT_HEATMAP_MAX_ROUTES

    full_edges = load_station_network_edges(pd)
    full_scores = station_scores_from_edges(full_edges)
    full_score_lookup = {str(name): float(score) for name, score in full_scores.items()}

    if args.stations:
        if len(args.stations) < 2:
            raise ValueError("--stations must contain at least two station names.")
        full_stations = selected_stations(pd, args.stations)
    else:
        full_stations = top_stations_from_network(pd, station_count)

    summary = weekday_weekend_summary(pd, args.cache_dir, top_n=station_count)
    weekday_scores = station_scores_from_edges(summary["weekday_edges"])
    weekend_scores = station_scores_from_edges(summary["weekend_edges"])
    weekday_score_lookup = {str(name): float(score) for name, score in weekday_scores.items()}
    weekend_score_lookup = {str(name): float(score) for name, score in weekend_scores.items()}

    weekday_stations = stations_from_exact_names(stations_df, summary["weekday_top_names"])
    weekend_stations = stations_from_exact_names(stations_df, summary["weekend_top_names"])

    print_top_preview("pełne 2 lata", [station.name for station in full_stations])
    print_top_preview("dni robocze", summary["weekday_top_names"])
    print_top_preview("weekendy", summary["weekend_top_names"])

    map_station_lookup = {}
    for station in full_stations + weekday_stations + weekend_stations:
        map_station_lookup[station.name] = station
    map_stations = list(map_station_lookup.values())

    if len(map_stations) < 2:
        raise RuntimeError("Not enough stations to run the heatmap animation.")

    bbox = bbox_around_stations(map_stations, args.buffer_meters)
    graph_path = graph_cache_path(args.cache_dir, bbox, map_stations)
    force_rebuild_routes = args.refresh_routes or args.refresh_osm
    candidate_limit = max(max_routes * 3, 60)

    scope_builders = [
        {
            "key": "full",
            "label": "Pełne 2 lata",
            "button_label": "2 lata",
            "stations": full_stations,
            "edges": full_edges,
            "station_scores": full_score_lookup,
            "cache_label": "heatmap_full_without_discontinuities_undirected_pairs_v1",
            "route_prefix": "2 lata",
            "stations_label": "Stacje do tras",
            "routes_label": "Trasy",
        },
        {
            "key": "weekday",
            "label": "Dni tygodnia",
            "button_label": "Dni tyg.",
            "stations": weekday_stations,
            "edges": summary["weekday_edges"],
            "station_scores": weekday_score_lookup,
            "cache_label": "heatmap_weekday_without_discontinuities_undirected_pairs_v1",
            "route_prefix": "Dni tyg.",
            "stations_label": "Stacje dni tyg.",
            "routes_label": "Trasy dni tyg.",
        },
        {
            "key": "weekend",
            "label": "Weekendy",
            "button_label": "Weekendy",
            "stations": weekend_stations,
            "edges": summary["weekend_edges"],
            "station_scores": weekend_score_lookup,
            "cache_label": "heatmap_weekend_without_discontinuities_undirected_pairs_v1",
            "route_prefix": "Weekend",
            "stations_label": "Stacje weekendów",
            "routes_label": "Trasy weekendów",
        },
    ]

    route_caches = {}
    scope_routes: dict[str, list[RouteAnimation] | None] = {}
    for scope in scope_builders:
        route_caches[scope["key"]] = routes_cache_path(
            args.cache_dir,
            scope["stations"],
            graph_path.name,
            cache_label=scope["cache_label"],
        )
        if force_rebuild_routes:
            scope_routes[scope["key"]] = None
        else:
            scope_routes[scope["key"]] = load_routes_from_cache(route_caches[scope["key"]], scope["stations"])

    graph = None
    if any(routes is None for routes in scope_routes.values()):
        graph = load_or_download_graph(
            ox,
            graph_path,
            bbox,
            args.refresh_osm,
        )
        map_station_nodes = nearest_graph_nodes(graph, map_stations)
        station_node_lookup = {}
        for station, node in zip(map_stations, map_station_nodes):
            station_node_lookup[station.name] = node

        for scope in scope_builders:
            scope_key = scope["key"]
            if scope_routes[scope_key] is not None:
                continue

            station_lookup = {}
            for station in scope["stations"]:
                station_lookup[station.name] = station

            station_pairs = top_station_pairs_from_edges(
                scope["edges"],
                set(station_lookup),
                candidate_limit,
            )
            routes = build_routes_from_station_pairs(
                ox,
                nx,
                graph,
                station_lookup=station_lookup,
                station_node_lookup=station_node_lookup,
                station_pairs=station_pairs,
                route_prefix=scope["route_prefix"],
            )
            save_routes_to_cache(route_caches[scope_key], routes)
            scope_routes[scope_key] = routes
    else:
        print("Heatmap routes loaded from cache.")
        graph = load_cached_graph_for_render(ox, graph_path, args.cache_dir, bbox)

    scopes = []
    for scope in scope_builders:
        routes = scope_routes[scope["key"]] or []
        routes = select_routes_for_display(routes, max_routes, scope["key"])
        routes = apply_heatmap_route_styles(routes)
        print_summary(scope["stations"], routes, label=scope["label"])
        scopes.append(
            {
                "key": scope["key"],
                "label": scope["label"],
                "button_label": scope["button_label"],
                "stations": scope["stations"],
                "routes": routes,
                "station_scores": scope["station_scores"],
                "stations_label": scope["stations_label"],
                "routes_label": scope["routes_label"],
            }
        )

    return run_heatmap_scope_animation(
        ctx=ctx,
        pygame=pygame,
        screen=screen,
        graph=graph,
        scopes=scopes,
        all_stations=all_stations,
        speed_kmh=args.speed_kmh,
        time_scale=args.time_scale,
        width=args.width,
        height=args.height,
        cache_dir=args.cache_dir,
        refresh_map=args.refresh_map,
        map_zoom=args.map_zoom,
        render_scale=args.render_scale,
        max_real_seconds=args.max_real_seconds,
    )


def run_weekday_weekend_mode(args, pd, pygame, screen, ox, nx, ctx) -> str:
    summary = weekday_weekend_summary(pd, args.cache_dir, top_n=COMPARISON_STATION_COUNT)
    stations_df = load_stations_table(pd)
    weekday_scores_series = station_scores_from_edges(summary["weekday_edges"])
    weekend_scores_series = station_scores_from_edges(summary["weekend_edges"])
    weekday_score_lookup = {str(name): float(score) for name, score in weekday_scores_series.items()}
    weekend_score_lookup = {str(name): float(score) for name, score in weekend_scores_series.items()}

    weekday_stations = stations_from_exact_names(stations_df, summary["weekday_top_names"])
    weekend_stations = stations_from_exact_names(stations_df, summary["weekend_top_names"])
    all_station_names = [str(name) for name in stations_df["station_name"].tolist()]
    all_stations = stations_from_exact_names(stations_df, all_station_names)

    print_top_preview("dni robocze", summary["weekday_top_names"])
    print_top_preview("weekendy", summary["weekend_top_names"])

    union_lookup = {}
    for station in weekday_stations + weekend_stations:
        union_lookup[station.name] = station
    comparison_stations = list(union_lookup.values())

    if len(comparison_stations) < 2:
        raise RuntimeError("Not enough stations to run weekday/weekend comparison.")

    bbox = bbox_around_stations(comparison_stations, args.buffer_meters)
    graph_path = graph_cache_path(args.cache_dir, bbox, comparison_stations)

    weekday_cache = routes_cache_path(
        args.cache_dir,
        weekday_stations,
        graph_path.name,
        cache_label="weekday_without_discontinuities_pairs_v3",
    )
    weekend_cache = routes_cache_path(
        args.cache_dir,
        weekend_stations,
        graph_path.name,
        cache_label="weekend_without_discontinuities_pairs_v3",
    )

    force_rebuild_routes = args.refresh_routes or args.refresh_osm
    weekday_routes = None if force_rebuild_routes else load_routes_from_cache(weekday_cache, weekday_stations)
    weekend_routes = None if force_rebuild_routes else load_routes_from_cache(weekend_cache, weekend_stations)
    graph = None

    if weekday_routes is None or weekend_routes is None:
        graph = load_or_download_graph(
            ox,
            graph_path,
            bbox,
            args.refresh_osm,
        )

        weekday_station_lookup = {}
        for station in weekday_stations:
            weekday_station_lookup[station.name] = station

        weekend_station_lookup = {}
        for station in weekend_stations:
            weekend_station_lookup[station.name] = station

        weekend_weekday_limit = min(args.max_routes, COMPARISON_MAX_ROUTES)
        candidate_limit = max(weekend_weekday_limit * 3, 60)

        node_lookup_cache: dict[str, int] | None = None

        def station_node_lookup() -> dict[str, int]:
            nonlocal node_lookup_cache
            if node_lookup_cache is None:
                union_nodes = nearest_graph_nodes(graph, comparison_stations)
                node_lookup_cache = {}
                for station, node in zip(comparison_stations, union_nodes):
                    node_lookup_cache[station.name] = node
            return node_lookup_cache

        if weekday_routes is None:
            weekday_pairs = top_station_pairs_from_edges(
                summary["weekday_edges"],
                set(weekday_station_lookup),
                candidate_limit,
            )
            weekday_routes = build_routes_from_station_pairs(
                ox,
                nx,
                graph,
                station_lookup=weekday_station_lookup,
                station_node_lookup=station_node_lookup(),
                station_pairs=weekday_pairs,
                route_prefix="Weekday",
            )
            save_routes_to_cache(weekday_cache, weekday_routes)

        if weekend_routes is None:
            weekend_pairs = top_station_pairs_from_edges(
                summary["weekend_edges"],
                set(weekend_station_lookup),
                candidate_limit,
            )
            weekend_routes = build_routes_from_station_pairs(
                ox,
                nx,
                graph,
                station_lookup=weekend_station_lookup,
                station_node_lookup=station_node_lookup(),
                station_pairs=weekend_pairs,
                route_prefix="Weekend",
            )
            save_routes_to_cache(weekend_cache, weekend_routes)
    else:
        print("Weekday and weekend routes loaded from cache.")
        graph = load_cached_graph_for_render(ox, graph_path, args.cache_dir, bbox)

    weekend_weekday_limit = min(args.max_routes, COMPARISON_MAX_ROUTES)
    weekday_routes = select_routes_for_display(weekday_routes, weekend_weekday_limit, "weekday")
    weekend_routes = select_routes_for_display(weekend_routes, weekend_weekday_limit, "weekend")
    weekday_routes = apply_heatmap_route_styles(weekday_routes)
    weekend_routes = apply_heatmap_route_styles(weekend_routes)

    print_summary(weekday_stations, weekday_routes, label="Dni robocze")
    print_summary(weekend_stations, weekend_routes, label="Weekendy")

    return run_weekday_weekend_animation(
        ctx=ctx,
        pygame=pygame,
        screen=screen,
        graph=graph,
        weekday_stations=weekday_stations,
        weekend_stations=weekend_stations,
        weekday_routes=weekday_routes,
        weekend_routes=weekend_routes,
        all_stations=all_stations,
        speed_kmh=args.speed_kmh,
        time_scale=args.time_scale,
        width=args.width,
        height=args.height,
        cache_dir=args.cache_dir,
        refresh_map=args.refresh_map,
        map_zoom=args.map_zoom,
        render_scale=args.render_scale,
        weekday_station_scores=weekday_score_lookup,
        weekend_station_scores=weekend_score_lookup,
        max_real_seconds=args.max_real_seconds,
    )


def main() -> None:
    args = parse_args()

    if args.list_stations:
        pd = require_pandas_module()
        print_station_matches(pd, args.list_stations)
        return

    if args.max_routes < 1:
        raise ValueError("--max-routes must be at least 1.")
    if args.render_scale < 1.0:
        raise ValueError("--render-scale must be at least 1.0.")
    if args.render_scale > MAX_RENDER_SCALE:
        raise ValueError(f"--render-scale must be at most {MAX_RENDER_SCALE}.")

    os.environ.setdefault("SDL_VIDEO_HIGHDPI_DISABLED", "0")
    os.environ.setdefault("SDL_HINT_VIDEO_HIGHDPI_DISABLED", "0")
    pygame = require_pygame_module()
    pygame.init()
    args.width, args.height = window_size_for_screen(pygame, args.width, args.height)
    pygame.display.set_caption("London bike route animation")
    screen = pygame.display.set_mode((args.width, args.height))

    mode = choose_mode(args.mode, pygame, screen, args.width, args.height)
    if mode is None:
        print("Program zamkniety bez wyboru trybu.")
        pygame.quit()
        return

    _, ox, nx, pd, ctx = require_runtime_modules(include_pygame=False)
    while True:
        if mode == "two_years":
            show_loading_screen(
                screen,
                pygame,
                args.width,
                args.height,
                title="Ładowanie animacji ...",
                subtitle="Przygotowuję trasy i mapę Londynu",
            )
        elif mode == "two_years_heatmap":
            show_loading_screen(
                screen,
                pygame,
                args.width,
                args.height,
                title="Ładowanie animacji ...",
                subtitle="Przygotowuję trasy i mapę Londynu",
            )
        elif mode == "weekday_weekend":
            show_loading_screen(
                screen,
                pygame,
                args.width,
                args.height,
                title="Ładowanie animacji ...",
                subtitle="Przygotowuję trasy i mapę Londynu",
            )

        if mode == "two_years":
            exit_action = run_two_year_mode(args, pd, pygame, screen, ox, nx, ctx)
        elif mode == "two_years_heatmap":
            exit_action = run_heatmap_scope_mode(args, pd, pygame, screen, ox, nx, ctx)
        elif mode == "weekday_weekend":
            exit_action = run_heatmap_scope_mode(args, pd, pygame, screen, ox, nx, ctx)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        if exit_action != "menu":
            break

        mode = run_mode_menu(screen, pygame, args.width, args.height)
        if mode is None:
            print("Program zamkniety z menu.")
            break

    pygame.quit()
