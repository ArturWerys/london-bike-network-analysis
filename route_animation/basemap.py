import sys
from pathlib import Path
from typing import Any

from .geo import crop_osm_image_to_bounds


# Szara mapa w tle: CartoDB Positron, czyli styl podobny do notebooka 04.


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
        return pygame.image.load(str(cache_path)).convert()

    if not refresh_map:
        cached_maps = sorted(cache_path.parent.glob("*.png"))
        if cached_maps:
            fallback_map = max(cached_maps, key=lambda item: item.stat().st_size)
            print(f"Using existing cached basemap for fast startup: {fallback_map}")
            return pygame.transform.smoothscale(
                pygame.image.load(str(fallback_map)).convert(),
                (width, height),
            ).convert()

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
        pygame.image.save(surface, str(cache_path))
        return surface

    except Exception as error:
        print(f"Could not load CartoDB Positron basemap: {error}", file=sys.stderr)
        return None
