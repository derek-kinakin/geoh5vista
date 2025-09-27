"""This module provides functions for converting geoh5py BlockModel objects to and from PyVista data objects."""

__all__ = [
    "get_blockmodel_shape",
    "blockmodel_grid_geom_to_vtk",
    "blockmodel_to_vtk",
]

__displayname__ = "Blockmodel"

from typing import Optional, Tuple
import numpy as np
import pyvista

from geoh5py.objects.block_model import BlockModel
from geoh5py.shared.utils import xy_rotation_matrix
from geoh5vista.data import add_data_to_vtk_grid, add_entity_metadata


def get_blockmodel_shape(bm: BlockModel) -> Tuple[int, int, int]:
    """Get the shape of a block model.

    Parameters
    ----------
    bm : geoh5py.objects.block_model.BlockModel
        The block model to get the shape of.

    Returns
    -------
    tuple
        The shape of the block model as (n_u, n_v, n_z).

    """
    return (bm.shape[0], bm.shape[1], bm.shape[2])


def create_blockmodel_rot_matrix(blkmdl: BlockModel) -> np.ndarray:
    """Create a rotation matrix for a block model.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to create the rotation matrix for.

    Returns
    -------
    numpy.ndarray
        The 2D rotation matrix.

    """
    rotation = np.radians(blkmdl.rotation)

    # Handle rotation matrix - ensure it's float64 and valid
    #if rotation_matrix is None:
    #    rotation_matrix = np.eye(3, dtype=np.float64)
    #else:
    #    rotation_matrix = np.array(rotation_matrix, dtype=np.float64)
    
    # create a rotation matrix from angle in radians
    #rotation_mtx = np.array([[np.cos(rotation), -np.sin(rotation), 0],
    #                         [np.sin(rotation), np.cos(rotation), 0],
    #                         [0, 0, 1]])
    rotation_mtx = xy_rotation_matrix(rotation)
    return rotation_mtx


def blockmodel_grid_geom_to_vtk(
    blkmdl: BlockModel, rotation_matrix: Optional[np.ndarray] = None
) -> pyvista.StructuredGrid:
    """Convert the block model geometry to a ``pyvista.StructuredGrid``.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to convert.
    rotation_matrix : numpy.ndarray, optional
        A 3x3 rotation matrix to apply to the grid points. If None, no
        rotation is applied. Default is None.

    Returns
    -------
    pyvista.StructuredGrid
        The block model geometry as a structured grid.

    """

    origin = np.array([blkmdl.origin[0], blkmdl.origin[1], blkmdl.origin[2]], "float32")
    
    xc = blkmdl.u_cell_delimiters
    yc = blkmdl.v_cell_delimiters
    zc = blkmdl.z_cell_delimiters

    # Use a vtkStructuredGrid
    # Build out all nodes in the mesh
    xx, yy, zz = np.meshgrid(xc, yc, zc, indexing='ij')
    points = np.c_[xx.ravel("F"), yy.ravel("F"), zz.ravel("F")]

    if rotation_matrix is not None:
        points = points.dot(rotation_matrix)
    points += origin

    output = pyvista.StructuredGrid()
    output.points = points
    output.dimensions = xc.shape[0], yc.shape[0], zc.shape[0] 
    return output


def blockmodel_to_vtk(blkmdl: BlockModel) -> pyvista.StructuredGrid:
    """Convert a ``geoh5py.objects.block_model.BlockModel`` to a ``pyvista.StructuredGrid``.

    This function converts the block model geometry and transfers all associated
    data.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to convert.

    Returns
    -------
    pyvista.StructuredGrid
        The converted block model.

    """
    rotation_mtx = create_blockmodel_rot_matrix(blkmdl)
    output = blockmodel_grid_geom_to_vtk(blkmdl, rotation_matrix=rotation_mtx)
    output = add_data_to_vtk_grid(output, blkmdl)
    output = add_entity_metadata(output, blkmdl)
    return output


# Now set up the display names for the docs
blockmodel_to_vtk.__displayname__ = "Blockmodel to VTK" # type: ignore
blockmodel_grid_geom_to_vtk.__displayname__ = "Blockmodel Grid Geometry to VTK" # type: ignore
get_blockmodel_shape.__displayname__ = "Blockmodel Shape" # type: ignore
