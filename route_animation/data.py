from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from .config import (
    DISTRICT_COLORS,
    EDGES_FILE,
    HEATMAP_COLORS,
    STATIONS_FILE,
    TRIPS_FILE,
    TRIP_DATA_SCOPE_CACHE_LABEL,
    TRIP_DURATION_MINUTES_MAX,
    TRIP_DURATION_MINUTES_MIN,
)
from .models import RouteAnimation, Station


# Dane projektu: stacje i Twoja zbudowana siec przejazdow stacja-stacja.


def load_stations_table(pd: Any) -> Any:
    if not STATIONS_FILE.exists():
        raise FileNotFoundError(f"Station file not found: {STATIONS_FILE}")
    return pd.read_parquet(STATIONS_FILE)


def load_station_network_edges(pd: Any) -> Any:
    if not EDGES_FILE.exists():
        trip_data = load_trip_data(
            pd,
            columns=[
                "start_station_id",
                "start_station_name",
                "end_station_id",
                "end_station_name",
            ],
        )
        edges_df = build_station_network_edges(trip_data)
        edges_df.to_parquet(EDGES_FILE, index=False)
        return edges_df
    return pd.read_parquet(EDGES_FILE)


def load_trip_data(pd: Any, columns: list[str] | None = None) -> Any:
    if not TRIPS_FILE.exists():
        raise FileNotFoundError(f"Trip file not found: {TRIPS_FILE}")

    read_columns = columns
    if columns is not None and "total_duration_minutes" not in columns:
        read_columns = [*columns, "total_duration_minutes"]

    trip_data = pd.read_parquet(TRIPS_FILE, columns=read_columns)
    filtered_trip_data = trip_data.loc[
        trip_data["total_duration_minutes"].between(
            TRIP_DURATION_MINUTES_MIN,
            TRIP_DURATION_MINUTES_MAX,
            inclusive="both",
        )
    ].copy()

    if columns is not None:
        return filtered_trip_data.loc[:, columns]

    return filtered_trip_data


def build_station_network_edges(trip_data: Any) -> Any:
    return (
        trip_data.groupby(
            [
                "start_station_id",
                "start_station_name",
                "end_station_id",
                "end_station_name",
            ]
        )
        .agg(weight=("start_station_id", "count"))
        .reset_index()
    )


def station_key(name: str) -> str:
    return " ".join(name.casefold().replace(",", " , ").split())


def print_station_matches(pd: Any, query: str) -> None:
    stations_df = load_stations_table(pd)
    query_key = station_key(query)
    matches = stations_df[
        stations_df["station_name"].map(lambda name: query_key in station_key(str(name)))
    ].copy()

    if matches.empty:
        print(f"No station names found for query: {query}")
        return

    for row in matches.sort_values("station_name").itertuples(index=False):
        print(f"{row.station_name}  ({row.lat:.6f}, {row.lon:.6f})")


def find_station(stations_df: Any, station_name: str) -> Station:
    target_key = station_key(station_name)
    normalized_names = stations_df["station_name"].map(lambda value: station_key(str(value)))
    matches = stations_df[normalized_names == target_key]

    if matches.empty:
        partial = stations_df[
            stations_df["station_name"].map(lambda value: target_key in station_key(str(value)))
        ]["station_name"].head(10)
        suggestions = "\n".join(f"  - {name}" for name in partial)
        message = f"Station not found: {station_name}"
        if suggestions:
            message += f"\nClosest partial matches:\n{suggestions}"
        raise ValueError(message)

    row = matches.iloc[0]
    return Station(
        station_id=float(row["station_id"]),
        name=str(row["station_name"]),
        lat=float(row["lat"]),
        lon=float(row["lon"]),
    )


def selected_stations(pd: Any, station_names: list[str]) -> list[Station]:
    stations_df = load_stations_table(pd)
    stations = []
    for station_name in station_names:
        stations.append(find_station(stations_df, station_name))
    return stations


