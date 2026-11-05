"""``geoh5vista``: 3D visualization and geometry processing for Geoh5 format (geoh5) objects.
"""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from .compat import patch_missing_concatenated_data
from .io.catalog import catalog_geoh5
from .models import EntityMetadata

if TYPE_CHECKING:
    from .converters.dispatch import geoh5wrap, vtkwrap
    from .io.readers import read_geoh5
    from .io.selective import read_geoh5_entities
    from .io.writers import write_geoh5

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
    "read_geoh5_entities",
    "vtkwrap",
    "write_geoh5"
)


_LAZY_EXPORTS = {
    "geoh5wrap": ".converters.dispatch",
    "read_geoh5": ".io.readers",
    "read_geoh5_entities": ".io.selective",
    "vtkwrap": ".converters.dispatch",
    "write_geoh5": ".io.writers",
}


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        value = getattr(import_module(_LAZY_EXPORTS[name], __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
