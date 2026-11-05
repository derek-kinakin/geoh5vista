"""This module provides functions for transferring data between geoh5py and PyVista objects."""

from __future__ import annotations

from typing import Final

import numpy as np
import pyvista
from geoh5py.data.boolean_data import BooleanData
from geoh5py.data.colour import Colour
from geoh5py.data.float_data import FloatData
from geoh5py.data.integer_data import IntegerData
from geoh5py.data.referenced_data import ReferencedData
from geoh5py.objects.block_model import BlockModel
from geoh5py.objects.drillhole import Drillhole
from geoh5py.objects.object_base import ObjectBase

from ..constants import DATASKIP

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "add_data_to_geoh5",
    "add_data_to_vtk",
    "add_data_to_vtk_grid",
    "add_drillhole_interval_data_to_vtk",
    "add_grid_data_to_geoh5",
    "get_vtk_array_association",
)


MODULE_DISPLAY_NAME: Final[str] = "Arrays"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "add_data_to_vtk": "Add Data to VTK",
    "add_drillhole_interval_data_to_vtk": "Add Drillhole Interval Data to VTK",
    "add_data_to_vtk_grid": "Add Data to VTK Grid",
    "add_data_to_geoh5": "Add Data to GeoH5",
    "add_grid_data_to_geoh5": "Add Grid Data to GeoH5",
    "get_vtk_array_association": "Get VTK Array Association",
}


def add_data_to_vtk(output: pyvista.DataSet, entity: ObjectBase) -> pyvista.DataSet:
    """Transfer data from a geoh5py entity to a VTK object.

    Data is added as point or cell arrays. For ``ReferencedData``, a
    companion array with the string representation of the values is also
    added.

    Parameters
    ----------
    output : pyvista.DataSet
        The VTK data object to add the data to.
    entity : geoh5py.objects.object_base.ObjectBase
        The geoh5py entity to source the data from.

    Returns
    -------
    pyvista.DataSet
        The VTK data object with added data.

    """

    fields = [f for f in entity.get_data_list() if f not in DATASKIP]

    for f in fields:
        data_obj_list = entity.get_data(f)
        if data_obj_list:
            data = data_obj_list[0]
            if data.values is None:
                continue
            if isinstance(data, BooleanData):
                continue
            if isinstance(data, ReferencedData):
                data_value_map = data.value_map
                output[f] = data.values
                if data_value_map is not None:
                    output[f"{f}_names"] = data_value_map.map_values(output[f])
            elif isinstance(data, (FloatData, IntegerData)):
                output[f] = data.values
            else:
                pass
        else:
            pass

    return output


def add_drillhole_interval_data_to_vtk(
    output: pyvista.PolyData, entity: Drillhole
) -> pyvista.PolyData:
    """Transfer independent drillhole tables to a supplied line view.

    The line must have sequential two-point cells, increasing measured
    depths, and vertices at every interval boundary within its extent.
    Point observations are transferred only at exact matching depths.
    Overlapping observations in one array raise ``ValueError`` rather
    than overwriting values. Prefer the composite drillhole converter
    for lossless import.

    Parameters
    ----------
    output : pyvista.PolyData
        The VTK line object representing the drillhole trace. It must have
        a point data array named 'depth'.
    entity : geoh5py.objects.drillhole.Drillhole
        The geoh5py drillhole entity containing the interval data.

    Returns
    -------
    pyvista.PolyData
        The VTK line object with added cell data.

    Raises
    ------
    ValueError
        If the input VTK object does not have a 'depth' point data array.

    """

    from .drillholes import _merged_hole, drillhole_to_vtk

    converted = _merged_hole(entity, drillhole_to_vtk(entity), output=output.copy(deep=True))
    output.copy_from(converted)
    return output