def stations_from_exact_names(stations_df: Any, station_names: list[str]) -> list[Station]:
    station_lookup = {}
    for row in stations_df.itertuples(index=False):
        station_lookup[str(row.station_name)] = Station(
            station_id=float(row.station_id),
            name=str(row.station_name),
            lat=float(row.lat),
            lon=float(row.lon),
        )

    stations = []
    for station_name in station_names:
        if station_name in station_lookup:
            stations.append(station_lookup[station_name])

    return stations


def station_scores_from_edges(edges_df: Any) -> Any:
    outgoing = edges_df.groupby("start_station_name")["weight"].sum()
    incoming = edges_df.groupby("end_station_name")["weight"].sum()
    return outgoing.add(incoming, fill_value=0).sort_values(ascending=False)


def station_scores_from_network(pd: Any) -> Any:
    edges_df = load_station_network_edges(pd)
    return station_scores_from_edges(edges_df)


def value_bounds(values: list[float] | tuple[float, ...]) -> tuple[float, float]:
    positive_values = [float(value) for value in values if float(value) > 0]
    if not positive_values:
        return 0.0, 1.0

    min_value = min(positive_values)
    max_value = max(positive_values)
    if max_value <= min_value:
        max_value = min_value + 1.0
    return min_value, max_value


def heatmap_fraction(value: float, min_value: float, max_value: float) -> float:
    low = math.log1p(max(0.0, min_value))
    high = math.log1p(max(0.0, max_value))
    if high <= low:
        return 0.5

    fraction = (math.log1p(max(0.0, value)) - low) / (high - low)
    return max(0.0, min(1.0, fraction))


def heatmap_color_at_fraction(fraction: float) -> tuple[int, int, int]:
    fraction = max(0.0, min(1.0, fraction))
    if len(HEATMAP_COLORS) == 1:
        return HEATMAP_COLORS[0]

    scaled = fraction * (len(HEATMAP_COLORS) - 1)
    left_index = int(math.floor(scaled))
    right_index = min(len(HEATMAP_COLORS) - 1, left_index + 1)
    blend = scaled - left_index
    left_color = HEATMAP_COLORS[left_index]
    right_color = HEATMAP_COLORS[right_index]
    return tuple(
        int(round(left + (right - left) * blend))
        for left, right in zip(left_color, right_color)
    )


def heatmap_color(value: float, min_value: float, max_value: float) -> tuple[int, int, int]:
    return heatmap_color_at_fraction(heatmap_fraction(value, min_value, max_value))


def darker_color(color: tuple[int, int, int], factor: float = 0.58) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(round(channel * factor)))) for channel in color)


def apply_heatmap_route_styles(routes: list[RouteAnimation]) -> list[RouteAnimation]:
    min_weight, max_weight = value_bounds([float(route.station_network_weight) for route in routes])
    styled_routes = []
    for route in routes:
        route_color = heatmap_color(route.station_network_weight, min_weight, max_weight)
        styled_routes.append(
            replace(
                route,
                district_name="Heatmap",
                route_color=route_color,
                bike_color=route_color,
            )
        )
    return styled_routes


def top_stations_from_network(pd: Any, station_count: int) -> list[Station]:
    stations_df = load_stations_table(pd)
    station_scores = station_scores_from_network(pd)
    available_names = set(stations_df["station_name"])

    selected_names = []
    for station_name in station_scores.index:
        if station_name in available_names:
            selected_names.append(station_name)
        if len(selected_names) >= station_count:
            break

    stations = []
    for station_name in selected_names:
        stations.append(find_station(stations_df, station_name))
    return stations


