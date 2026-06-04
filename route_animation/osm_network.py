from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Station


# OSMnx i NetworkX: pobranie grafu drogowego oraz najkrotsze sciezki.


def load_or_download_graph(
    ox: Any,
    cache_path: Path,
    bbox: tuple[float, float, float, float],
    refresh_osm: bool,
) -> Any:
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not refresh_osm:
        print(f"Loading cached OSM graph: {cache_path}")
        return ox.load_graphml(cache_path)

    print("Downloading OSM bike network for the selected London area...")
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(cache_path.parent / "http_cache")
    ox.settings.log_console = False

    left, bottom, right, top = bbox
    try:
        graph = ox.graph_from_bbox(
            (left, bottom, right, top),
            network_type="bike",
            simplify=True,
            retain_all=False,
            truncate_by_edge=True,
        )
    except TypeError:
        graph = ox.graph_from_bbox(
            top,
            bottom,
            right,
            left,
            network_type="bike",
            simplify=True,
            retain_all=False,
            truncate_by_edge=True,
        )

    ox.save_graphml(graph, cache_path)
    print(f"Saved OSM graph cache: {cache_path}")
    return graph


def nearest_graph_nodes(graph: Any, stations: list[Station]) -> list[int]:
    # OSMnx ma szybkie wyszukiwanie najblizszych wezlow. To jest duzo lzejsze
    # niz porownywanie kazdej stacji z kazdym wezlem grafu w Pythonie.
    try:
        import osmnx as ox

        lon_values = []
        lat_values = []
        for station in stations:
            lon_values.append(station.lon)
            lat_values.append(station.lat)

        nodes = ox.distance.nearest_nodes(graph, lon_values, lat_values)
        return list(nodes)
    except Exception:
        pass

    graph_node_points = []
    for node, data in graph.nodes(data=True):
        graph_node_points.append((node, float(data["x"]), float(data["y"])))

    nearest_nodes = []
    for station in stations:
        nearest_node = min(
            graph_node_points,
            key=lambda item: (item[1] - station.lon) ** 2 + (item[2] - station.lat) ** 2,
        )[0]
        nearest_nodes.append(nearest_node)

    return nearest_nodes


def shortest_path_between_nodes(ox: Any, nx: Any, graph: Any, start_node: int, end_node: int) -> tuple[Any, list[int]]:
    try:
        return graph, nx.shortest_path(graph, start_node, end_node, weight="length")
    except nx.NetworkXNoPath:
        pass

    try:
        reverse_segment = nx.shortest_path(graph, end_node, start_node, weight="length")
        reverse_segment.reverse()
        return graph, reverse_segment
    except nx.NetworkXNoPath:
        # Ostatni fallback bez kopiowania grafu. Taki odcinek bedzie prosty,
        # ale program sie nie wysypie na pamieci przy duzym grafie.
        return graph, [start_node, end_node]


def route_nodes_for_stations(ox: Any, nx: Any, graph: Any, station_nodes: list[int]) -> tuple[Any, list[int]]:
    routing_graph = graph
    route_nodes: list[int] = []

    for start_node, end_node in zip(station_nodes, station_nodes[1:]):
        routing_graph, segment = shortest_path_between_nodes(ox, nx, routing_graph, start_node, end_node)
        route_nodes.extend(segment[1:] if route_nodes else segment)

    return routing_graph, route_nodes


def line_coords_from_edge_data(edge_data: dict[str, Any]) -> list[tuple[float, float]] | None:
    geometry = edge_data.get("geometry")
    if geometry is None:
        return None
    return [(float(lon), float(lat)) for lon, lat in geometry.coords]


def best_edge_data(graph: Any, start_node: int, end_node: int) -> dict[str, Any] | None:
    edge_bundle = graph.get_edge_data(start_node, end_node)
    if edge_bundle is None:
        edge_bundle = graph.get_edge_data(end_node, start_node)
    if edge_bundle is None:
        return None
    if isinstance(edge_bundle, dict) and all(isinstance(value, dict) for value in edge_bundle.values()):
        return min(edge_bundle.values(), key=lambda data: float(data.get("length", 0)))
    return edge_bundle


def route_lonlat_points(graph: Any, route_nodes: list[int]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []

    for start_node, end_node in zip(route_nodes, route_nodes[1:]):
        edge_data = best_edge_data(graph, start_node, end_node)
        coords = line_coords_from_edge_data(edge_data) if edge_data else None
        if coords is None:
            coords = [
                (float(graph.nodes[start_node]["x"]), float(graph.nodes[start_node]["y"])),
                (float(graph.nodes[end_node]["x"]), float(graph.nodes[end_node]["y"])),
            ]

        if points and coords and points[-1] == coords[0]:
            points.extend(coords[1:])
        else:
            points.extend(coords)

    return points


def background_edge_lonlat(graph: Any, limit: int = 18_000) -> list[list[tuple[float, float]]]:
    polylines: list[list[tuple[float, float]]] = []

    for index, (start_node, end_node, _, data) in enumerate(graph.edges(keys=True, data=True)):
        if index >= limit:
            break
        coords = line_coords_from_edge_data(data)
        if coords is None:
            coords = [
                (float(graph.nodes[start_node]["x"]), float(graph.nodes[start_node]["y"])),
                (float(graph.nodes[end_node]["x"]), float(graph.nodes[end_node]["y"])),
            ]
        polylines.append(coords)

    return polylines
