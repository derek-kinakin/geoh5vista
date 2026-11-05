"""Compatibility imports; grid conversion lives in :mod:`geoh5vista.converters.grid2d`."""

from .converters.grid2d import (
    FUNCTION_DISPLAY_NAMES,
    MODULE_DISPLAY_NAME,
    grid2d_geom_to_vtk,
    grid2d_to_vtk,
    vtk_geom_to_grid2d,
    vtk_to_grid2d,
)

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "grid2d_geom_to_vtk",
    "grid2d_to_vtk",
    "vtk_geom_to_grid2d",
    "vtk_to_grid2d",
)
