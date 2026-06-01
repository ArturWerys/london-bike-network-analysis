from dataclasses import dataclass


# Modele danych uzywane wspolnie przez routing i pygame.


@dataclass(frozen=True)
class Station:
    station_id: float
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RouteAnimation:
    name: str
    stations: list[Station]
    route_nodes: list[int]
    points_lonlat: list[tuple[float, float]]
    district_name: str
    route_color: tuple[int, int, int]
    bike_color: tuple[int, int, int]
    station_network_weight: int
