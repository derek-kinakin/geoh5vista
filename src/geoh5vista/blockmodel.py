"""Compatibility imports; block-model conversion lives in :mod:`geoh5vista.converters.blockmodel`."""

from .converters.blockmodel import (
    FUNCTION_DISPLAY_NAMES,
    MODULE_DISPLAY_NAME,
    blockmodel_grid_geom_to_image_vtk,
    blockmodel_grid_geom_to_structured_vtk,
    blockmodel_to_vtk,
    get_blockmodel_shape,
    vtk_geom_to_blockmodel,
    vtk_to_blockmodel,
)

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "blockmodel_grid_geom_to_image_vtk",
    "blockmodel_grid_geom_to_structured_vtk",
    "blockmodel_to_vtk",
    "get_blockmodel_shape",
    "vtk_geom_to_blockmodel",
    "vtk_to_blockmodel",
)
