"""This module provides functions for converting geoh5py Grid2D objects to and from PyVista data objects."""

from __future__ import annotations

import numpy as np
import pyvista
from typing import Final
from geoh5py.objects.grid2d import Grid2D
from geoh5py.workspace.workspace import Workspace

from geoh5py.shared.utils import xy_rotation_matrix, yz_rotation_matrix
from geoh5vista.data import add_data_to_vtk, add_entity_metadata, add_data_to_geoh5


__all__ = (
    "grid2d_geom_to_vtk",
    "grid2d_to_vtk",
    "vtk_geom_to_grid2d",
    "vtk_to_grid2d",
    "MODULE_DISPLAY_NAME",
    "FUNCTION_DISPLAY_NAMES"
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

    output = pyvista.ImageData()
    output.dimensions = [int(grd.u_count), int(grd.v_count), 1]
    output.spacing = [grd.u_cell_size, grd.v_cell_size, 1.0]
    output.direction_matrix = rotation_mtx
    output.origin = grd.origin

    return output


def grid2d_to_vtk(grd: Grid2D) -> pyvista.DataSet:
    """Convert a ``geoh5py.objects.grid2d.Grid2D`` to a ``pyvista.DataSet`` object.

    This function converts the grid geometry and transfers all associated data.

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


def vtk_geom_to_grid2d(vtk: pyvista.ImageData | pyvista.UnstructuredGrid, workspace: Workspace, name: str) -> Grid2D:
    """Convert a ``pyvista.ImageData`` object to a ``geoh5py.objects.surface.Surface`` object.

    Parameters
    ----------
    vtk : pyvista.ImageData | pyvista.UnstructuredGrid
        The VTK object to convert. It must be a 2D ImageData object.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new surface to.
    name : str
        The name of the new surface.

    Returns
    -------
    geoh5py.objects.grid2d.Grid2D
        The newly created grid2d.

    Raises
    ------
    ValueError
        If the VTK object is not a 2D ImageData object.

    """
    if vtk.direction_matrix is None:    
        horizontal_rotation = np.rad2deg(0.0)
        dip_from_horizontal = np.rad2deg(0.0)
    else:
        # Extract rotation angles from direction matrix
        # The matrix is composed as: R_horizontal @ R_vertical
        direction_mtx = vtk.direction_matrix[:3, :3]
        horizontal_rotation = np.rad2deg(np.arctan2(direction_mtx[1, 0], direction_mtx[0, 0]))
        dip_from_horizontal = np.rad2deg(np.arcsin(direction_mtx[2, 1]))
    
    grid2d = Grid2D.create(
        workspace=workspace,
        name=name,
        origin=vtk.origin,
        u_cell_size=vtk.spacing[0],
        v_cell_size=vtk.spacing[1],
        u_count=vtk.dimensions[0],
        v_count=vtk.dimensions[1],
        rotation=horizontal_rotation,
        dip=dip_from_horizontal,
        )
    return grid2d


def vtk_to_grid2d(vtk: pyvista.ImageData | pyvista.UnstructuredGrid, workspace: Workspace, name: str) -> Grid2D:
    """Convert a ``pyvista.ImageData`` object to a ``geoh5py.objects.grid2d.Grid2D`` object.

    This is a wrapper for ``vtk_geom_to_grid2d`` and is intended to be the
    main entry point for this conversion. In the future, it will also handle
    transferring data from the VTK object to the geoh5py object.

    Parameters
    ----------
    vtk : pyvista.ImageData | pyvista.UnstructuredGrid
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
    grid2d = vtk_geom_to_grid2d(vtk=vtk, workspace=workspace, name=name)
    grid2d = add_data_to_geoh5(grid2d, vtk)
    return grid2d 
