"""Compatibility imports; curve conversion lives in :mod:`geoh5vista.converters.curve`."""

from .converters.curve import (
    FUNCTION_DISPLAY_NAMES,
    MODULE_DISPLAY_NAME,
    curve_geom_to_vtk,
    curve_to_vtk,
    vtk_geom_to_curve,
    vtk_to_curve,
)

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "curve_geom_to_vtk",
    "curve_to_vtk",
    "vtk_geom_to_curve",
    "vtk_to_curve",
)
