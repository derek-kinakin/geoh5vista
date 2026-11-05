"""Compatibility imports for drillhole conversion and VTM persistence."""

from typing import Final

from .converters.drillholes import (
    MODULE_DISPLAY_NAME,
    drillhole_to_vtk,
    drillholes_to_vtk,
)
from .io.drillhole_vtm import read_drillholes, save_drillholes

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "drillhole_to_vtk",
    "drillholes_to_vtk",
    "read_drillholes",
    "save_drillholes",
)

FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "drillhole_to_vtk": "Drillhole to VTK",
    "drillholes_to_vtk": "Drillholes to VTK",
    "save_drillholes": "Save Drillholes",
    "read_drillholes": "Read Drillholes",
}
