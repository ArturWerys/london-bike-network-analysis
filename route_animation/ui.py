from typing import Any

from .config import (
    DISTRICT_COLORS,
    DISTRICT_ORDER,
    STATION_COLOR,
    STATION_OUTLINE,
    TEXT_COLOR,
    WHITE,
)
from .models import RouteAnimation, Station


# Proste elementy UI pygame: menu, panele i przyciski.


def draw_text(surface: Any, font: Any, text: str, position: tuple[int, int], color: tuple[int, int, int]) -> None:
    image = font.render(text, True, color)
    surface.blit(image, position)


def draw_mode_menu_background(screen: Any, pygame: Any, width: int, height: int) -> None:
    for y in range(height):
        blend = y / max(height - 1, 1)
        color = (
            int(238 + 7 * blend),
            int(241 + 7 * blend),
            int(244 + 5 * blend),
        )
        pygame.draw.line(screen, color, (0, y), (width, y))


def run_mode_menu(screen: Any, pygame: Any, width: int, height: int) -> str | None:
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("segoeui", 44, bold=True) or pygame.font.Font(None, 44)
    subtitle_font = pygame.font.SysFont("segoeui", 22) or pygame.font.Font(None, 22)
    button_title_font = pygame.font.SysFont("segoeui", 30, bold=True) or pygame.font.Font(None, 30)
    button_text_font = pygame.font.SysFont("segoeui", 18) or pygame.font.Font(None, 18)

    options = [
        {
            "mode": "two_years",
            "title": "1. Animacja przejazdów z pełnego okresu 2 lat",
            "text": "Dane z lat 2024-2025, jedna ciagla animacja tras.",
            "color": (42, 130, 128),
        },
        {
            "mode": "weekday_weekend",
            "title": "2. Dni robocze vs weekend",
            "text": "Porównanie danych z dni roboczych i weekendów.",
            "color": (184, 83, 101),
        },
    ]

    button_width = min(920, width - 180)
    button_height = 124
    start_x = (width - button_width) // 2
    start_y = max(240, (height - (button_height * 2 + 24)) // 2)
    buttons = [
        pygame.Rect(start_x, start_y, button_width, button_height),
        pygame.Rect(start_x, start_y + button_height + 24, button_width, button_height),
    ]

    selected_index = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None

            if event.type == pygame.KEYDOWN:
                if event.key in {pygame.K_1, pygame.K_KP1}:
                    return "two_years"
                if event.key in {pygame.K_2, pygame.K_KP2}:
                    return "weekday_weekend"
                if event.key in {pygame.K_UP, pygame.K_w}:
                    selected_index = max(0, selected_index - 1)
                if event.key in {pygame.K_DOWN, pygame.K_s}:
                    selected_index = min(len(options) - 1, selected_index + 1)
                if event.key in {pygame.K_RETURN, pygame.K_KP_ENTER}:
                    return options[selected_index]["mode"]
                if event.key in {pygame.K_ESCAPE, pygame.K_q}:
                    return None

            if event.type == pygame.MOUSEMOTION:
                for index, rect in enumerate(buttons):
                    if rect.collidepoint(event.pos):
                        selected_index = index

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for index, rect in enumerate(buttons):
                    if rect.collidepoint(event.pos):
                        return options[index]["mode"]

        draw_mode_menu_background(screen, pygame, width, height)

        title_image = title_font.render("Wybierz tryb animacji", True, TEXT_COLOR)
        title_rect = title_image.get_rect(center=(width // 2, 88))
        screen.blit(title_image, title_rect)

        subtitle_image = subtitle_font.render("Kliknij przycisk albo nacisnij klawisz 1/2", True, (88, 98, 108))
        subtitle_rect = subtitle_image.get_rect(center=(width // 2, 132))
        screen.blit(subtitle_image, subtitle_rect)

        for index, rect in enumerate(buttons):
            option = options[index]
            is_selected = index == selected_index
            fill_color = (255, 255, 255) if not is_selected else (245, 250, 252)
            border_color = (194, 202, 210) if not is_selected else option["color"]

            pygame.draw.rect(screen, fill_color, rect, border_radius=10)
            pygame.draw.rect(screen, border_color, rect, 2, border_radius=10)
            pygame.draw.rect(
                screen,
                option["color"],
                (rect.x + 16, rect.y + 18, 8, rect.height - 36),
                border_radius=4,
            )

            title = button_title_font.render(option["title"], True, TEXT_COLOR)
            text = button_text_font.render(option["text"], True, (82, 92, 102))
            screen.blit(title, (rect.x + 40, rect.y + 24))
            screen.blit(text, (rect.x + 40, rect.y + 68))

        footer = button_text_font.render("Esc lub Q: zamknij program", True, (100, 108, 116))
        screen.blit(footer, footer.get_rect(center=(width // 2, height - 36)))
        pygame.display.flip()
        clock.tick(60)


def show_loading_screen(
    screen: Any,
    pygame: Any,
    width: int,
    height: int,
    title: str = "Ladowanie...",
    subtitle: str = "Przygotowuje mape i trasy",
) -> None:
    draw_mode_menu_background(screen, pygame, width, height)
    title_font = pygame.font.SysFont("segoeui", 52, bold=True) or pygame.font.Font(None, 52)
    subtitle_font = pygame.font.SysFont("segoeui", 24) or pygame.font.Font(None, 24)

    title_image = title_font.render(title, True, TEXT_COLOR)
    subtitle_image = subtitle_font.render(subtitle, True, (88, 98, 108))
    screen.blit(title_image, title_image.get_rect(center=(width // 2, height // 2 - 22)))
    screen.blit(subtitle_image, subtitle_image.get_rect(center=(width // 2, height // 2 + 28)))

    pygame.display.flip()
    pygame.event.pump()


def route_counts_by_district(routes: list[RouteAnimation]) -> dict[str, int]:
    counts = {}
    for route in routes:
        counts[route.district_name] = counts.get(route.district_name, 0) + 1
    return counts


def pause_button_rect(pygame: Any, panel_x: int, panel_width: int, height: int) -> Any:
    return pygame.Rect(panel_x + 24, height - 76, panel_width - 48, 44)


def menu_button_rect(pygame: Any, panel_x: int, panel_width: int, height: int) -> Any:
    return pygame.Rect(panel_x + 24, height - 126, panel_width - 48, 44)


def toggle_stage_button_rect(pygame: Any, panel_x: int, panel_width: int, height: int) -> Any:
    return pygame.Rect(panel_x + 24, height - 176, panel_width - 48, 44)


def draw_button(
    pygame: Any,
    screen: Any,
    rect: Any,
    label: str,
    font: Any,
    fill_color: tuple[int, int, int] = (245, 248, 250),
    border_color: tuple[int, int, int] = (176, 184, 190),
) -> None:
    pygame.draw.rect(screen, fill_color, rect, border_radius=8)
    pygame.draw.rect(screen, border_color, rect, 2, border_radius=8)
    label_image = font.render(label, True, TEXT_COLOR)
    screen.blit(label_image, label_image.get_rect(center=rect.center))


def draw_pause_button(pygame: Any, screen: Any, font: Any, paused: bool, panel_x: int, panel_width: int, height: int) -> None:
    rect = pause_button_rect(pygame, panel_x, panel_width, height)
    if paused:
        draw_button(
            pygame,
            screen,
            rect,
            "Wznow",
            font,
            fill_color=(229, 244, 242),
            border_color=(46, 150, 140),
        )
    else:
        draw_button(pygame, screen, rect, "Pauza", font)


def draw_menu_button(pygame: Any, screen: Any, font: Any, panel_x: int, panel_width: int, height: int) -> None:
    draw_button(
        pygame,
        screen,
        menu_button_rect(pygame, panel_x, panel_width, height),
        "Menu",
        font,
    )


def draw_toggle_stage_button(
    pygame: Any,
    screen: Any,
    font: Any,
    panel_x: int,
    panel_width: int,
    height: int,
    active_stage: str,
) -> None:
    if active_stage == "weekday":
        label = "Pokaz weekend"
    else:
        label = "Pokaz weekday"
    draw_button(
        pygame,
        screen,
        toggle_stage_button_rect(pygame, panel_x, panel_width, height),
        label,
        font,
        fill_color=(236, 243, 250),
        border_color=(126, 155, 186),
    )


def draw_pause_badge(pygame: Any, screen: Any, title_font: Any, width: int) -> None:
    pause_image = title_font.render("PAUZA", True, TEXT_COLOR)
    pause_rect = pause_image.get_rect(center=(width // 2, 44)).inflate(26, 14)
    pause_panel = pygame.Surface(pause_rect.size, pygame.SRCALPHA)
    pause_panel.fill((255, 255, 255, 226))
    pygame.draw.rect(pause_panel, (185, 190, 196, 240), pause_panel.get_rect(), 1, border_radius=8)
    screen.blit(pause_panel, pause_rect.topleft)
    screen.blit(pause_image, pause_image.get_rect(center=pause_rect.center))


def draw_stage_badge(pygame: Any, screen: Any, title_font: Any, width: int, stage_title: str) -> None:
    stage_title_image = title_font.render(stage_title, True, TEXT_COLOR)
    stage_title_rect = stage_title_image.get_rect(midtop=(width // 2, 14)).inflate(24, 12)
    stage_panel = pygame.Surface(stage_title_rect.size, pygame.SRCALPHA)
    stage_panel.fill((255, 255, 255, 220))
    pygame.draw.rect(stage_panel, (185, 190, 196, 230), stage_panel.get_rect(), 1, border_radius=8)
    screen.blit(stage_panel, stage_title_rect.topleft)
    screen.blit(stage_title_image, stage_title_image.get_rect(center=stage_title_rect.center))


def draw_attribution(pygame: Any, screen: Any, small_font: Any, map_width: int, height: int) -> None:
    attribution = "(c) OpenStreetMap contributors (c) CARTO"
    attribution_image = small_font.render(attribution, True, TEXT_COLOR)
    attribution_rect = attribution_image.get_rect(bottomright=(map_width - 18, height - 14)).inflate(10, 6)
    attribution_panel = pygame.Surface(attribution_rect.size, pygame.SRCALPHA)
    attribution_panel.fill((255, 255, 255, 196))
    screen.blit(attribution_panel, attribution_rect.topleft)
    screen.blit(attribution_image, attribution_image.get_rect(center=attribution_rect.center))


def draw_info_panel(
    pygame: Any,
    screen: Any,
    font: Any,
    title_font: Any,
    routes: list[RouteAnimation],
    prepared_routes: list[dict[str, Any]],
    stations: list[Station],
    speed_kmh: float,
    time_scale: float,
    panel_x: int,
    panel_width: int,
    height: int,
) -> None:
    panel_rect = pygame.Rect(panel_x, 0, panel_width, height)
    pygame.draw.rect(screen, (247, 249, 250), panel_rect)
    pygame.draw.line(screen, (205, 211, 216), (panel_x, 0), (panel_x, height), 1)

    x = panel_x + 24
    y = 26
    draw_text(screen, title_font, "London bike routes", (x, y), TEXT_COLOR)
    y += 42

    total_route_m = 0.0
    for prepared_route in prepared_routes:
        total_route_m += prepared_route["total_distance_m"]

    total_station_trips = 0
    for route in routes:
        total_station_trips += route.station_network_weight

    total_route_km = total_route_m / 1000
    average_route_km = total_route_km / max(len(prepared_routes), 1)
    info_lines = [
        f"Stacje: {len(stations)}",
        f"Trasy: {len(routes)}",
        f"Rowerzysci: {len(routes)}",
        f"Laczna dlugosc: {total_route_km:.0f} km",
        f"Srednia trasa: {average_route_km:.1f} km",
        f"Ruch w sieci: {total_station_trips:,}".replace(",", " "),
        f"Predkosc: {speed_kmh:.1f} km/h",
        f"Skala czasu: x{time_scale:.0f}",
    ]
    for line in info_lines:
        draw_text(screen, font, line, (x, y), TEXT_COLOR)
        y += 25

    y += 16
    draw_text(screen, title_font, "Legenda", (x, y), TEXT_COLOR)
    y += 38

    route_counts = route_counts_by_district(routes)
    for district_name in DISTRICT_ORDER:
        route_count = route_counts.get(district_name, 0)
        if route_count == 0:
            continue

        route_color, bike_color = DISTRICT_COLORS[district_name]
        pygame.draw.line(screen, route_color, (x, y + 10), (x + 48, y + 10), 4)
        pygame.draw.circle(screen, bike_color, (x + 68, y + 10), 6)
        draw_text(screen, font, f"{district_name}: {route_count} tras", (x + 88, y), TEXT_COLOR)
        y += 30

    y += 16
    pygame.draw.circle(screen, WHITE, (x + 8, y + 10), 6)
    pygame.draw.circle(screen, STATION_COLOR, (x + 8, y + 10), 5)
    pygame.draw.circle(screen, STATION_OUTLINE, (x + 8, y + 10), 5, 1)
    draw_text(screen, font, "Stacje i klastry stacji", (x + 28, y), TEXT_COLOR)

    y += 44
    draw_text(screen, font, "Kolory oznaczaja obszar", (x, y), TEXT_COLOR)
    y += 24
    draw_text(screen, font, "trasy, a nie pojedyncza", (x, y), TEXT_COLOR)
    y += 24
    draw_text(screen, font, "losowa trase.", (x, y), TEXT_COLOR)

    y = height - 134
    draw_text(screen, font, "M lub przycisk: menu", (x, y), TEXT_COLOR)
    y += 24
    draw_text(screen, font, "Spacja lub przycisk: pauza", (x, y), TEXT_COLOR)
    draw_text(screen, font, "Esc / Q: zamknij", (x, y + 24), TEXT_COLOR)


def draw_weekday_weekend_panel(
    pygame: Any,
    screen: Any,
    font: Any,
    title_font: Any,
    weekday_routes: list[RouteAnimation],
    weekend_routes: list[RouteAnimation],
    weekday_stations: list[Station],
    weekend_stations: list[Station],
    active_stage: str,
    speed_kmh: float,
    time_scale: float,
    panel_x: int,
    panel_width: int,
    height: int,
) -> None:
    panel_rect = pygame.Rect(panel_x, 0, panel_width, height)
    pygame.draw.rect(screen, (247, 249, 250), panel_rect)
    pygame.draw.line(screen, (205, 211, 216), (panel_x, 0), (panel_x, height), 1)

    x = panel_x + 24
    y = 26
    draw_text(screen, title_font, "Weekday vs weekend", (x, y), TEXT_COLOR)
    y += 40

    if active_stage == "weekday":
        stage_label = "Aktualnie: dni robocze"
    else:
        stage_label = "Aktualnie: weekendy"
    draw_text(screen, font, stage_label, (x, y), TEXT_COLOR)
    y += 30

    info_lines = [
        f"Weekday stacje: {len(weekday_stations)}",
        f"Weekday trasy: {len(weekday_routes)}",
        f"Weekend stacje: {len(weekend_stations)}",
        f"Weekend trasy: {len(weekend_routes)}",
        f"Predkosc: {speed_kmh:.1f} km/h",
        f"Skala czasu: x{time_scale:.0f}",
        "Przelaczanie: TAB/T lub przycisk",
    ]
    for line in info_lines:
        draw_text(screen, font, line, (x, y), TEXT_COLOR)
        y += 24

    y += 12
    draw_text(screen, title_font, "Legenda", (x, y), TEXT_COLOR)
    y += 36

    active_routes = weekday_routes if active_stage == "weekday" else weekend_routes
    route_counts = route_counts_by_district(active_routes)
    for district_name in DISTRICT_ORDER:
        route_count = route_counts.get(district_name, 0)
        if route_count == 0:
            continue

        route_color, bike_color = DISTRICT_COLORS[district_name]
        pygame.draw.line(screen, route_color, (x, y + 10), (x + 48, y + 10), 4)
        pygame.draw.circle(screen, bike_color, (x + 68, y + 10), 6)
        draw_text(screen, font, f"{district_name}: {route_count} tras", (x + 88, y), TEXT_COLOR)
        y += 30

    y += 14
    pygame.draw.circle(screen, WHITE, (x + 8, y + 10), 6)
    pygame.draw.circle(screen, STATION_COLOR, (x + 8, y + 10), 5)
    pygame.draw.circle(screen, STATION_OUTLINE, (x + 8, y + 10), 5, 1)
    draw_text(screen, font, "Stacje i klastry stacji", (x + 28, y), TEXT_COLOR)

    y += 10
    draw_text(screen, title_font, "Top stacje weekday", (x, y), TEXT_COLOR)
    y += 34
    for station in weekday_stations[:6]:
        station_label = station.name
        if len(station_label) > 34:
            station_label = station_label[:31] + "..."
        draw_text(screen, font, f"- {station_label}", (x, y), TEXT_COLOR)
        y += 22

    y += 8
    draw_text(screen, title_font, "Top stacje weekend", (x, y), TEXT_COLOR)
    y += 34
    for station in weekend_stations[:6]:
        station_label = station.name
        if len(station_label) > 34:
            station_label = station_label[:31] + "..."
        draw_text(screen, font, f"- {station_label}", (x, y), TEXT_COLOR)
        y += 22

    y = height - 134
    draw_text(screen, font, "M lub przycisk: menu", (x, y), TEXT_COLOR)
    y += 24
    draw_text(screen, font, "Spacja lub przycisk: pauza", (x, y), TEXT_COLOR)
    draw_text(screen, font, "Esc / Q: zamknij", (x, y + 24), TEXT_COLOR)