def add_data_to_vtk_grid(
    output: pyvista.StructuredGrid | pyvista.ImageData,
    entity: BlockModel,
    reverse_axes: tuple[bool, bool, bool] | None = None,
) -> pyvista.DataSet:
    """Transfer data from a geoh5py grid entity to a VTK grid object.

    This function is specialized for grid objects like ``BlockModel``, where
    data needs to be reshaped and transposed to match the VTK cell
    ordering.

    Parameters
    ----------
    output : pyvista.StructuredGrid | pyvista.ImageData
        The VTK grid object to add the data to.
    entity : geoh5py.objects.block_model.BlockModel
        The geoh5py grid entity to source the data from.
    reverse_axes : tuple[bool, bool, bool] | None, optional
        U/V/Z axes whose VTK index order is reversed relative to geoh5.

    Returns
    -------
    pyvista.DataSet
        The VTK grid object with added data.

    """

    fields = [f for f in entity.get_data_list() if f not in DATASKIP]

    for f in fields:
        data_obj_list = entity.get_data(f)
        if not data_obj_list:
            continue
        data = data_obj_list[0]
        if data.values is None:
            continue
        values = data.values

        if entity.shape is None:
            continue
        n_u, n_v, n_z = entity.shape

        values_3d = values.reshape((n_v, n_u, n_z), order="C").transpose(1, 0, 2)
        if reverse_axes is not None:
            values_3d = np.flip(
                values_3d, axis=tuple(i for i, reverse in enumerate(reverse_axes) if reverse)
            )

        values_vtk = values_3d.flatten(order="F")

        if isinstance(data, ReferencedData):
            data_value_map = data.value_map
            output[f] = values_vtk
            if data_value_map is not None:
                output[f"{f}_names"] = data_value_map.map_values(output.cell_data[f])
        else:
            output[f] = values_vtk

    return output


def get_vtk_array_association(data: pyvista.DataSet, name: str) -> str:
    """Determine if a VTK array should be assigned to 'VERTEX' or 'CELL'
    for writing to geoh5.

    Parameters
    ----------
    data : pyvista.DataSet
        The VTK data object containing the array.
    name : str
        The name of the array.

    Returns
    -------
        str
            The determined association: 'VERTEX' or 'CELL'.

    """
    # Placeholder logic; replace with actual determination logic
    if name in data.point_data:
        return "VERTEX"
    elif name in data.cell_data:
        return "CELL"
    else:
        return None


def create_value_map(data: pyvista.DataSet, name: str) -> dict:
    """Create a mapping dictionary for referenced data values.

    Parameters
    ----------
    data : pyvista.DataSet
        The VTK data object containing the array.
    name : str
    """
    return _value_map_from_values(data[name])


def _value_map_from_values(values: np.ndarray) -> dict:
    unique_values = np.unique(values)
    # Check if there is already and "Unknown" entry in the unique values;
    # if so, set move it to position 0 and create the values dict from 0
    if "Unknown" in unique_values:
        unique_values = [v for v in unique_values if v != "Unknown"]
        unique_values.insert(0, "Unknown")
        values_dict = {int(n): i for n, i in enumerate(unique_values)}
    else:
        values_dict = {int(n+1): i for n, i in enumerate(unique_values)}
        values_dict[0] = "Unknown"

    return values_dict


def get_data_type(data: pyvista.DataSet, name: str) -> str:
    """Determine the data type for a VTK array when writing to geoh5.

    Parameters
    ----------
    data : pyvista.DataSet
        The VTK data object containing the array.
    name : str
        The name of the array.

    Returns
    -------
        str
            The determined data type: 'float', 'int', or 'referenced'.

    """
    array = data[name]
    if np.issubdtype(array.dtype, np.floating): # Float data type
        return "FLOAT"
    elif np.issubdtype(array.dtype, np.integer): # Integer data type
        return "INTEGER"
    elif np.issubdtype(array.dtype, np.str_): # String data type (for referenced data)
        return "REFERENCED"
    else:
        return "FLOAT"


_XYZ_SUFFIXES: Final[tuple[str, ...]] = ("x", "y", "z")


def _is_colour_array(values: np.ndarray, output: ObjectBase | None = None) -> bool:
    """Return True for RGB/RGBA arrays (unsigned 8-bit, 3 or 4 columns) the entity can store as colour."""
    if not (values.ndim == 2 and values.shape[1] in (3, 4) and values.dtype == np.uint8):
        return False
    allowed_parents = getattr(Colour, "_allowed_parent", None)
    return output is None or allowed_parents is None or type(output).__name__ in allowed_parents


