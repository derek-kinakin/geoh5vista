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
from geoh5py.data.referenced_data import ReferencedData
from geoh5py.data.float_data import FloatData
from geoh5py.data.integer_data import IntegerData
from geoh5vista.utilities import get_gh5_entity_colour


def add_entity_metadata(output, entity):
    """Add geoh5 entity metadata to a VTK object's field data.

    This includes the entity's name, color (from visual parameters), and
    class name.

    Parameters
    ----------
    output : pyvista.DataSet
        The VTK data object to add the metadata to.
    entity : geoh5py.objects.base_object.BaseObject
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
    return output


def add_data_to_vtk(output, entity):
    """Transfer data from a geoh5py entity to a VTK object.

    Data is added as point or cell arrays. For ``ReferencedData``, a
    companion array with the string representation of the values is also
    added.

    Parameters
    ----------
    output : pyvista.DataSet
        The VTK data object to add the data to.
    entity : geoh5py.objects.base_object.BaseObject
        The geoh5py entity to source the data from.

    Returns
    -------
    pyvista.DataSet
        The VTK data object with added data.

    """

    fields = [f for f in entity.get_data_list() if f not in SKIPDATA]
    #fields = [i.name for i in entity.children]
    #if "Visual Parameters" in fields:
    #    fields.remove("Visual Parameters")
    #if "UserComments" in fields:
    #    fields.remove("UserComments")
    
    for f in fields:
        data_obj = entity.get_data(f)
        if data_obj:
            data = data_obj[0]
            if isinstance(data, ReferencedData):
                data_value_map = data.value_map
                output[f] = data.values
                output[f"{f}_names"] = data_value_map.map_values(output[f])
            elif isinstance(data, FloatData):
                output[f] = data.values
            elif isinstance(data, IntegerData):
                output[f] = data.values
            else:
                pass
        else:
            pass
    
    return output


def add_drillhole_interval_data_to_vtk(output, entity):
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

    if 'depth' not in output.point_data:
        raise ValueError("The line object must have a 'depth' point data array.")

    point_depths = output.point_data['depth']
    cell_depth_midpoints = (point_depths[:-1] + point_depths[1:]) / 2.0

    fields = [f for f in entity.get_data_list() if f not in SKIPDATA]
    interval_from = entity.from_[0].values
    interval_to = entity.to_[0].values

    for f in fields:
        data_obj = entity.get_data(f)
        if not data_obj:
            continue
        
        data = data_obj[0]
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
            names_array[valid_mask] = value_map.map_values(new_cell_data[valid_mask])
            output.cell_data[f"{f}_names"] = names_array

    return output


def add_data_to_vtk_grid(output, entity):
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
    pyvista.StructuredGrid
        The VTK grid object with added data.

    """

    fields = [f for f in entity.get_data_list() if f not in SKIPDATA]
    #fields = [i.name for i in entity.children]
    #if "Visual Parameters" in fields:
    #    fields.remove("Visual Parameters")
    #if "UserComments" in fields:
    #    fields.remove("UserComments")
    
    for f in fields:
        data = entity.get_data(f)[0]
        values = data.values
        
        # For block models, we need to reshape to match the grid structure
        # geoh5 uses (n_u, n_v, n_z) ordering, but we need to match PyVista's cell ordering
        n_u, n_v, n_z = entity.shape
        
        # Reshape values to 3D array with proper dimensions
        # This order seems to be the inverse of what one might expect
        # but it works to get the correct orientation in PyVista when
        # combined with the transpose below
        values_3d = values.reshape((n_v, n_u, n_z), order='C')
        
        # PyVista structured grids expect cell data in a specific order
        # We need to transpose and flatten to match VTK cell ordering
        values_vtk = values_3d.transpose(1, 0, 2).flatten(order='F')
        
        if isinstance(data, ReferencedData):
            data_value_map = data.value_map
            output[f] = values_vtk
            output[f"{f}_names"] = data_value_map.map_values(output.cell_data[f])
        elif isinstance(data, FloatData):
            output[f] = values_vtk
        else:
            # Handle other data types if needed
            output[f] = values_vtk
    
    return output


def add_data_to_geoh5(output, data):
    """Add data from a VTK object to a geoh5py entity.

    .. warning::
        This function is not yet implemented.

    Parameters
    ----------
    output : geoh5py.objects.base_object.BaseObject
        The geoh5py entity to add the data to.
    data : pyvista.DataSet
        The VTK data object to source the data from.

    """
    pass


SKIPDATA = [
    'Azimuth',
    'DEPTH (Static-Survey)',
    'Dip',
    'Visual Parameters',
    'UserComments'
]

add_entity_metadata.__displayname__ = "Metadata to VTK"  # type: ignore
add_data_to_vtk.__displayname__ = "Text Data to VTK"  # type: ignore
add_drillhole_interval_data_to_vtk.__displayname__ = "Float Data to VTK"  # type: ignore
add_data_to_vtk_grid.__displayname__ = "Referenced Data to VTK"  # type: ignore
add_data_to_geoh5.__displayname__ = "Integer Data to VTK"  # type: ignore
