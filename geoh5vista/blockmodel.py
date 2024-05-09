"""Methods for converting block model data objects"""

__all__ = [
    "get_blockmodel_shape",
    "blockmodel_grid_geom_to_vtk",
    "blockmodel_to_vtk",
]

__displayname__ = "Blockmodel"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data


def get_blockmodel_shape(bm):
    """Returns the shape of a block model"""
    return (bm.shape[0], bm.shape[1], bm.shape[2])


def blockmodel_grid_geom_to_vtk(blkmdl, origin=(0.0, 0.0, 0.0)):
    """Convert the block model to a :class:`pyvista.StructuredGrid`
    object containing the 3D grid.

    Args:
        blkmdl (:class:`geoh5py.objects.block_model.BlockModel`): the grid geometry
            to convert
    """

    ox, oy, oz = blkmdl.origin.tolist()
 
    # Make coordinates along each axis
    xc = ox + np.cumsum(blkmdl.u_cells)
    xc = np.insert(xc, 0, ox)
    yc = oy + np.cumsum(blkmdl.v_cells)
    yc = np.insert(yc, 0, oy)
    zc = oz + np.cumsum(blkmdl.z_cells)
    zc = np.insert(zc, 0, oz)
    
    # Use a vtkStructuredGrid
    # Build out all nodes in the mesh
    xx, yy, zz = np.meshgrid(xc, yc, zc, indexing='ij')
    points = np.c_[xx.ravel("F"), yy.ravel("F"), zz.ravel("F")]
  
    output = pyvista.StructuredGrid()
    output.points = points
    output.dimensions = xc.shape[0],yc.shape[0],zc.shape[0]
  
    # TODO: Add rotation check and calculation
    # Rotate the points based on the axis orientations
    #rotation_mtx = np.array([blkmdl.axis_u, blkmdl.axis_v, blkmdl.axis_w])
    #points = points.dot(rotation_mtx)

    output.points += np.array(origin)
    return output


def blockmodel_to_vtk(blkmdl, origin=(0.0, 0.0, 0.0)):
    """Convert the block model to a VTK data object.

    Args:
        blkmdl (:class:`geoh5py.objects.block_model.BlockModel`): The block model
        to convert

    """
    output = blockmodel_grid_geom_to_vtk(blkmdl, origin=origin)

    # Add data to output
    fields = [i.name for i in blkmdl.children]
    if "Visual Parameters" in fields:
        fields.remove("Visual Parameters")
    if "UserComments" in fields:
        fields.remove("UserComments")
    arr = pyvista.PolyData(blkmdl.centroids)
    
    for f in fields:
        arr[f] = blkmdl.get_data(f)[0].values
    
    output = output.interpolate(arr, n_points=1, strategy="closest_point", null_value=-9999)
    
    return output


# Now set up the display names for the docs
blockmodel_to_vtk.__displayname__ = "Blockmodel to VTK"
blockmodel_grid_geom_to_vtk.__displayname__ = "Blockmodel Grid Geometry to VTK"
get_blockmodel_shape.__displayname__ = "Blockmodel Shape"
