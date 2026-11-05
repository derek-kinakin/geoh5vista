"""Compatibility imports; slicer conversion lives in :mod:`geoh5vista.converters.slicer`."""

from .converters.slicer import (
    FUNCTION_DISPLAY_NAMES,
    MODULE_DISPLAY_NAME,
    slicer_to_vtk_plane,
)

__all__ = ("FUNCTION_DISPLAY_NAMES", "MODULE_DISPLAY_NAME", "slicer_to_vtk_plane")