def _split_components(name: str, values: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Split a multi-component array into named 1D component arrays.

    geoh5 data entries are one value per vertex or cell, so an ``(n, k)``
    array (e.g. ``Normals``) is written as ``k`` entries. Three-component
    arrays use ``_x``, ``_y``, ``_z`` suffixes; others use ``_0`` ... ``_k-1``.
    """
    values = np.asarray(values)
    if values.ndim == 1:
        return [(name, values)]
    values = values.reshape(values.shape[0], -1)
    if values.shape[1] == 1:
        return [(name, values[:, 0])]
    suffixes = _XYZ_SUFFIXES if values.shape[1] == 3 else range(values.shape[1])
    return [(f"{name}_{suffix}", values[:, i]) for i, suffix in enumerate(suffixes)]


def _array_data_type(values: np.ndarray) -> str:
    if np.issubdtype(values.dtype, np.floating):
        return "FLOAT"
    if np.issubdtype(values.dtype, np.integer):
        return "INTEGER"
    if np.issubdtype(values.dtype, np.str_):
        return "REFERENCED"
    return "FLOAT"


def _add_array_to_geoh5(output: ObjectBase, name: str, values: np.ndarray, association: str) -> None:
    """Add one VTK array to a geoh5 entity, handling colour and multi-component arrays."""
    values = np.asarray(values)
    if _is_colour_array(values, output):
        output.add_data(
            {name: {"type": "COLOUR", "association": association, "values": values}}
        )
        return

    for component_name, component in _split_components(name, values):
        data_type = _array_data_type(component)
        if data_type == "REFERENCED":
            data_dict = _value_map_from_values(component)
            data_dict_inverted = {v: k for k, v in data_dict.items()}
            # Map the string values to integer keys of the value map
            ref_data = np.vectorize(data_dict_inverted.get)(component)
            output.add_data(
                {component_name: {
                    "type": "REFERENCED",
                    "association": association,
                    "values": ref_data,
                    "value_map": data_dict,
                }}
            )
        else:
            output.add_data(
                {component_name: {
                    "type": data_type,
                    "association": association,
                    "values": component,
                }}
            )


def add_data_to_geoh5(output: ObjectBase, data: pyvista.DataSet) -> ObjectBase:
    """Add data from a VTK object to a geoh5py entity.

    Modifies the geoh5py entity in place by adding point and cell data
    arrays from the VTK object. Multi-component arrays (e.g. ``Normals``)
    are split into one geoh5 data entry per component, and unsigned 8-bit
    RGB/RGBA arrays are written as geoh5 colour data.

    Parameters
    ----------
    output : geoh5py.objects.object_base.ObjectBase
        The geoh5py entity to add the data to.
    data : pyvista.DataSet
        The VTK data object to source the data from.

    """
    for association, arrays in (("VERTEX", data.point_data), ("CELL", data.cell_data)):
        for name in arrays.keys():
            _add_array_to_geoh5(output, name, arrays[name], association)

    return output


def add_grid_data_to_geoh5(output: ObjectBase, data: pyvista.DataSet) -> ObjectBase:
    """Add data from a VTK object to a geoh5py entity.

    Modifies the geoh5py entity in place by adding data arrays from the
    VTK object, excluding certain metadata arrays.

    Parameters
    ----------
    output : geoh5py.objects.object_base.ObjectBase
        The geoh5py entity to add the data to.
    data : pyvista.DataSet
        The VTK data object to source the data from.

    """
    n_u, n_v, n_z = output.shape
    for name in data.cell_data.keys():
        values = np.asarray(data.cell_data[name])
        if _is_colour_array(values, output):
            # Reorder rows from VTK's F-order to geoh5py grid cell ordering (C-order)
            order = np.arange(values.shape[0]).reshape((n_u, n_v, n_z), order="F")
            order = order.transpose(1, 0, 2).flatten(order="C")
            _add_array_to_geoh5(output, name, values[order], "CELL")
            continue
        for component_name, component in _split_components(name, values):
            # Order data values to match the geoh5py grid cell ordering (C-order) from VTK's F-order
            values_vtk = component.reshape((n_u, n_v, n_z), order="F")
            values_geoh5 = values_vtk.transpose(1, 0, 2).flatten(order="C")
            _add_array_to_geoh5(output, component_name, values_geoh5, "CELL")

    return output
