import json
import os

from .animation import run_animation, run_weekday_weekend_animation
from .cache import graph_cache_path, routes_cache_path
from .cli import parse_args
from .config import (
    COMPARISON_MAX_ROUTES,
    COMPARISON_STATION_COUNT,
)
from .data import (
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


def choose_mode(selected_mode: str | None, pygame, screen, width: int, height: int) -> str | None:
    if selected_mode is not None:
        return selected_mode

    if os.environ.get("SDL_VIDEODRIVER", "").lower() == "dummy":
        print("No interactive input detected, default mode: two_years")
        return "two_years"

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


def run_two_year_mode(args, pd, pygame, screen, ox, nx, ctx) -> str:
    if args.stations:
        if len(args.stations) < 2:
            raise ValueError("--stations must contain at least two station names.")
        stations = selected_stations(pd, args.stations)
    else:
        if args.station_count < 2:
            raise ValueError("--station-count must be at least 2.")
        stations = top_stations_from_network(pd, args.station_count)

    station_lookup = {}
    for station in stations:
        station_lookup[station.name] = station

    bbox = bbox_around_stations(stations, args.buffer_meters)
    graph_path = graph_cache_path(args.cache_dir, bbox, stations)
    route_cache = routes_cache_path(
        args.cache_dir,
        stations,
        2,
        graph_path.name,
        cache_label="two_years_pairs_v1",
    )
    force_rebuild_routes = args.refresh_routes or args.refresh_osm
    routes = None if force_rebuild_routes else load_routes_from_cache(route_cache, stations)
    graph = None

    station_score_lookup = None

    if routes is None:
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

        candidate_limit = max(args.max_routes * 3, 60)
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
        print("Routes loaded from cache. Skipping OSM graph load.")
        edges_df = load_station_network_edges(pd)
        station_scores = station_scores_from_edges(edges_df)
        station_score_lookup = {str(name): float(score) for name, score in station_scores.items()}

    routes = select_routes_for_display(routes, args.max_routes, "two_years")

    print_summary(stations, routes, label="Animacja 2 lata")

    return run_animation(
        ctx=ctx,
        pygame=pygame,
        screen=screen,
        graph=graph,
        stations=stations,
        routes=routes,
        speed_kmh=args.speed_kmh,
        time_scale=args.time_scale,
        width=args.width,
        height=args.height,
        cache_dir=args.cache_dir,
        refresh_map=args.refresh_map,
        map_zoom=args.map_zoom,
        station_scores=station_score_lookup,
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
        2,
        graph_path.name,
        cache_label="weekday_pairs_v1",
    )
    weekend_cache = routes_cache_path(
        args.cache_dir,
        weekend_stations,
        2,
        graph_path.name,
        cache_label="weekend_pairs_v1",
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
        print("Weekday and weekend routes loaded from cache. Skipping OSM graph load.")

    weekend_weekday_limit = min(args.max_routes, COMPARISON_MAX_ROUTES)
    weekday_routes = select_routes_for_display(weekday_routes, weekend_weekday_limit, "weekday")
    weekend_routes = select_routes_for_display(weekend_routes, weekend_weekday_limit, "weekend")

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
        speed_kmh=args.speed_kmh,
        time_scale=args.time_scale,
        width=args.width,
        height=args.height,
        cache_dir=args.cache_dir,
        refresh_map=args.refresh_map,
        map_zoom=args.map_zoom,
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

    pygame = require_pygame_module()
    pygame.init()
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
                title="Ladowanie 2 lata...",
                subtitle="Przygotowuje trasy i mape Londynu",
            )
        elif mode == "weekday_weekend":
            show_loading_screen(
                screen,
                pygame,
                args.width,
                args.height,
                title="Ladowanie weekday/weekend...",
                subtitle="Przygotowuje porownanie i mape Londynu",
            )

        if mode == "two_years":
            exit_action = run_two_year_mode(args, pd, pygame, screen, ox, nx, ctx)
        elif mode == "weekday_weekend":
            exit_action = run_weekday_weekend_mode(args, pd, pygame, screen, ox, nx, ctx)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        if exit_action != "menu":
            break

        mode = run_mode_menu(screen, pygame, args.width, args.height)
        if mode is None:
            print("Program zamkniety z menu.")
            break

    pygame.quit()
