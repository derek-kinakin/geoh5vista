"""Methods for converting block model data objects"""

__all__ = [
    "get_blockmodel_shape",
    "blockmodel_grid_geom_to_vtk",
    "blockmodel_to_vtk",
]

__displayname__ = "Blockmodel"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data_to_vtk_grid


def get_blockmodel_shape(bm):
    """Returns the shape of a block model"""
    return (bm.shape[0], bm.shape[1], bm.shape[2])


def create_blockmodel_rot_matrix(blkmdl):
    rotation = np.radians(blkmdl.rotation)

    # Handle rotation matrix - ensure it's float64 and valid
    #if rotation_matrix is None:
    #    rotation_matrix = np.eye(3, dtype=np.float64)
    #else:
    #    rotation_matrix = np.array(rotation_matrix, dtype=np.float64)
    
    # create a rotation matrix from angle in radians
    rotation_mtx = np.array([[np.cos(rotation), -np.sin(rotation), 0],
                             [np.sin(rotation), np.cos(rotation), 0],
                             [0, 0, 1]])
    return rotation_mtx 


def blockmodel_grid_geom_to_vtk(blkmdl, origin=(0, 0, 0), rotation_matrix=None):
    """Convert the block model to a :class:`pyvista.StructuredGrid`
    object containing the 3D grid.

    Args:
        blkmdl (:class:`geoh5py.objects.block_model.BlockModel`): the grid geometry
            to convert
    """

    origin = np.array(origin, dtype=np.float32)
    
    xc = blkmdl.u_cell_delimiters
    yc = blkmdl.v_cell_delimiters
    zc = blkmdl.z_cell_delimiters

    # Use a vtkStructuredGrid
    # Build out all nodes in the mesh
    xx, yy, zz = np.meshgrid(xc, yc, zc, indexing='ij')
    points = np.c_[xx.ravel("F"), yy.ravel("F"), zz.ravel("F")]

    #points = points.dot(rotation_matrix)

    output = pyvista.StructuredGrid()
    output.points = points
    output.dimensions = xc.shape[0], yc.shape[0], zc.shape[0] 
    output.points += origin
    return output


def blockmodel_to_vtk(blkmdl, origin=(0,0,0)):
    """Convert the block model to a VTK data object.

    Args:
        blkmdl (:class:`geoh5py.objects.block_model.BlockModel`): The block model
        to convert

    """
    origin = np.array([blkmdl.origin[0], blkmdl.origin[1], blkmdl.origin[2]], "float32")
    rotation_mtx = create_blockmodel_rot_matrix(blkmdl)
    output = blockmodel_grid_geom_to_vtk(blkmdl, origin=origin, rotation_matrix=rotation_mtx)
    output = add_data_to_vtk_grid(output, blkmdl, index=None)
    
    return output


# Now set up the display names for the docs
blockmodel_to_vtk.__displayname__ = "Blockmodel to VTK"
blockmodel_grid_geom_to_vtk.__displayname__ = "Blockmodel Grid Geometry to VTK"
get_blockmodel_shape.__displayname__ = "Blockmodel Shape"
