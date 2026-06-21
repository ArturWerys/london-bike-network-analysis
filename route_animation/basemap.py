from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .geo import crop_osm_image_to_bounds


# Szara mapa w tle: CartoDB Positron, czyli styl podobny do notebooka 04.


def surface_is_too_dark(surface: Any, sample_count: int = 18) -> bool:
    width, height = surface.get_size()
    if width <= 0 or height <= 0:
        return True

    x_step = max(1, width // sample_count)
    y_step = max(1, height // sample_count)
    luminance_sum = 0.0
    dark_pixels = 0
    samples = 0

    for y in range(y_step // 2, height, y_step):
        for x in range(x_step // 2, width, x_step):
            color = surface.get_at((x, y))
            luminance = 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b
            luminance_sum += luminance
            if luminance < 32:
                dark_pixels += 1
            samples += 1

    if samples == 0:
        return True

    average_luminance = luminance_sum / samples
    dark_ratio = dark_pixels / samples
    return average_luminance < 45 or dark_ratio > 0.82


def load_or_download_basemap(
    ctx: Any,
    pygame: Any,
    cache_path: Path,
    bounds: tuple[float, float, float, float],
    width: int,
    height: int,
    zoom: int | None,
    refresh_map: bool,
) -> Any | None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not refresh_map:
        surface = pygame.image.load(str(cache_path)).convert()
        if surface.get_size() != (width, height):
            surface = pygame.transform.smoothscale(surface, (width, height)).convert()
        if surface_is_too_dark(surface):
            print(f"Ignoring dark basemap cache: {cache_path}", file=sys.stderr)
            return None
        return surface

    try:
        left, bottom, right, top = bounds
        image, extent = ctx.bounds2img(
            left,
            bottom,
            right,
            top,
            zoom=zoom if zoom is not None else "auto",
            source=ctx.providers.CartoDB.Positron,
            ll=False,
        )

        cropped = crop_osm_image_to_bounds(image, extent, bounds)
        surface = pygame.image.frombuffer(
            cropped.tobytes(),
            (cropped.shape[1], cropped.shape[0]),
            "RGB",
        ).convert()
        surface = pygame.transform.smoothscale(surface, (width, height)).convert()
        if surface_is_too_dark(surface):
            print(f"Ignoring dark CartoDB Positron basemap: {cache_path}", file=sys.stderr)
            return None
        pygame.image.save(surface, str(cache_path))
        return surface

    except Exception as error:
        print(f"Could not load CartoDB Positron basemap: {error}", file=sys.stderr)
        return None
