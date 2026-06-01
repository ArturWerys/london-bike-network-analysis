import sys
from typing import Any


# Tu sprawdzamy biblioteki potrzebne dopiero przy uruchomieniu animacji.


def _require_module(import_name: str, package_name: str | None = None) -> Any:
    try:
        return __import__(import_name)
    except ImportError:
        package = package_name or import_name
        install_cmd = f".\\.venv\\Scripts\\python.exe -m pip install {package}"
        print(f"Missing package: {package}", file=sys.stderr)
        print("Install it with:", install_cmd, file=sys.stderr)
        sys.exit(1)


def require_pygame_module() -> Any:
    return _require_module("pygame")


def require_pandas_module() -> Any:
    return _require_module("pandas")


def require_runtime_modules(include_pygame: bool = True) -> tuple[Any, Any, Any, Any, Any]:
    pygame = _require_module("pygame") if include_pygame else None
    ox = _require_module("osmnx")
    nx = _require_module("networkx")
    pd = _require_module("pandas")
    ctx = _require_module("contextily")
    return pygame, ox, nx, pd, ctx
