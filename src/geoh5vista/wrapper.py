"""Compatibility imports for file I/O and converter dispatch."""

from typing import Final

from .converters import dispatch as _dispatch
from .converters.dispatch import geoh5wrap, vtkwrap
from .io.readers import read_geoh5
from .io.writers import vtk_to_entities as _vtk_to_entities
from .io.writers import write_geoh5

GEOH5WRAPPERS = _dispatch.GEOH5WRAPPERS
VTKWRAPPERS = _dispatch.VTKWRAPPERS
entities_to_vtk = _dispatch.entities_to_vtk
vtk_to_entities = _vtk_to_entities

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "geoh5wrap",
    "read_geoh5",
    "vtkwrap",
    "write_geoh5",
)

MODULE_DISPLAY_NAME: Final[str] = "Wrapper"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "geoh5wrap": "Geoh5 Wrap",
    "read_geoh5": "Read Geoh5",
    "vtkwrap": "VTK Wrap",
    "write_geoh5": "Write Geoh5",
}
