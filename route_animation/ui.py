from __future__ import annotations

from typing import Any

from .config import (
    DISTRICT_COLORS,
    DISTRICT_ORDER,
    SIDE_PANEL_WIDTH,
    TEXT_COLOR,
    UI_MAX_SCALE,
    UI_MIN_SCALE,
    UI_REFERENCE_HEIGHT,
    UI_REFERENCE_WIDTH,
    WHITE,
)
from .data import route_district
from .models import RouteAnimation, Station


# Proste elementy UI pygame: menu, panele i przyciski.

DISTRICT_LABELS = {
    "Centrum": "Centrum",
    "Polnoc": "Północ",
    "Polnocny Wschod": "Północny Wschód",
    "Wschod": "Wschód",
    "Poludniowy Wschod": "Południowy Wschód",
    "Poludnie": "Południe",
    "Poludniowy Zachod": "Południowy Zachód",
    "Zachod": "Zachód",
    "Polnocny Zachod": "Północny Zachód",
}


def ui_scale(width: int, height: int) -> float:
    raw_scale = min(width / UI_REFERENCE_WIDTH, height / UI_REFERENCE_HEIGHT)
    return max(UI_MIN_SCALE, min(UI_MAX_SCALE, raw_scale))


def scale_px(value: int | float, scale: float, minimum: int = 1) -> int:
    return max(minimum, int(round(value * scale)))


def scaled_font(
    pygame: Any,
    size: int,
    scale: float,
    *,
    bold: bool = False,
    min_size: int = 12,
) -> Any:
    font_size = scale_px(size, scale, min_size)
    return pygame.font.SysFont("segoeui", font_size, bold=bold) or pygame.font.Font(None, font_size)


def panel_width_for_window(width: int, scale: float) -> int:
    desired_width = scale_px(SIDE_PANEL_WIDTH, scale, 280)
    compact_limit = max(scale_px(260, scale, 220), width // 3)
    return min(desired_width, compact_limit)


def fit_text_to_width(font: Any, text: str, max_width: int) -> str:
    if font.size(text)[0] <= max_width:
        return text

    suffix = "..."
    available_width = max_width - font.size(suffix)[0]
    if available_width <= 0:
        return suffix

    clipped = text
    while clipped and font.size(clipped)[0] > available_width:
        clipped = clipped[:-1]
    return clipped.rstrip() + suffix


def draw_scrollbar(
    pygame: Any,
    screen: Any,
    panel_x: int,
    panel_width: int,
    viewport_top: int,
    viewport_height: int,
    content_height: int,
    scroll: int,
    scale: float,
) -> None:
    if content_height <= viewport_height:
        return

    margin = scale_px(8, scale, 6)
    track_width = scale_px(5, scale, 4)
    track = pygame.Rect(
        panel_x + panel_width - margin - track_width,
        viewport_top + margin,
        track_width,
        max(1, viewport_height - margin * 2),
    )
    thumb_height = max(scale_px(34, scale, 28), int(track.height * viewport_height / content_height))
    scroll_range = max(1, content_height - viewport_height)
    thumb_y = track.y + int((track.height - thumb_height) * scroll / scroll_range)
    thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_height)

    pygame.draw.rect(screen, (224, 230, 235), track, border_radius=scale_px(3, scale, 2))
    pygame.draw.rect(screen, (132, 145, 156), thumb, border_radius=scale_px(3, scale, 2))


def blit_scrollable_panel_content(
    pygame: Any,
    screen: Any,
    content: Any,
    panel_x: int,
    panel_width: int,
    viewport_top: int,
    viewport_height: int,
    content_height: int,
    scroll: int,
    scale: float,
) -> int:
    max_scroll = max(0, content_height - viewport_height)
    scroll = max(0, min(scroll, max_scroll))
    visible_height = min(viewport_height, max(0, content_height - scroll))
    if visible_height > 0:
        area = pygame.Rect(0, scroll, panel_width, visible_height)
        screen.blit(content, (panel_x, viewport_top), area)

    draw_scrollbar(
        pygame,
        screen,
        panel_x,
        panel_width,
        viewport_top,
        viewport_height,
        content_height,
        scroll,
        scale,
    )
    return max_scroll


