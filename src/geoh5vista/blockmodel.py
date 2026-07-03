"""This module provides functions for converting geoh5py BlockModel objects to and from PyVista data objects."""

from __future__ import annotations

from typing import Final
import numpy as np
import pyvista

from geoh5py.objects.object_base import ObjectBase
from geoh5py.objects.block_model import BlockModel
from geoh5py.workspace.workspace import Workspace
from geoh5py.shared.utils import xy_rotation_matrix
from geoh5vista.data import (
    add_data_to_vtk_grid,
    add_entity_metadata,
    add_grid_data_to_geoh5,
)


__all__ = (
    "get_blockmodel_shape",
    "blockmodel_grid_geom_to_structured_vtk",
    "blockmodel_grid_geom_to_image_vtk",
    "blockmodel_to_vtk",
    "vtk_geom_to_blockmodel",
    "vtk_to_blockmodel",
    "MODULE_DISPLAY_NAME",
    "FUNCTION_DISPLAY_NAMES",
)


MODULE_DISPLAY_NAME: Final[str] = "BlockModel"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "get_blockmodel_shape": "BlockModel Shape",
    "blockmodel_grid_geom_to_structured_vtk": "BlockModel Geometry to Structured VTK",
    "blockmodel_grid_geom_to_image_vtk": "BlockModel Geometry to Image VTK",
    "blockmodel_to_vtk": "BlockModel to VTK",
    "vtk_geom_to_blockmodel": "VTK Geometry to BlockModel",
    "vtk_to_blockmodel": "VTK to BlockModel",
}


def get_blockmodel_shape(bm: BlockModel) -> tuple[int, int, int]:
    """Get the shape of a block model.

    Parameters
    ----------
    bm : geoh5py.objects.block_model.BlockModel
        The block model to get the shape of.

    Returns
    -------
    tuple[int, int, int]
        The shape of the block model as (n_u, n_v, n_z).

    """
    return (bm.shape[0], bm.shape[1], bm.shape[2])


def _create_blockmodel_rot_matrix(blkmdl: BlockModel) -> np.ndarray:
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
    rotation = np.deg2rad(blkmdl.rotation)
    rotation_mtx = xy_rotation_matrix(rotation)
    return rotation_mtx