def top_station_pairs_from_edges(
    edges_df: Any,
    allowed_station_names: set[str] | None,
    max_pairs: int,
    directed: bool = False,
) -> list[tuple[str, str, int]]:
    if max_pairs < 1:
        return []

    filtered = edges_df[edges_df["start_station_name"] != edges_df["end_station_name"]].copy()
    if allowed_station_names is not None:
        filtered = filtered[
            filtered["start_station_name"].isin(allowed_station_names)
            & filtered["end_station_name"].isin(allowed_station_names)
        ].copy()

    if filtered.empty:
        return []

    directed_weights = filtered.groupby(["start_station_name", "end_station_name"])["weight"].sum()
    if directed:
        station_pairs: list[tuple[str, str, int]] = []
        for (start_name, end_name), pair_weight in directed_weights.sort_values(ascending=False).head(max_pairs).items():
            station_pairs.append((str(start_name), str(end_name), int(pair_weight)))
        return station_pairs

    start_names = filtered["start_station_name"].astype(str)
    end_names = filtered["end_station_name"].astype(str)
    filtered["pair_a"] = np.where(start_names <= end_names, start_names, end_names)
    filtered["pair_b"] = np.where(start_names <= end_names, end_names, start_names)

    undirected_weights = (
        filtered.groupby(["pair_a", "pair_b"])["weight"]
        .sum()
        .sort_values(ascending=False)
    )

    station_pairs: list[tuple[str, str, int]] = []
    for (name_a, name_b), pair_weight in undirected_weights.head(max_pairs).items():
        forward_weight = float(directed_weights.get((name_a, name_b), 0))
        backward_weight = float(directed_weights.get((name_b, name_a), 0))
        if backward_weight > forward_weight:
            start_name, end_name = name_b, name_a
        else:
            start_name, end_name = name_a, name_b
        station_pairs.append((str(start_name), str(end_name), int(pair_weight)))

    return station_pairs


def day_type_edges_from_trip_data(trip_data: Any, day_type: str) -> Any:
    trip_data = trip_data.copy()

    if not np.issubdtype(trip_data["start_date"].dtype, np.datetime64):
        trip_data["start_date"] = trip_data["start_date"].astype("datetime64[ns]")

    if "start_day_of_week" not in trip_data.columns:
        trip_data["start_day_of_week"] = trip_data["start_date"].dt.day_name()

    if day_type == "weekday":
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    elif day_type == "weekend":
        valid_days = ["Saturday", "Sunday"]
    else:
        raise ValueError(f"Unsupported day type: {day_type}")

    filtered = trip_data[trip_data["start_day_of_week"].isin(valid_days)]
    edges_df = (
        filtered.groupby(["start_station_name", "end_station_name"])
        .size()
        .reset_index(name="weight")
    )
    return edges_df


def stationary_top_station_names(edges_df: Any, top_n: int) -> list[str]:
    station_names = sorted(
        set(edges_df["start_station_name"]).union(set(edges_df["end_station_name"]))
    )
    station_to_index = {name: index for index, name in enumerate(station_names)}

    matrix_size = len(station_names)
    transition_counts = np.zeros((matrix_size, matrix_size), dtype=np.float64)

    for row in edges_df.itertuples(index=False):
        start_name = str(row.start_station_name)
        end_name = str(row.end_station_name)
        transition_counts[station_to_index[start_name], station_to_index[end_name]] += float(row.weight)

    row_sums = transition_counts.sum(axis=1, keepdims=True)
    zero_rows = row_sums[:, 0] == 0
    for zero_index in np.where(zero_rows)[0]:
        transition_counts[zero_index, zero_index] = 1.0
        row_sums[zero_index, 0] = 1.0

    transition_matrix = transition_counts / row_sums
    probabilities = np.full(matrix_size, 1.0 / matrix_size, dtype=np.float64)

    for _ in range(5000):
        next_probabilities = probabilities @ transition_matrix
        if np.linalg.norm(next_probabilities - probabilities, ord=1) < 1e-12:
            probabilities = next_probabilities
            break
        probabilities = next_probabilities

    sorted_indices = np.argsort(probabilities)[::-1]
    top_station_names = []
    for index in sorted_indices[:top_n]:
        top_station_names.append(station_names[int(index)])
    return top_station_names


