"""Compatibility imports; label conversion lives in :mod:`geoh5vista.converters.label`."""

from .converters.label import (
    FUNCTION_DISPLAY_NAMES,
    MODULE_DISPLAY_NAME,
    get_label_text,
    label_geom_to_vtk,
    label_to_vtk,
)

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "get_label_text",
    "label_geom_to_vtk",
    "label_to_vtk",
)