def draw_text(surface: Any, font: Any, text: str, position: tuple[int, int], color: tuple[int, int, int]) -> None:
    image = font.render(text, True, color)
    surface.blit(image, position)


def district_label(district_name: str) -> str:
    return DISTRICT_LABELS.get(district_name, district_name)


def draw_legend_description(
    content: Any,
    font: Any,
    x: int,
    y: int,
    text_width: int,
    scale: float,
) -> int:
    lines = [
        "Kolor odpowiada części miasta,",
        "w której znajduje się stacja.",
        "Liczba mówi o ich ilości.",
    ]
    for line in lines:
        draw_text(content, font, fit_text_to_width(font, line, text_width), (x, y), TEXT_COLOR)
        y += scale_px(23, scale, 19)
    return y


def draw_mode_menu_background(screen: Any, pygame: Any, width: int, height: int) -> None:
    for y in range(height):
        blend = y / max(height - 1, 1)
        color = (
            int(238 + 7 * blend),
            int(241 + 7 * blend),
            int(244 + 5 * blend),
        )
        pygame.draw.line(screen, color, (0, y), (width, y))


def draw_mode_menu_instructions(
    screen: Any,
    pygame: Any,
    width: int,
    height: int,
    scale: float,
    title_font: Any,
    text_font: Any,
) -> Any:
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((35, 42, 50, 72))
    screen.blit(overlay, (0, 0))

    panel_width = min(scale_px(720, scale, 520), width - scale_px(80, scale, 36))
    panel_height = scale_px(300, scale, 245)
    panel = pygame.Rect(
        (width - panel_width) // 2,
        (height - panel_height) // 2,
        panel_width,
        panel_height,
    )
    pygame.draw.rect(screen, WHITE, panel, border_radius=scale_px(10, scale, 7))
    pygame.draw.rect(screen, (184, 194, 204), panel, scale_px(2, scale, 1), border_radius=scale_px(10, scale, 7))

    x = panel.x + scale_px(30, scale, 22)
    y = panel.y + scale_px(26, scale, 20)
    title_image = title_font.render("Klawisze", True, TEXT_COLOR)
    screen.blit(title_image, (x, y))
    y += scale_px(54, scale, 42)

    lines = [
        "M lub przycisk Menu - powrót do menu",
        "Spacja lub przycisk Pauza - zatrzymanie/wznowienie animacji",
        "Esc lub Q - zamknięcie programu",
        "T lub TAB - zmiana widoku w trybie Dni tygodnia vs weekendy",
    ]
    text_width = panel.width - scale_px(60, scale, 44)
    for line in lines:
        text = text_font.render(fit_text_to_width(text_font, line, text_width), True, TEXT_COLOR)
        screen.blit(text, (x, y))
        y += scale_px(26, scale, 22)

    close_rect = pygame.Rect(
        panel.right - scale_px(150, scale, 118),
        panel.bottom - scale_px(58, scale, 48),
        scale_px(120, scale, 96),
        scale_px(38, scale, 32),
    )
    pygame.draw.rect(screen, (245, 248, 250), close_rect, border_radius=scale_px(8, scale, 6))
    pygame.draw.rect(screen, (176, 184, 190), close_rect, scale_px(2, scale, 1), border_radius=scale_px(8, scale, 6))
    close_image = text_font.render("Zamknij", True, TEXT_COLOR)
    screen.blit(close_image, close_image.get_rect(center=close_rect.center))
    return close_rect


