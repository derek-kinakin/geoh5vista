"""This module provides functions for transferring data between geoh5py and PyVista objects."""

from __future__ import annotations

from typing import Final

import numpy as np
import pyvista
from geoh5py.data.boolean_data import BooleanData
from geoh5py.data.float_data import FloatData
from geoh5py.data.integer_data import IntegerData
from geoh5py.data.referenced_data import ReferencedData
from geoh5py.objects.block_model import BlockModel
from geoh5py.objects.drillhole import Drillhole
from geoh5py.objects.object_base import ObjectBase

from geoh5vista.constants import DATASKIP
from geoh5vista.utilities import get_gh5_entity_colour, normalize_visibility

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


def add_entity_metadata(output: pyvista.DataSet, entity: ObjectBase) -> pyvista.DataSet:
    """Add geoh5 entity metadata to a VTK object as a user_dict.

    The metadata is stored in ``output.user_dict["geoh5"]`` as a nested
    dictionary containing schema version, source, and display information.

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
    output.user_dict["geoh5"] = {
        "schema_version": 1,
        "source": {
            "uid": str(entity.uid),
            "entity_type": entity.__class__.__name__,
            "parent_uid": str(entity.parent.uid) if entity.parent else None,
        },
        "display": {
            "name": entity.name,
            "colour": get_gh5_entity_colour(entity),
            "visible": normalize_visibility(entity.visible),
        },
    }

    return output


def restore_entity_metadata(
    output: ObjectBase, data: pyvista.DataSet, *, name: str | None = None
) -> ObjectBase:
    """Restore geoh5 display metadata onto an existing geoh5 entity.

    Reads schema version 1 from ``data.user_dict["geoh5"]``. Missing
    metadata or display fields leave the corresponding entity defaults
    unchanged. All supported fields are validated before applying changes.
    Source UID, parent UID, and entity type are not restored.

    Parameters
    ----------
    output : geoh5py.objects.object_base.ObjectBase
        The newly created entity to update in place.
    data : pyvista.DataSet
        The PyVista object containing geoh5 metadata.
    name : str or None, optional
        An explicit name overriding the stored display name.
        Only applied when geoh5 metadata is present.

    Returns
    -------
    geoh5py.objects.object_base.ObjectBase
        The updated entity.

    Raises
    ------
    ValueError
        If the metadata schema or a supported display value is invalid.

    """
    if "geoh5" not in data.user_dict:
        return output

    metadata = data.user_dict["geoh5"]
    if not isinstance(metadata, dict):
        raise ValueError("geoh5 metadata must be a dictionary.")
    version = metadata.get("schema_version")
    if type(version) is not int or version != 1:
        raise ValueError("geoh5.schema_version must be the integer 1.")

    display = metadata.get("display", {})
    if not isinstance(display, dict):
        raise ValueError("geoh5.display must be a dictionary.")

    restored_name = name if name is not None else display.get("name")
    if (name is not None or "name" in display) and not isinstance(restored_name, str):
        raise ValueError("geoh5.display.name must be a string.")
    if "visible" in display and not isinstance(display["visible"], bool):
        raise ValueError("geoh5.display.visible must be a boolean.")
    if "colour" in display:
        colour = display["colour"]
        if (
            not isinstance(colour, (list, tuple))
            or len(colour) != 3
            or not all(type(value) is int and 0 <= value <= 255 for value in colour)
        ):
            raise ValueError(
                "geoh5.display.colour must contain three RGB integers between 0 and 255."
            )

    if restored_name is not None:
        output.name = restored_name
    if "visible" in display:
        output.visible = display["visible"]
    if "colour" in display:
        visual_parameters = output.visual_parameters
        if visual_parameters is None:
            visual_parameters = output.add_default_visual_parameters()
        visual_parameters.colour = list(display["colour"])

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
    unique_values = np.unique(data[name])
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
    # Get only cell or point data arrays
    data_array_names = [i for i in data.array_names if get_vtk_array_association(data, i) in ["CELL", "VERTEX"]]
    
    if not data_array_names or data.n_arrays == 0:
        return output

    else:
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
    # Get only cell data arrays
    data_array_names = [i for i in data.array_names if get_vtk_array_association(data, i) in ["CELL"]]
    
    if not data_array_names or data.n_arrays == 0:
        return output

    else:
        for name in data_array_names:
            data_type = get_data_type(data, name)
            # Order data values to match the geoh5py grid cell ordering (C-order) from VTK's F-order
            n_u, n_v, n_z = output.shape
            values = data[name]
            values_vtk = values.reshape((n_u, n_v, n_z), order="F")
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
                        "association": "CELL",
                        "values": ref_data,
                        "value_map":data_dict,
                    }}
                )
            else:
                output.add_data(
                    {name: {
                        "type": data_type,
                        "association": "CELL",
                        "values": values_geoh5
                    }}
                )

    return output
