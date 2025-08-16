"""Methods to convert grid2d objects to VTK data objects"""


__all__ = [
    "grid2d_to_vtk"
]

__displayname__ = "Grid2D"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data_to_vtk, add_texture_coordinates, check_orthogonal


def grid2d_to_vtk(grd, origin=(0.0, 0.0, 0.0)):
    """Convert the 2D grid to a :class:`pyvista.RectilinearGrid` object.

    Args:
        grd (:class:`geoh5py.objects.grid2d.Grid2D`): the surface
            grid geometry to convert

    """

    #dip = np.deg2rad(grd.dip)
    #rot = np.deg2rad(grd.rotation)
    
    #axis_u = grd.axis_u
    #axis_v = grd.axis_v
    #axis_w = np.cross(axis_u, axis_v)
    #if not check_orthogonal(axis_u, axis_v, axis_w):
    #    raise ValueError("axis_u, axis_v, and axis_w must be orthogonal")
    #rotation_mtx = np.array([axis_u, axis_v, axis_w])
    
    #ox, oy, oz = grd.origin

    # Make coordinates along each axis
    #x = ox + np.cumsum(grd.cell_center_u)
    #x = np.insert(x, 0, ox)
    #y = oy + np.cumsum(grd.cell_center_v)
    #y = np.insert(y, 0, oy)

    #z = np.array([oz])

    # Build out all nodes in the mesh
    #xx, yy, zz = np.meshgrid(x, y, z, indexing="ij")
    #(
    #    xx,
    #    yy,
    #    zz,
    #) = (
    #    xx.ravel("F"),
    #    yy.ravel("F"),
    #    zz.ravel("F"),
    #)
    #zz += grd.offset_w
    #points = np.c_[xx, yy, zz]

    # Rotate the points based on the axis orientations
    #points = points.dot(rotation_mtx)

    points = grd.centroids
    
    # Now build the output
    output = pyvista.RectilinearGrid()
    #output.points = points
    #output.dimensions = len(x), len(y), len(z)

    output.points = points
    output.dimensions = grd.shape[0], grd.shape[1], 1

    output.points += np.array(origin)
    return output


grid2d_to_vtk.__displayname__ = "Grid2D to VTK"
