"""This module provides functions for transferring data between geoh5py and PyVista objects."""


__all__ = [
    "add_entity_metadata",
    "add_data_to_vtk",
    "add_drillhole_interval_data_to_vtk",
    "add_data_to_vtk_grid",
    "add_data_to_geoh5"
]

__displayname__ = "Data"

import numpy as np
import pyvista
from typing import Union
from geoh5py.data.float_data import FloatData
from geoh5py.data.integer_data import IntegerData
from geoh5py.data.referenced_data import ReferencedData
from geoh5py.data.boolean_data import BooleanData
from geoh5py.objects.block_model import BlockModel
from geoh5py.objects.drillhole import Drillhole
from geoh5py.objects.object_base import ObjectBase
from geoh5vista.constants import DATASKIP
from geoh5vista.utilities import get_gh5_entity_colour


def add_entity_metadata(output: pyvista.DataSet, entity: ObjectBase) -> pyvista.DataSet:
    """Add geoh5 entity metadata to a VTK object's field data.

    This includes the entity's name, color (from visual parameters), and
    class name.

    Parameters
    ----------
    output : pyvista.DataSet
        The VTK data object to add the metadata to.
    entity : geoh5py.objects.object_base.ObjectBase
        The geoh5py entity to source the metadata from.

    Returns
    -------
    pyvista.DataSet
        The VTK data object with added metadata.

    """
    colour = get_gh5_entity_colour(entity)
    output.field_data["gh5_colour"] = colour
    output.field_data["gh5_name"] = entity.name
    output.field_data["gh5_entity_type"] = entity.__class__.__name__

    # Visibility is a bit tricky since it can be a bool or a dict
    if isinstance(entity.visible, dict) and "Visible" in entity.visible:
        if entity.visible["Visible"].any():
            output.field_data["gh5_visible"] = True  # type: ignore
        else:
            output.field_data["gh5_visible"] = False # type: ignore
    elif isinstance(entity.visible, bool):
        output.field_data["gh5_visible"] = entity.visible # type: ignore
    else:
        output.field_data["gh5_visible"] = True # type: ignore
    return output


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
    """Transfer interval-based drillhole data to a VTK line object.

    This function maps interval data (e.g., geology, assays) from a
    ``Drillhole`` entity onto the cells of a VTK line representation of
    that drillhole. It uses the cell midpoints to determine which
    interval each cell belongs to.

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

    if "depth" not in output.point_data:
        raise ValueError("The line object must have a 'depth' point data array.")

    point_depths = output.point_data["depth"]
    cell_depth_midpoints = (point_depths[:-1] + point_depths[1:]) / 2.0

    fields = [f for f in entity.get_data_list() if f not in DATASKIP]

    if entity.from_ is None or entity.to_ is None:
        return output

    from_data = entity.from_[0]
    to_data = entity.to_[0]

    if from_data.values is None or to_data.values is None:
        return output

    interval_from = from_data.values
    interval_to = to_data.values

    for f in fields:
        data_obj_list = entity.get_data(f)
        if not data_obj_list:
            continue

        data = data_obj_list[0]
        if data.values is None:
            continue
        data_values = data.values

        if isinstance(data, FloatData):
            new_cell_data = np.full(output.n_cells, np.nan, dtype=float)
        elif isinstance(data, IntegerData):
            new_cell_data = np.full(output.n_cells, -1, dtype=int)
        elif isinstance(data, ReferencedData):
            new_cell_data = np.full(output.n_cells, -1, dtype=int)
        else:
            continue

        for i in range(len(interval_from)):
            start, end = interval_from[i], interval_to[i]
            mask = (cell_depth_midpoints >= start) & (cell_depth_midpoints < end)
            new_cell_data[mask] = data_values[i]

        output.cell_data[f] = new_cell_data

        if isinstance(data, ReferencedData):
            value_map = data.value_map
            names_array = np.full(output.n_cells, "N/A", dtype=object)
            valid_mask = new_cell_data != -1
            if value_map is not None:
                names_array[valid_mask] = value_map.map_values(
                    new_cell_data[valid_mask]
                )
            output.cell_data[f"{f}_names"] = names_array

    return output


def add_data_to_vtk_grid(output: Union[pyvista.StructuredGrid, pyvista.ImageData], entity: BlockModel) -> pyvista.DataSet:
    """Transfer data from a geoh5py grid entity to a VTK grid object.

    This function is specialized for grid objects like ``BlockModel``, where
    data needs to be reshaped and transposed to match the VTK cell
    ordering.

    Parameters
    ----------
    output : pyvista.StructuredGrid
        The VTK grid object to add the data to.
    entity : geoh5py.objects.block_model.BlockModel
        The geoh5py grid entity to source the data from.

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

        values_3d = values.reshape((n_v, n_u, n_z), order="C")

        values_vtk = values_3d.transpose(1, 0, 2).flatten(order="F")

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
        return "VERTEX"