def run_mode_menu(screen: Any, pygame: Any, width: int, height: int) -> str | None:
    clock = pygame.time.Clock()
    scale = ui_scale(width, height)
    title_font = scaled_font(pygame, 44, scale, bold=True, min_size=30)
    subtitle_font = scaled_font(pygame, 22, scale, min_size=16)
    button_title_font = scaled_font(pygame, 30, scale, bold=True, min_size=20)
    button_text_font = scaled_font(pygame, 18, scale, min_size=15)

    options = [
        {
            "mode": "two_years",
            "title": "1. Animacja przejazdów z pełnego okresu 2 lat",
            "color": (42, 130, 128),
        },
        {
            "mode": "weekday_weekend",
            "title": "2. Dni tygodnia vs weekendy",
            "color": (184, 83, 101),
        },
    ]

    side_margin = scale_px(90, scale, 32)
    button_width = min(scale_px(920, scale, 600), width - side_margin * 2)
    button_height = scale_px(124, scale, 92)
    button_gap = scale_px(24, scale, 18)
    instruction_height = scale_px(52, scale, 42)
    total_button_height = button_height * 2 + button_gap * 2 + instruction_height
    start_x = (width - button_width) // 2
    start_y = max(scale_px(180, scale, 135), (height - total_button_height) // 2)
    buttons = [
        pygame.Rect(start_x, start_y, button_width, button_height),
        pygame.Rect(start_x, start_y + button_height + button_gap, button_width, button_height),
    ]
    instruction_button = pygame.Rect(
        start_x,
        start_y + button_height * 2 + button_gap * 2,
        button_width,
        instruction_height,
    )

    selected_index = 0
    show_instructions = False
    close_instruction_rect = None
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None

            if event.type == pygame.KEYDOWN:
                if show_instructions:
                    if event.key in {pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER}:
                        show_instructions = False
                    elif event.key == pygame.K_q:
                        return None
                    continue
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

            if show_instructions:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if close_instruction_rect is None or close_instruction_rect.collidepoint(event.pos):
                        show_instructions = False
                continue

            if event.type == pygame.MOUSEMOTION:
                for index, rect in enumerate(buttons):
                    if rect.collidepoint(event.pos):
                        selected_index = index

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for index, rect in enumerate(buttons):
                    if rect.collidepoint(event.pos):
                        return options[index]["mode"]
                if instruction_button.collidepoint(event.pos):
                    show_instructions = True

        draw_mode_menu_background(screen, pygame, width, height)

        title_image = title_font.render("Wybierz tryb animacji", True, TEXT_COLOR)
        title_rect = title_image.get_rect(center=(width // 2, scale_px(88, scale, 62)))
        screen.blit(title_image, title_rect)

        subtitle_image = subtitle_font.render("Kliknij przycisk albo nacisnij klawisz 1/2", True, (88, 98, 108))
        subtitle_rect = subtitle_image.get_rect(center=(width // 2, scale_px(132, scale, 96)))
        screen.blit(subtitle_image, subtitle_rect)

        for index, rect in enumerate(buttons):
            option = options[index]
            is_selected = index == selected_index
            fill_color = (255, 255, 255) if not is_selected else (245, 250, 252)
            border_color = (194, 202, 210) if not is_selected else option["color"]

            pygame.draw.rect(screen, fill_color, rect, border_radius=scale_px(10, scale, 7))
            pygame.draw.rect(screen, border_color, rect, scale_px(2, scale, 1), border_radius=scale_px(10, scale, 7))
            pygame.draw.rect(
                screen,
                option["color"],
                (
                    rect.x + scale_px(16, scale, 12),
                    rect.y + scale_px(18, scale, 12),
                    scale_px(8, scale, 6),
                    rect.height - scale_px(36, scale, 24),
                ),
                border_radius=scale_px(4, scale, 3),
            )

            text_x = rect.x + scale_px(40, scale, 28)
            title = button_title_font.render(
                fit_text_to_width(button_title_font, option["title"], rect.right - text_x - scale_px(20, scale, 14)),
                True,
                TEXT_COLOR,
            )
            if "text" in option:
                title_y = rect.y + scale_px(24, scale, 16)
                text = button_text_font.render(option["text"], True, (82, 92, 102))
                screen.blit(title, (text_x, title_y))
                screen.blit(text, (text_x, rect.y + scale_px(68, scale, 50)))
            else:
                screen.blit(title, title.get_rect(midleft=(text_x, rect.centery)))

        mouse_pos = pygame.mouse.get_pos()
        instruction_hovered = instruction_button.collidepoint(mouse_pos)
        instruction_fill = (245, 250, 252) if instruction_hovered else (255, 255, 255)
        instruction_border = (42, 130, 128) if instruction_hovered else (194, 202, 210)
        pygame.draw.rect(screen, instruction_fill, instruction_button, border_radius=scale_px(8, scale, 6))
        pygame.draw.rect(
            screen,
            instruction_border,
            instruction_button,
            scale_px(2, scale, 1),
            border_radius=scale_px(8, scale, 6),
        )
        instruction_image = button_text_font.render("Instrukcja", True, TEXT_COLOR)
        screen.blit(instruction_image, instruction_image.get_rect(center=instruction_button.center))

        footer = button_text_font.render("Esc lub Q: zamknij program", True, (100, 108, 116))
        screen.blit(footer, footer.get_rect(center=(width // 2, height - scale_px(36, scale, 26))))

        if show_instructions:
            close_instruction_rect = draw_mode_menu_instructions(
                screen,
                pygame,
                width,
                height,
                scale,
                button_title_font,
                button_text_font,
            )
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
    scale = ui_scale(width, height)
    title_font = scaled_font(pygame, 52, scale, bold=True, min_size=32)
    subtitle_font = scaled_font(pygame, 24, scale, min_size=17)

    title_image = title_font.render(title, True, TEXT_COLOR)
    subtitle_image = subtitle_font.render(subtitle, True, (88, 98, 108))
    screen.blit(title_image, title_image.get_rect(center=(width // 2, height // 2 - scale_px(22, scale, 16))))
    screen.blit(subtitle_image, subtitle_image.get_rect(center=(width // 2, height // 2 + scale_px(28, scale, 20))))

    pygame.display.flip()
    pygame.event.pump()


def station_counts_by_district(stations: list[Station]) -> dict[str, int]:
    counts = {}
    for station in stations:
        district_name = route_district([station])
        counts[district_name] = counts.get(district_name, 0) + 1
    return counts


def average_route_km(prepared_routes: list[dict[str, Any]]) -> float:
    if not prepared_routes:
        return 0.0
    total_route_m = 0.0
    for prepared_route in prepared_routes:
        total_route_m += float(prepared_route["total_distance_m"])
    return total_route_m / 1000 / len(prepared_routes)


def control_button_rect(
    pygame: Any,
    panel_x: int,
    panel_width: int,
    height: int,
    index_from_bottom: int,
    scale: float,
) -> Any:
    margin = scale_px(24, scale, 18)
    button_height = scale_px(44, scale, 38)
    bottom_margin = scale_px(32, scale, 24)
    button_gap = scale_px(6, scale, 5)
    y = height - bottom_margin - button_height * index_from_bottom - button_gap * (index_from_bottom - 1)
    return pygame.Rect(panel_x + margin, y, panel_width - margin * 2, button_height)


def pause_button_rect(pygame: Any, panel_x: int, panel_width: int, height: int, scale: float = 1.0) -> Any:
    return control_button_rect(pygame, panel_x, panel_width, height, 1, scale)


def menu_button_rect(pygame: Any, panel_x: int, panel_width: int, height: int, scale: float = 1.0) -> Any:
    return control_button_rect(pygame, panel_x, panel_width, height, 2, scale)


def toggle_stage_button_rect(pygame: Any, panel_x: int, panel_width: int, height: int, scale: float = 1.0) -> Any:
    return control_button_rect(pygame, panel_x, panel_width, height, 3, scale)


def draw_button(
    pygame: Any,
    screen: Any,
    rect: Any,
    label: str,
    font: Any,
    fill_color: tuple[int, int, int] = (245, 248, 250),
    border_color: tuple[int, int, int] = (176, 184, 190),
) -> None:
    scale = ui_scale(*screen.get_size())
    radius = scale_px(8, scale, 6)
    pygame.draw.rect(screen, fill_color, rect, border_radius=radius)
    pygame.draw.rect(screen, border_color, rect, scale_px(2, scale, 1), border_radius=radius)
    label_image = font.render(label, True, TEXT_COLOR)
    screen.blit(label_image, label_image.get_rect(center=rect.center))


def draw_pause_button(
    pygame: Any,
    screen: Any,
    font: Any,
    paused: bool,
    panel_x: int,
    panel_width: int,
    height: int,
    scale: float = 1.0,
) -> None:
    rect = pause_button_rect(pygame, panel_x, panel_width, height, scale)
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


def draw_menu_button(
    pygame: Any,
    screen: Any,
    font: Any,
    panel_x: int,
    panel_width: int,
    height: int,
    scale: float = 1.0,
) -> None:
    draw_button(
        pygame,
        screen,
        menu_button_rect(pygame, panel_x, panel_width, height, scale),
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
    scale: float = 1.0,
) -> None:
    if active_stage == "weekday":
        label = "Pokaż weekendy"
    else:
        label = "Pokaż dni tygodnia"
    draw_button(
        pygame,
        screen,
        toggle_stage_button_rect(pygame, panel_x, panel_width, height, scale),
        label,
        font,
        fill_color=(236, 243, 250),
        border_color=(126, 155, 186),
    )


def draw_pause_badge(pygame: Any, screen: Any, title_font: Any, width: int, scale: float = 1.0) -> None:
    pause_image = title_font.render("PAUZA", True, TEXT_COLOR)
    pause_rect = pause_image.get_rect(center=(width // 2, scale_px(44, scale, 34))).inflate(
        scale_px(26, scale, 20),
        scale_px(14, scale, 10),
    )
    pause_panel = pygame.Surface(pause_rect.size, pygame.SRCALPHA)
    pause_panel.fill((255, 255, 255, 226))
    pygame.draw.rect(
        pause_panel,
        (185, 190, 196, 240),
        pause_panel.get_rect(),
        scale_px(1, scale, 1),
        border_radius=scale_px(8, scale, 6),
    )
    screen.blit(pause_panel, pause_rect.topleft)
    screen.blit(pause_image, pause_image.get_rect(center=pause_rect.center))


def draw_stage_badge(
    pygame: Any,
    screen: Any,
    title_font: Any,
    width: int,
    stage_title: str,
    scale: float = 1.0,
) -> None:
    stage_title_image = title_font.render(stage_title, True, TEXT_COLOR)
    stage_title_rect = stage_title_image.get_rect(midtop=(width // 2, scale_px(14, scale, 10))).inflate(
        scale_px(24, scale, 18),
        scale_px(12, scale, 10),
    )
    stage_panel = pygame.Surface(stage_title_rect.size, pygame.SRCALPHA)
    stage_panel.fill((255, 255, 255, 220))
    pygame.draw.rect(
        stage_panel,
        (185, 190, 196, 230),
        stage_panel.get_rect(),
        scale_px(1, scale, 1),
        border_radius=scale_px(8, scale, 6),
    )
    screen.blit(stage_panel, stage_title_rect.topleft)
    screen.blit(stage_title_image, stage_title_image.get_rect(center=stage_title_rect.center))


def draw_attribution(
    pygame: Any,
    screen: Any,
    small_font: Any,
    map_width: int,
    height: int,
    scale: float = 1.0,
) -> None:
    attribution = "(c) OpenStreetMap contributors (c) CARTO"
    attribution_image = small_font.render(attribution, True, TEXT_COLOR)
    attribution_rect = attribution_image.get_rect(
        bottomright=(map_width - scale_px(18, scale, 12), height - scale_px(14, scale, 10))
    ).inflate(scale_px(10, scale, 8), scale_px(6, scale, 4))
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
    panel_x: int,
    panel_width: int,
    height: int,
    selected_station_count: int | None = None,
    active_route_station_count: int | None = None,
    scroll: int = 0,
    scale: float = 1.0,
) -> int:
    panel_rect = pygame.Rect(panel_x, 0, panel_width, height)
    pygame.draw.rect(screen, (247, 249, 250), panel_rect)
    pygame.draw.line(screen, (205, 211, 216), (panel_x, 0), (panel_x, height), scale_px(1, scale, 1))

    controls_top = menu_button_rect(pygame, panel_x, panel_width, height, scale).top
    viewport_top = 0
    viewport_height = max(1, controls_top - scale_px(14, scale, 10))
    content_surface_height = max(height * 2, scale_px(900, scale, 760))
    content = pygame.Surface((panel_width, content_surface_height), pygame.SRCALPHA)

    x = scale_px(24, scale, 18)
    right_margin = scale_px(26, scale, 20)
    text_width = panel_width - x - right_margin - scale_px(8, scale, 6)
    y = scale_px(26, scale, 20)
    draw_text(content, title_font, "Rowery miejskie Londyn", (x, y), TEXT_COLOR)
    y += scale_px(42, scale, 34)

    total_route_m = 0.0
    for prepared_route in prepared_routes:
        total_route_m += prepared_route["total_distance_m"]

    total_station_trips = 0
    for route in routes:
        total_station_trips += route.station_network_weight

    total_route_km = total_route_m / 1000
    average_route_km = total_route_km / max(len(prepared_routes), 1)
    info_lines = [
        f"Stacje na mapie: {len(stations)}",
    ]
    if selected_station_count is not None and selected_station_count != len(stations):
        info_lines.append(f"Stacje do tras: {selected_station_count}")
    info_lines.extend(
        [
            f"Trasy: {len(routes)}",
            f"Rowerzyści: {len(routes)}",
            f"Prędkość: {speed_kmh:.1f} km/h",
        ]
    )
    for line in info_lines:
        draw_text(content, font, fit_text_to_width(font, line, text_width), (x, y), TEXT_COLOR)
        y += scale_px(25, scale, 21)

    y += scale_px(16, scale, 12)
    draw_text(content, title_font, "Legenda", (x, y), TEXT_COLOR)
    y += scale_px(32, scale, 26)
    y = draw_legend_description(content, font, x, y, text_width, scale)
    y += scale_px(8, scale, 6)

    station_counts = station_counts_by_district(stations)
    for district_name in DISTRICT_ORDER:
        station_count = station_counts.get(district_name, 0)
        if station_count == 0:
            continue

        route_color, bike_color = DISTRICT_COLORS[district_name]
        line_y = y + scale_px(10, scale, 8)
        pygame.draw.line(
            content,
            route_color,
            (x, line_y),
            (x + scale_px(48, scale, 34), line_y),
            scale_px(4, scale, 3),
        )
        pygame.draw.circle(
            content,
            bike_color,
            (x + scale_px(68, scale, 48), line_y),
            scale_px(6, scale, 4),
        )
        draw_text(
            content,
            font,
            fit_text_to_width(font, f"{district_label(district_name)}: {station_count}", text_width - scale_px(88, scale, 64)),
            (x + scale_px(88, scale, 64), y),
            TEXT_COLOR,
        )
        y += scale_px(30, scale, 24)

    content_height = min(content_surface_height, y + scale_px(24, scale, 18))
    return blit_scrollable_panel_content(
        pygame,
        screen,
        content,
        panel_x,
        panel_width,
        viewport_top,
        viewport_height,
        content_height,
        scroll,
        scale,
    )


def draw_weekday_weekend_panel(
    pygame: Any,
    screen: Any,
    font: Any,
    title_font: Any,
    weekday_routes: list[RouteAnimation],
    weekend_routes: list[RouteAnimation],
    prepared_weekday_routes: list[dict[str, Any]],
    prepared_weekend_routes: list[dict[str, Any]],
    weekday_stations: list[Station],
    weekend_stations: list[Station],
    map_station_count: int,
    map_stations: list[Station],
    active_stage: str,
    speed_kmh: float,
    time_scale: float,
    panel_x: int,
    panel_width: int,
    height: int,
    scroll: int = 0,
    scale: float = 1.0,
) -> int:
    panel_rect = pygame.Rect(panel_x, 0, panel_width, height)
    pygame.draw.rect(screen, (247, 249, 250), panel_rect)
    pygame.draw.line(screen, (205, 211, 216), (panel_x, 0), (panel_x, height), scale_px(1, scale, 1))

    controls_top = toggle_stage_button_rect(pygame, panel_x, panel_width, height, scale).top
    viewport_top = 0
    viewport_height = max(1, controls_top - scale_px(14, scale, 10))
    content_surface_height = max(height * 3, scale_px(1300, scale, 1000))
    content = pygame.Surface((panel_width, content_surface_height), pygame.SRCALPHA)

    x = scale_px(24, scale, 18)
    right_margin = scale_px(26, scale, 20)
    text_width = panel_width - x - right_margin - scale_px(8, scale, 6)
    y = scale_px(26, scale, 20)
    for title_line in ["Dni tygodnia vs", "weekendy"]:
        draw_text(content, title_font, fit_text_to_width(title_font, title_line, text_width), (x, y), TEXT_COLOR)
        y += scale_px(30, scale, 24)
    y += scale_px(12, scale, 8)

    if active_stage == "weekday":
        active_routes = weekday_routes
        active_prepared_routes = prepared_weekday_routes
        active_stations = weekday_stations
        station_count_label = "Stacje dni tygodnia"
        route_count_label = "Trasy dni tygodnia"
    else:
        active_routes = weekend_routes
        active_prepared_routes = prepared_weekend_routes
        active_stations = weekend_stations
        station_count_label = "Stacje weekendów"
        route_count_label = "Trasy weekendów"

    active_average_route_km = average_route_km(active_prepared_routes)
    info_lines = [
        f"Stacje na mapie: {map_station_count}",
        f"{station_count_label}: {len(active_stations)}",
        f"{route_count_label}: {len(active_routes)}",
        f"Prędkość: {speed_kmh:.1f} km/h"
    ]
    for line in info_lines:
        draw_text(content, font, fit_text_to_width(font, line, text_width), (x, y), TEXT_COLOR)
        y += scale_px(24, scale, 20)

    y += scale_px(12, scale, 9)
    draw_text(content, title_font, "Legenda", (x, y), TEXT_COLOR)
    y += scale_px(30, scale, 24)
    y = draw_legend_description(content, font, x, y, text_width, scale)
    y += scale_px(6, scale, 5)

    station_counts = station_counts_by_district(map_stations)
    for district_name in DISTRICT_ORDER:
        station_count = station_counts.get(district_name, 0)
        if station_count == 0:
            continue

        route_color, bike_color = DISTRICT_COLORS[district_name]
        line_y = y + scale_px(10, scale, 8)
        pygame.draw.line(
            content,
            route_color,
            (x, line_y),
            (x + scale_px(48, scale, 34), line_y),
            scale_px(4, scale, 3),
        )
        pygame.draw.circle(
            content,
            bike_color,
            (x + scale_px(68, scale, 48), line_y),
            scale_px(6, scale, 4),
        )
        draw_text(
            content,
            font,
            fit_text_to_width(font, f"{district_label(district_name)}: {station_count}", text_width - scale_px(88, scale, 64)),
            (x + scale_px(88, scale, 64), y),
            TEXT_COLOR,
        )
        y += scale_px(30, scale, 24)

    content_height = min(content_surface_height, y + scale_px(24, scale, 18))
    return blit_scrollable_panel_content(
        pygame,
        screen,
        content,
        panel_x,
        panel_width,
        viewport_top,
        viewport_height,
        content_height,
        scroll,
        scale,
    )
