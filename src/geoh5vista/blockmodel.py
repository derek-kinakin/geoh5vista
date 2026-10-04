"""This module provides functions for converting geoh5py BlockModel objects to and from PyVista data objects."""

from __future__ import annotations

from typing import Final

import numpy as np
import pyvista
from geoh5py.objects.block_model import BlockModel
from geoh5py.objects.object_base import ObjectBase
from geoh5py.shared.utils import xy_rotation_matrix
from geoh5py.workspace.workspace import Workspace

from geoh5vista.data import (
    add_data_to_vtk_grid,
    add_entity_metadata,
    add_grid_data_to_geoh5,
)

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "blockmodel_grid_geom_to_image_vtk",
    "blockmodel_to_vtk",
    "get_blockmodel_shape",
    "vtk_geom_to_blockmodel",
    "vtk_to_blockmodel",
)


MODULE_DISPLAY_NAME: Final[str] = "BlockModel"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "get_blockmodel_shape": "BlockModel Shape",
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


def blockmodel_grid_geom_to_image_vtk(
    blkmdl: BlockModel, rotation_matrix: np.ndarray | None = None
) -> pyvista.ImageData:
    """Convert block model geometry, preserving local-axis cell ordering.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to convert.
    rotation_matrix : np.ndarray | None, optional
        A 3x3 rotation matrix to apply to the grid points. If None, no
        rotation is applied. Default is None. Descending cell delimiters
        are represented by signed directions with positive spacing.

    Returns
    -------
    pyvista.ImageData
        The block model geometry as an image data object.

    Raises
    ------
    ValueError
        If cell spacing is not uniform within each axis.

    """
    _validate_uniform_spacing(blkmdl)
    output = pyvista.ImageData()

    steps = np.array(
        [blkmdl.u_cells[0], blkmdl.v_cells[0], blkmdl.z_cells[0]],
        dtype=np.float64,
    )
    output.spacing = np.abs(steps)

    # Use a vtkImageData
    dimensions = np.array(blkmdl.shape) + 1
    output.dimensions = dimensions

    rotation = np.eye(3) if rotation_matrix is None else rotation_matrix
    output.direction_matrix = rotation @ np.diag(np.sign(steps))

    model_origin = np.asarray(blkmdl.origin.tolist(), dtype=np.float64)
    first_corner = np.array(
        [
            blkmdl.u_cell_delimiters[0],
            blkmdl.v_cell_delimiters[0],
            blkmdl.z_cell_delimiters[0],
        ],
        dtype=np.float64,
    )
    output.origin = model_origin + rotation @ first_corner

    return output


def _validate_uniform_spacing(blkmdl: BlockModel) -> None:
    """Require finite, nonzero cell spacing that is uniform within each axis."""
    for axis, cells in (
        ("u", blkmdl.u_cells),
        ("v", blkmdl.v_cells),
        ("z", blkmdl.z_cells),
    ):
        if (
            cells.size == 0
            or not np.all(np.isfinite(cells))
            or np.any(cells == 0)
        ):
            raise ValueError(
                f"BlockModel '{blkmdl.name}' must have finite, nonzero cell spacing "
                f"along the {axis} axis."
            )
        if not np.allclose(cells, cells[0], rtol=1e-10, atol=1e-12):
            raise ValueError(
                f"BlockModel '{blkmdl.name}' has variable cell spacing along the "
                f"{axis} axis. Only uniform spacing within each axis is supported."
            )


def blockmodel_to_vtk(blkmdl: BlockModel) -> pyvista.ImageData:
    """Convert a uniformly spaced block model to a ``pyvista.ImageData``.

    This function converts the block model geometry and transfers all associated
    data.

    Parameters
    ----------
    blkmdl : geoh5py.objects.block_model.BlockModel
        The block model to convert.

    Returns
    -------
    pyvista.ImageData
        The converted block model.

    Raises
    ------
    ValueError
        If cell spacing is not uniform within each axis.

    """
    rotation_mtx = _create_blockmodel_rot_matrix(blkmdl)
    output = blockmodel_grid_geom_to_image_vtk(blkmdl, rotation_matrix=rotation_mtx)

    output = add_data_to_vtk_grid(output, blkmdl)
    output = add_entity_metadata(output, blkmdl)
    return output


def vtk_geom_to_blockmodel(
    vtk: pyvista.ImageData, workspace: Workspace, name: str
) -> BlockModel:
    """Convert a ``pyvista.ImageData`` to a ``geoh5py.objects.block_model.BlockModel``.

    Parameters
    ----------
    vtk : pyvista.ImageData
        A 3D grid with horizontal U/V axes and a vertical Z axis.
        Rotation and axis reflections are supported; tilt and shear are not.
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
    TypeError
        If the input is not ImageData. StructuredGrid conversion is unsupported.
    ValueError
        If the grid is not three-dimensional or its geometry cannot be
        represented by a BlockModel.

    """

    if not isinstance(vtk, pyvista.ImageData):
        raise TypeError(
            "BlockModel conversion only supports pyvista.ImageData with uniform "
            "spacing within each axis; StructuredGrid conversion is not supported."
        )

    if any(dimension < 2 for dimension in vtk.dimensions):
        raise ValueError("BlockModel conversion requires at least one cell in each axis.")
    spacing = np.asarray(vtk.spacing, dtype=np.float64)
    origin = np.asarray(vtk.origin, dtype=np.float64)
    direction = vtk.direction_matrix
    if (
        not np.all(np.isfinite(spacing))
        or np.any(spacing == 0)
        or not np.all(np.isfinite(origin))
        or not np.all(np.isfinite(direction))
    ):
        raise ValueError("BlockModel conversion requires finite geometry and nonzero spacing.")

    angle = np.arctan2(direction[1, 0], direction[0, 0])
    rotation_matrix = xy_rotation_matrix(angle)
    # A reversed U axis is absorbed into rotation; V/Z retain their signs.
    signs = np.array(
        [1.0, np.sign(np.linalg.det(direction[:2, :2])), np.sign(direction[2, 2])]
    )
    if np.any(signs == 0) or not np.allclose(
        direction, rotation_matrix @ np.diag(signs), rtol=0, atol=1e-10
    ):
        raise ValueError(
            "BlockModel conversion requires orthonormal horizontal U/V axes and "
            "a vertical Z axis; tilted, sheared, or scaled directions are not supported."
        )

    # ImageData extents may start at nonzero indices (e.g. after cropping).
    origin = origin + direction @ (np.asarray(vtk.extent[::2]) * spacing)
    steps = spacing * signs
    u_cell_delimiters, v_cell_delimiters, z_cell_delimiters = (
        np.arange(dimension, dtype=np.float64) * step
        for dimension, step in zip(vtk.dimensions, steps)
    )
    rotation = float(np.rad2deg(angle))

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
    vtk: pyvista.ImageData, workspace: Workspace, name: str
) -> ObjectBase:
    """Convert a ``pyvista.ImageData`` to a ``geoh5py.objects.block_model.BlockModel``.

    This is a wrapper for ``vtk_geom_to_blockmodel`` and is intended to be the
    main entry point for geometry and data conversion.

    Parameters
    ----------
    vtk : pyvista.ImageData
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
    )
    return blockmodel
