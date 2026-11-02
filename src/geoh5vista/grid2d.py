"""This module provides functions for converting geoh5py Grid2D objects to and from PyVista data objects."""

from __future__ import annotations

from typing import Final

import numpy as np
import pyvista
from geoh5py.objects.grid2d import Grid2D
from geoh5py.shared.utils import xy_rotation_matrix, yz_rotation_matrix
from geoh5py.workspace.workspace import Workspace

from geoh5vista.data import (
    add_data_to_geoh5,
    add_data_to_vtk,
    add_entity_metadata,
    restore_entity_metadata,
)

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "grid2d_geom_to_vtk",
    "grid2d_to_vtk",
    "vtk_geom_to_grid2d",
    "vtk_to_grid2d",
)


MODULE_DISPLAY_NAME: Final[str] = "Grid2D"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "grid2d_geom_to_vtk": "Grid2D Geometry to VTK",
    "grid2d_to_vtk": "Grid2D to VTK",
    "vtk_geom_to_grid2d": "VTK Geometry to Grid2D",
    "vtk_to_grid2d": "VTK to Grid2D",
}


def grid2d_geom_to_vtk(grd: Grid2D) -> pyvista.ImageData:
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
    if grd.u_cell_size is None or grd.v_cell_size is None:
        raise ValueError("Grid2D must have cell sizes defined.")
    if grd.origin is None:
        raise ValueError("Grid2D must have an origin defined.")
    if grd.u_count is None or grd.v_count is None:
        raise ValueError("Grid2D must have cell counts defined.")
    if grd.rotation is None:
        raise ValueError("Grid2D must have a rotation defined.")

    if grd.vertical:
        dip = np.deg2rad(90)
    else:
        dip = np.deg2rad(grd.dip if grd.dip is not None else 0.0)

    horizontal_rotation = np.deg2rad(grd.rotation)

    # Combine horizontal and vertical rotations
    rotation_mtx_vertical = yz_rotation_matrix(dip)
    rotation_mtx_horizontal = xy_rotation_matrix(horizontal_rotation)
    rotation_mtx = rotation_mtx_horizontal @ rotation_mtx_vertical

    steps = np.array([grd.u_cell_size, grd.v_cell_size, 1.0], dtype=np.float64)
    origin = np.asarray(grd.origin.tolist(), dtype=np.float64)
    if not np.all(np.isfinite(steps)) or np.any(steps == 0):
        raise ValueError("Grid2D requires finite, nonzero cell sizes.")
    if not np.all(np.isfinite(origin)) or not np.all(np.isfinite(rotation_mtx)):
        raise ValueError("Grid2D requires finite origin, rotation, and dip.")
    if grd.u_count < 1 or grd.v_count < 1:
        raise ValueError("Grid2D requires at least one cell along U and V.")

    output = pyvista.ImageData(
        dimensions=(int(grd.u_count) + 1, int(grd.v_count) + 1, 1),
        spacing=np.abs(steps),
        direction_matrix=rotation_mtx @ np.diag(np.sign(steps)),
        origin=origin,
    )

    return output


def grid2d_to_vtk(grd: Grid2D) -> pyvista.DataSet:
    """Convert a ``geoh5py.objects.grid2d.Grid2D`` to a ``pyvista.DataSet`` object.

    Native cell values are stored in ``cell_data``, in U-fastest order.
    Image dimensions are ``(u_count + 1, v_count + 1, 1)``.

    Parameters
    ----------
    grd : geoh5py.objects.grid2d.Grid2D
        The 2D grid to convert.

    Returns
    -------
    pyvista.DataSet
        The converted 2D grid.

    """
    output = grid2d_geom_to_vtk(grd)
    output = add_data_to_vtk(output, grd)
    output = add_entity_metadata(output, grd)

    return output


def vtk_geom_to_grid2d(
    vtk: pyvista.ImageData, workspace: Workspace, name: str
) -> Grid2D:
    """Convert a two-dimensional ImageData's cell geometry to Grid2D.

    Parameters
    ----------
    vtk : pyvista.ImageData
        Image with at least two points along U and V and one along W.
        U must be horizontal; V may be dipped or vertical. Directions must
        be orthonormal. Nonzero extents are incorporated into the origin.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new grid to.
    name : str
        The name of the new grid.

    Returns
    -------
    geoh5py.objects.grid2d.Grid2D
        The newly created grid2d.

    Raises
    ------
    ValueError
        If the VTK object is not a 2D ImageData object.

    """
    if not isinstance(vtk, pyvista.ImageData):
        raise TypeError("Grid2D conversion only supports pyvista.ImageData.")
    if vtk.dimensions[0] < 2 or vtk.dimensions[1] < 2 or vtk.dimensions[2] != 1:
        raise ValueError(
            "Grid2D requires a 2D U/V image with at least one cell in each axis."
        )

    spacing = np.asarray(vtk.spacing, dtype=np.float64)
    origin = np.asarray(vtk.origin, dtype=np.float64)
    direction = vtk.direction_matrix
    if (
        not np.all(np.isfinite(spacing))
        or np.any(spacing == 0)
        or not np.all(np.isfinite(origin))
        or not np.all(np.isfinite(direction))
    ):
        raise ValueError(
            "Grid2D conversion requires finite geometry and nonzero spacing."
        )
    if not np.allclose(direction.T @ direction, np.eye(3), rtol=0, atol=1e-10):
        raise ValueError(
            "Grid2D requires orthonormal directions; shear and scale are unsupported."
        )
    if not np.isclose(direction[2, 0], 0.0, rtol=0, atol=1e-10):
        raise ValueError("Grid2D requires a horizontal U axis.")

    angle = np.arctan2(direction[1, 0], direction[0, 0])
    local_v = xy_rotation_matrix(angle).T @ direction[:, 1]
    dip = np.arctan2(local_v[2], local_v[1])
    # Extents index the image in local space, including its singleton W plane.
    origin = origin + direction @ (np.asarray(vtk.extent[::2]) * spacing)

    grid2d = Grid2D.create(
        workspace=workspace,
        name=name,
        origin=origin,
        u_cell_size=spacing[0],
        v_cell_size=spacing[1],
        u_count=vtk.dimensions[0] - 1,
        v_count=vtk.dimensions[1] - 1,
        rotation=float(np.rad2deg(angle)),
        dip=float(np.rad2deg(dip)),
    )
    return grid2d


def vtk_to_grid2d(vtk: pyvista.ImageData, workspace: Workspace, name: str) -> Grid2D:
    """Convert a ``pyvista.ImageData`` object to a ``geoh5py.objects.grid2d.Grid2D`` object.

    Cell arrays retain their U-fastest ordering. Point arrays are rejected
    because Grid2D stores cell values; convert them to cell data explicitly
    before export. Input geometry and arrays are not modified.

    Parameters
    ----------
    vtk : pyvista.ImageData
        The VTK object to convert.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new grid2d to.
    name : str
        The name of the new grid2d.

    Returns
    -------
    geoh5py.objects.grid2d.Grid2D
        The newly created grid2d.

    """
    if not isinstance(vtk, pyvista.ImageData):
        raise TypeError("Grid2D conversion only supports pyvista.ImageData.")
    if vtk.point_data:
        raise ValueError(
            "Grid2D cannot store point data; convert point arrays to cell data before export."
        )
    grid2d = vtk_geom_to_grid2d(vtk=vtk, workspace=workspace, name=name)
    grid2d = add_data_to_geoh5(grid2d, vtk)
    grid2d = restore_entity_metadata(grid2d, vtk)
    return grid2d
