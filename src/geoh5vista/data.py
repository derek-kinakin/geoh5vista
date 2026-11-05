"""Compatibility imports for array transfer and source/display metadata."""

from typing import Final

from .converters import arrays as _arrays
from .converters.arrays import (
    add_data_to_geoh5,
    add_data_to_vtk,
    add_data_to_vtk_grid,
    add_drillhole_interval_data_to_vtk,
    add_grid_data_to_geoh5,
    get_vtk_array_association,
)
from .converters.metadata import add_entity_metadata, restore_entity_metadata

create_value_map = _arrays.create_value_map
get_data_type = _arrays.get_data_type

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "add_data_to_geoh5",
    "add_data_to_vtk",
    "add_data_to_vtk_grid",
    "add_drillhole_interval_data_to_vtk",
    "add_entity_metadata",
    "add_grid_data_to_geoh5",
    "get_vtk_array_association",
    "restore_entity_metadata",
)

MODULE_DISPLAY_NAME: Final[str] = "Data"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "add_entity_metadata": "Add Entity Metadata",
    "add_data_to_vtk": "Add Data to VTK",
    "add_drillhole_interval_data_to_vtk": "Add Drillhole Interval Data to VTK",
    "add_data_to_vtk_grid": "Add Data to VTK Grid",
    "add_data_to_geoh5": "Add Data to GeoH5",
    "add_grid_data_to_geoh5": "Add Grid Data to GeoH5",
    "get_vtk_array_association": "Get VTK Array Association",
    "restore_entity_metadata": "Restore Entity Metadata",
}
