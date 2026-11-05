"""Compatibility imports; surface conversion lives in :mod:`geoh5vista.converters.surface`."""

from .converters.surface import (
    FUNCTION_DISPLAY_NAMES,
    MODULE_DISPLAY_NAME,
    surface_geom_to_vtk,
    surface_to_vtk,
    vtk_geom_to_surface,
    vtk_to_surface,
)

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "surface_geom_to_vtk",
    "surface_to_vtk",
    "vtk_geom_to_surface",
    "vtk_to_surface",
)
