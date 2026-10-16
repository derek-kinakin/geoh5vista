"""``geoh5vista``: 3D visualization and geometry processing for Geoh5 format (geoh5) objects.
"""

from importlib.metadata import PackageNotFoundError, version
from .compat import patch_missing_concatenated_data
from .wrapper import geoh5wrap, read_geoh5, vtkwrap, write_geoh5

patch_missing_concatenated_data()

try:
    __version__ = version("geoh5vista")
except PackageNotFoundError:
    # Fallback for non-installed, source-only execution contexts.
    __version__ = "unknown"


__all__ = (
    "geoh5wrap",
    "read_geoh5",
    "vtkwrap",
    "write_geoh5"
)
