"""This module provides functions for converting geoh5py Grid2D objects to and from PyVista data objects."""


__all__ = [
    "grid2d_to_vtk"
]

__displayname__ = "Grid2D"

import numpy as np
import pyvista

from geoh5py.shared.utils import xy_rotation_matrix, yz_rotation_matrix
from geoh5vista.data import add_data_to_vtk, add_entity_metadata


def grid2d_geom_to_vtk(grd):
    """Convert the 2D grid geometry to a ``pyvista.ImageData`` object.

    Parameters
    ----------
    grd : geoh5py.objects.grid2d.Grid2D
        The 2D grid to convert.

    Returns
    -------
    pyvista.ImageData
        The converted 2D grid geometry.

    """
    if grd.vertical:
        dip = np.deg2rad(90)
    else:
        dip = np.deg2rad(grd.dip)
        
    rot = np.deg2rad(grd.rotation)
    # TO DO: Implement rotation matrix for 2D grid inclined from horizontal
    #rotation_mtx = yz_rotation_matrix(dip)*xy_rotation_matrix(rot)
    rotation_mtx = xy_rotation_matrix(rot)
    
    output = pyvista.ImageData()
    output.origin = grd.origin
    output.dimensions = [grd.u_count, grd.v_count, 1]
    output.spacing = [grd.u_cell_size, grd.v_cell_size, 1.0]
    output.direction_matrix = rotation_mtx

    return output


def grid2d_to_vtk(grd):
    """Convert a ``geoh5py.objects.grid2d.Grid2D`` to a ``pyvista.ImageData`` object.

    This function converts the grid geometry and transfers all associated data.

    Parameters
    ----------
    grd : geoh5py.objects.grid2d.Grid2D
        The 2D grid to convert.

    Returns
    -------
    pyvista.ImageData
        The converted 2D grid.

    """
    output = grid2d_geom_to_vtk(grd)
    output = add_data_to_vtk(output, grd)
    output = add_entity_metadata(output, grd)
    
    return output


grid2d_geom_to_vtk.__displayname__ = "Grid2D Geometry to VTK" # type: ignore
grid2d_to_vtk.__displayname__ = "Grid2D to VTK" # type: ignore