def create_value_map(data: pyvista.DataSet, name: str) -> dict:
    """Create a mapping dictionary for referenced data values.

    Parameters
    ----------
    data : pyvista.DataSet
        The VTK data object containing the array.
    name : str
    """
    unique_values = np.unique(data[name])
    # Check if there is already and "Unknown" entry in the unique values;
    # if so, set move it to position 0 and create the values dict from 0
    if "Unknown" in unique_values:
        unique_values = np.array([v for v in unique_values if v != "Unknown"])
        unique_values = np.insert(unique_values, 0, "Unknown")
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
    

def add_data_to_geoh5(output: ObjectBase, data: pyvista.DataSet) -> ObjectBase:
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
    skip_names = ["gh5_colour", "gh5_name", "gh5_entity_type", "gh5_visible"]
    
    if data is None or data.n_arrays == 0:
        return output

    else:
        data_array_names = [i for i in data.array_names if i not in skip_names]
        for name in data_array_names:
            association = get_vtk_array_association(data, name)
            data_type = get_data_type(data, name)
            # Implement data transfer logic here
            if data_type == "REFERENCED":
                data_dict = create_value_map(data, name)
                data_dict_inverted = {v: k for k, v in data_dict.items()}
                # Create an array of integers that maps the string values to integer indices based on the data_dict
                mapper = np.vectorize(data_dict_inverted.get)
                ref_data = mapper(data[name])
                output.add_data(
                    {name: {
                        "type": "REFERENCED",
                        "association": association,
                        "values": ref_data,
                        "value_map":data_dict,
                    }}
                )
            else:
                output.add_data(
                    {name: {
                        "type": data_type,
                        "association": association,
                        "values": data[name]
                    }}
                )

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
    skip_names = ["gh5_colour", "gh5_name", "gh5_entity_type", "gh5_visible"]
    
    if data is None or data.n_arrays == 0:
        return output

    else:
        data_array_names = [i for i in data.array_names if i not in skip_names]
        for name in data_array_names:
            association = get_vtk_array_association(data, name)
            data_type = get_data_type(data, name)
            # Implement data transfer logic here

            # Order data values to match the geoh5py grid cell ordering (C-order) from VTK's F-order
            n_u, n_v, n_z = output.shape
            values = data[name]
            values_vtk = values.reshape((n_v, n_u, n_z), order="F")
            values_geoh5 = values_vtk.transpose(1, 0, 2).flatten(order="C")

            if data_type == "REFERENCED":
                data_dict = create_value_map(data, name)
                data_dict_inverted = {v: k for k, v in data_dict.items()}
                # Create an array of integers that maps the string values to integer indices based on the data_dict
                mapper = np.vectorize(data_dict_inverted.get)
                ref_data = mapper(values_geoh5)
                output.add_data(
                    {name: {
                        "type": "REFERENCED",
                        "association": association,
                        "values": ref_data,
                        "value_map":data_dict,
                    }}
                )
            else:
                output.add_data(
                    {name: {
                        "type": data_type,
                        "association": association,
                        "values": values_geoh5
                    }}
                )

    return output

    
add_entity_metadata.__displayname__ = "Metadata to VTK"  # type: ignore
add_data_to_vtk.__displayname__ = "Text Data to VTK"  # type: ignore
add_drillhole_interval_data_to_vtk.__displayname__ = "Float Data to VTK"  # type: ignore
add_data_to_vtk_grid.__displayname__ = "Referenced Data to VTK"  # type: ignore
add_grid_data_to_geoh5.__displayname__ = "Integer Data to VTK"  # type: ignore
