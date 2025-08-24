"""Methods to convert grid2d objects to VTK data objects"""


__all__ = [
    "grid2d_to_vtk"
]

__displayname__ = "Grid2D"

import numpy as np
import pyvista

from geoh5py.shared.utils import xy_rotation_matrix, yz_rotation_matrix
from geoh5vista.utilities import add_data_to_vtk, add_entity_metadata #, add_texture_coordinates


def grid2d_geom_to_vtk(grd):
    """Convert the 2D grid geometry to a :class:`pyvista.RectilinearGrid` object.

    Args:
        grd (:class:`geoh5py.objects.grid2d.Grid2D`): the surface
            grid geometry to convert

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
    """Convert the 2D grid to a :class:`pyvista.RectilinearGrid` object.

    Args:
        grd (:class:`geoh5py.objects.grid2d.Grid2D`): the surface
            grid geometry to convert

    """
    output = grid2d_geom_to_vtk(grd)
    output = add_data_to_vtk(output, grd)
    output = add_entity_metadata(output, grd)
    
    return output


grid2d_geom_to_vtk.__displayname__ = "Grid2D Geometry to VTK" # type: ignore
grid2d_to_vtk.__displayname__ = "Grid2D to VTK" # type: ignore
