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
from geoh5vista.utilities import get_ga_entity_colour


def add_entity_metadata(output, entity):
    """Add the GA entity colour to the output VTK object."""
    colour = get_ga_entity_colour(entity)
    output.user_dict["colour"] = colour
    output.user_dict["name"] = entity.name
    output.user_dict["entity_type"] = entity.__class__.__name__
    return output


def add_data_to_vtk(output, entity):
    """Adds data arrays to an output VTK data object. Assigns data to cells or points
    based on number of data values compared to number of cells or points."""

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
    """Adds data arrays to Polydata line objects. Assigns data to cells or points
    based on number of data values compared to number of cells or points."""

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
    """Adds data arrays to an output VTK data object. Assigns data to cells or points
    based on number of data values compared to number of cells or points."""

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
    """Add data to the output VTK object."""
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