def weekday_weekend_summary(pd: Any, cache_dir: Path, top_n: int) -> dict[str, Any]:
    summary_dir = cache_dir / f"weekday_weekend_{TRIPS_FILE.stem}_{TRIP_DATA_SCOPE_CACHE_LABEL}"
    summary_dir.mkdir(parents=True, exist_ok=True)

    weekday_edges_path = summary_dir / "edges_weekday.parquet"
    weekend_edges_path = summary_dir / "edges_weekend.parquet"
    ranking_path = summary_dir / "stationary_ranking.json"

    if weekday_edges_path.exists() and weekend_edges_path.exists():
        weekday_edges = pd.read_parquet(weekday_edges_path)
        weekend_edges = pd.read_parquet(weekend_edges_path)
    else:
        trip_data = load_trip_data(
            pd,
            columns=["start_date", "start_station_name", "end_station_name"],
        )
        weekday_edges = day_type_edges_from_trip_data(trip_data, "weekday")
        weekend_edges = day_type_edges_from_trip_data(trip_data, "weekend")
        weekday_edges.to_parquet(weekday_edges_path, index=False)
        weekend_edges.to_parquet(weekend_edges_path, index=False)

    if ranking_path.exists():
        with ranking_path.open("r", encoding="utf-8") as file:
            ranking_payload = json.load(file)
        weekday_ranking = ranking_payload["weekday"]
        weekend_ranking = ranking_payload["weekend"]
    else:
        weekday_ranking = stationary_top_station_names(weekday_edges, top_n=801)
        weekend_ranking = stationary_top_station_names(weekend_edges, top_n=801)
        ranking_payload = {"weekday": weekday_ranking, "weekend": weekend_ranking}
        with ranking_path.open("w", encoding="utf-8") as file:
            json.dump(ranking_payload, file)

    return {
        "weekday_edges": weekday_edges,
        "weekend_edges": weekend_edges,
        "weekday_top_names": weekday_ranking[:top_n],
        "weekend_top_names": weekend_ranking[:top_n],
    }


def route_district(route_stations: list[Station]) -> str:
    lon_sum = 0.0
    lat_sum = 0.0

    for station in route_stations:
        lon_sum += station.lon
        lat_sum += station.lat

    avg_lon = lon_sum / len(route_stations)
    avg_lat = lat_sum / len(route_stations)

    # To jest lekki podzial na obszary, nie oficjalne granice dzielnic.
    london_lon = -0.1276
    london_lat = 51.5072
    lon_diff = (avg_lon - london_lon) * 0.62
    lat_diff = avg_lat - london_lat

    center_threshold = 0.018
    diagonal_threshold = 0.012

    if abs(lon_diff) < center_threshold and abs(lat_diff) < center_threshold:
        return "Centrum"

    if lat_diff > diagonal_threshold and lon_diff > diagonal_threshold:
        return "Polnocny Wschod"
    if lat_diff > diagonal_threshold and lon_diff < -diagonal_threshold:
        return "Polnocny Zachod"
    if lat_diff < -diagonal_threshold and lon_diff > diagonal_threshold:
        return "Poludniowy Wschod"
    if lat_diff < -diagonal_threshold and lon_diff < -diagonal_threshold:
        return "Poludniowy Zachod"

    if abs(lat_diff) > abs(lon_diff):
        if lat_diff > 0:
            return "Polnoc"
        return "Poludnie"
    if lon_diff > 0:
        return "Wschod"
    return "Zachod"


def route_style(route_index: int, district_name: str) -> dict[str, Any]:
    if district_name not in DISTRICT_COLORS:
        district_name = "Centrum"

    route_color, bike_color = DISTRICT_COLORS[district_name]
    return {
        "name": f"Trasa {route_index + 1}",
        "district_name": district_name,
        "route_color": route_color,
        "bike_color": bike_color,
    }
