"""``geoh5vista``: 3D visualization and geometry processing for Geoh5 format (geoh5) objects.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from .catalog import EntityMetadata, catalog_geoh5
from .compat import patch_missing_concatenated_data

if TYPE_CHECKING:
    from .wrapper import geoh5wrap, read_geoh5, vtkwrap, write_geoh5

patch_missing_concatenated_data()

try:
    __version__ = version("geoh5vista")
except PackageNotFoundError:
    # Fallback for non-installed, source-only execution contexts.
    __version__ = "unknown"


__all__ = (
    "EntityMetadata",
    "catalog_geoh5",
    "geoh5wrap",
    "read_geoh5",
    "vtkwrap",
    "write_geoh5"
)


def __getattr__(name: str):
    if name in ("geoh5wrap", "read_geoh5", "vtkwrap", "write_geoh5"):
        from . import wrapper

        value = getattr(wrapper, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