def blockmodel_grid_geom_to_structured_vtk(
    blkmdl: BlockModel, rotation_matrix: np.ndarray | None = None
) -> pyvista.StructuredGrid:
    """Convert the block model geometry to a ``pyvista.StructuredGrid``.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to convert.
    rotation_matrix : np.ndarray | None, optional
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
    xx, yy, zz = np.meshgrid(xc, yc, zc, indexing="ij")
    points = np.c_[xx.ravel("F"), yy.ravel("F"), zz.ravel("F")]

    if rotation_matrix is not None:
        points = points.dot(rotation_matrix)
    points += origin

    output = pyvista.StructuredGrid()
    output.points = points
    output.dimensions = xc.shape[0], yc.shape[0], zc.shape[0]
    return output


def blockmodel_grid_geom_to_image_vtk(
    blkmdl: BlockModel, rotation_matrix: np.ndarray | None = None
) -> pyvista.ImageData:
    """Convert the block model geometry to a ``pyvista.ImageData``.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to convert.
    rotation_matrix : np.ndarray | None, optional
        A 3x3 rotation matrix to apply to the grid points. If None, no
        rotation is applied. Default is None.

    Returns
    -------
    pyvista.ImageData
        The block model geometry as an image data object.

    """
    output = pyvista.ImageData()

    spacing = (
        np.abs(blkmdl.u_cells[0]),
        np.abs(blkmdl.v_cells[0]),
        np.abs(blkmdl.z_cells[0]),
    )
    output.spacing = spacing

    # Use a vtkImageData
    dimensions = np.array(blkmdl.shape) + 1
    output.dimensions = dimensions

    if rotation_matrix is not None:
        output.direction_matrix = rotation_matrix

    origin = [
        (blkmdl.centroids[:, 0].min() - spacing[0] / 2),
        (blkmdl.centroids[:, 1].min() - spacing[1] / 2),
        (blkmdl.centroids[:, 2].min() - spacing[2] / 2),
    ]

    output.origin = origin

    return output


def _determine_grid_type(blkmdl: BlockModel) -> str:
    """Determine the grid type of a block model.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to determine the grid type of.

    Returns
    -------
    str
        The grid type of the block model. One of "uniform" or "structured".

    """
    if (
        np.allclose(blkmdl.u_cells, blkmdl.u_cells[0])
        and np.allclose(blkmdl.v_cells, blkmdl.v_cells[0])
        and np.allclose(blkmdl.z_cells, blkmdl.z_cells[0])
    ):
        return "uniform"
    else:
        return "structured"


def blockmodel_to_vtk(blkmdl: BlockModel) -> pyvista.DataSet:
    """Convert a ``geoh5py.objects.block_model.BlockModel`` to a ``pyvista.DataSet``.

    This function converts the block model geometry and transfers all associated
    data.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to convert.

    Returns
    -------
    pyvista.DataSet
        The converted block model.

    """
    rotation_mtx = _create_blockmodel_rot_matrix(blkmdl)
    if _determine_grid_type(blkmdl) == "uniform":
        output = blockmodel_grid_geom_to_image_vtk(blkmdl, rotation_matrix=rotation_mtx)
    else:
        output = blockmodel_grid_geom_to_structured_vtk(
            blkmdl, rotation_matrix=rotation_mtx
        )

    output = add_data_to_vtk_grid(output, blkmdl)
    output = add_entity_metadata(output, blkmdl)
    return output


def vtk_geom_to_blockmodel(
    vtk: pyvista.ImageData | pyvista.StructuredGrid, workspace: Workspace, name: str
) -> BlockModel:
    """Convert a ``pyvista.ImageData`` or ``pyvista.StructuredGrid`` object to a ``geoh5py.objects.block_model.BlockModel`` object.

    Parameters
    ----------
    vtk : pyvista.ImageData | pyvista.StructuredGrid
        The VTK object to convert. It must have the required dimensions for a block model (nU x nV x nZ).
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new block model to.
    name : str
        The name of the new block model.

    Returns
    -------
    geoh5py.objects.block_model.BlockModel
        The newly created block model.

    Raises
    ------
    ValueError
        If the VTK object does not have the required dimensions for a block model (nU x nV x nZ).

    """

    # TO DO: Add checks for required dimensions. Cells must be uniform size in each direction. Cells must be 6 sided.
    # TO DO: Extract cell sizes and origin correctly
    # TO DO: Extract rotation correctly
    if isinstance(vtk, pyvista.ImageData):
        # For ImageData, the spacing is uniform and can be used to determine cell sizes
        origin = vtk.origin
        spacing = vtk.spacing
        n_blocks_x = vtk.dimensions[0] - 1
        n_blocks_y = vtk.dimensions[1] - 1
        n_blocks_z = vtk.dimensions[2] - 1
        block_x_dim = spacing[0]
        block_y_dim = spacing[1]
        block_z_dim = spacing[2]

        u_cell_delimiters = np.cumsum(
            np.pad(np.ones(n_blocks_x) * block_x_dim, (1, 0), "constant")
        )  # Constant offsets along u
        v_cell_delimiters = np.cumsum(
            np.pad(np.ones(n_blocks_y) * block_y_dim, (1, 0), "constant")
        )  # Constant offsets along v
        z_cell_delimiters = np.cumsum(
            np.pad(np.ones(n_blocks_z) * block_z_dim, (1, 0), "constant")
        )  # Constant offsets along z

    elif isinstance(vtk, pyvista.StructuredGrid):
        # For StructuredGrid, the cell sizes can be determined from the points
        n_blocks_x = vtk.dimensions[0]
        n_blocks_y = vtk.dimensions[1]
        n_blocks_z = vtk.dimensions[2]
        points = vtk.points.reshape((n_blocks_x, n_blocks_y, n_blocks_z, 3), order="F")
        origin = points[0, 0, 0]
        block_x_dim = np.diff(points[:, 0, 0, 0])
        block_y_dim = np.diff(points[0, :, 0, 1])
        block_z_dim = np.diff(points[0, 0, :, 2])

        u_cell_delimiters = np.cumsum(
            np.pad(block_x_dim, (1, 0), "constant")
        )  # Maybe variable offsets along u
        v_cell_delimiters = np.cumsum(
            np.pad(block_y_dim, (1, 0), "constant")
        )  # Maybe variableoffsets along v
        z_cell_delimiters = np.cumsum(
            np.pad(block_z_dim, (1, 0), "constant")
        )  # Maybe variableoffsets along z

    rotation = 0.0  # TO DO: Extract rotation from vtk.direction_matrix if

    blockmodel = BlockModel.create(
        workspace,
        origin=origin,
        u_cell_delimiters=u_cell_delimiters,  # Offsets along u
        v_cell_delimiters=v_cell_delimiters,  # Offsets along v
        z_cell_delimiters=z_cell_delimiters,  # Offsets along z
        rotation=rotation,
        name=name,
    )
    return blockmodel


def vtk_to_blockmodel(
    vtk: pyvista.ImageData | pyvista.StructuredGrid, workspace: Workspace, name: str
) -> ObjectBase:
    """Convert a ``pyvista.ImageData`` or ``pyvista.StructuredGrid`` object to a ``geoh5py.objects.block_model.BlockModel`` object.

    This is a wrapper for ``vtk_geom_to_blockmodel`` and is intended to be the
    main entry point for this conversion. In the future, it will also handle
    transferring data from the VTK object to the geoh5py object.

    Parameters
    ----------
    vtk : pyvista.ImageData | pyvista.StructuredGrid
        The VTK object to convert. It must have the required dimensions for a block model (nU x nV x nZ).
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new block model to.
    name : str
        The name of the new block model.

    Returns
    -------
    geoh5py.objects.block_model.BlockModel
        The newly created block model.


    """
    blockmodel = vtk_geom_to_blockmodel(vtk=vtk, workspace=workspace, name=name)
    blockmodel = add_grid_data_to_geoh5(
        blockmodel, vtk
    )  # may need a new function to ensure data is aligned to the grid cells correctly
    return blockmodel
