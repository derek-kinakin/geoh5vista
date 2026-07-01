"""This module provides functions for converting geoh5py Surface objects to and from PyVista data objects."""


__all__ = [
    "surface_geom_to_vtk",
    "surface_to_vtk",
    "vtk_geom_to_surface",
    "vtk_to_surface"
]

__displayname__ = "Surface"


import pyvista
import numpy as np
from typing import Union
from geoh5py.objects.object_base import ObjectBase
from geoh5py.objects.surface import Surface
from geoh5py.workspace.workspace import Workspace
from geoh5vista.data import add_data_to_vtk, add_entity_metadata, add_data_to_geoh5


def _validate_surface_geometry(vertices: np.ndarray | None, cells: np.ndarray | None) -> None:
    if vertices is None or cells is None:
        raise ValueError("Surface must have vertices and cells defined.")

    vertices = np.asarray(vertices, dtype=float)
    cells = np.asarray(cells, dtype=int)

    if vertices.ndim != 2 or vertices.shape[1] != 3 or vertices.shape[0] < 3:
        raise ValueError("Surface vertices must have shape (n, 3) with n >= 3.")
    if cells.ndim != 2 or cells.shape[1] != 3 or cells.shape[0] < 1:
        raise ValueError("Surface cells must have shape (m, 3) with m >= 1.")
    if not np.isfinite(vertices).all():
        raise ValueError("Surface vertices must be finite numbers.")

    if (cells < 0).any() or (cells >= vertices.shape[0]).any():
        raise ValueError("Surface cells contain out-of-range vertex indices.")
    if ((cells[:, 0] == cells[:, 1]) | (cells[:, 1] == cells[:, 2]) | (cells[:, 0] == cells[:, 2])).any():
        raise ValueError("Surface cells must reference 3 distinct vertices.")

    tri = vertices[cells]
    area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    if not np.any(area2 > 0.0):
        raise ValueError("Surface geometry is degenerate (zero-area triangles only).")


def surface_geom_to_vtk(trisurf: Surface) -> pyvista.PolyData:
    """Convert the triangulated surface geometry to a ``pyvista.PolyData`` object.

    Parameters
    ----------
    trisurf : geoh5py.objects.surface.Surface
        The surface to convert.

    Returns
    -------
    pyvista.PolyData
        The surface geometry as a PolyData object.

    """
    _validate_surface_geometry(trisurf.vertices, trisurf.cells)
    return pyvista.make_tri_mesh(trisurf.vertices, trisurf.cells)


def surface_to_vtk(trisurf: Surface) -> pyvista.DataSet:
    """Convert a ``geoh5py.objects.surface.Surface`` to a ``pyvista.PolyData`` object.

    This function converts the surface geometry and transfers all associated
    data.

    Parameters
    ----------
    trisurf : geoh5py.objects.surface.Surface
        The surface to convert.

    Returns
    -------
    pyvista.DataSet
        The converted surface.

    """

    output = surface_geom_to_vtk(trisurf)

    # Now add point data:
    output = add_data_to_vtk(output, trisurf)
    output = add_entity_metadata(output, trisurf)

    return output


def vtk_geom_to_surface(vtk: Union[pyvista.PolyData, pyvista.UnstructuredGrid], workspace: Workspace, name: str) -> Surface:
    """Convert a ``pyvista.PolyData`` object to a ``geoh5py.objects.surface.Surface`` object.

    Parameters
    ----------
    vtk : pyvista.PolyData
        The VTK object to convert. It must be a triangular mesh.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new surface to.
    name : str
        The name of the new surface.

    Returns
    -------
    geoh5py.objects.surface.Surface
        The newly created surface.

    Raises
    ------
    ValueError
        If the VTK object is not a triangular mesh PolyData object.

    """

    points = vtk.points
    # extract triangle faces without VTK padding
    cells = vtk.faces.reshape((vtk.n_cells, 4))[:, 1:]

    surface = Surface.create(workspace=workspace, name=name, vertices=points, cells=cells)
    return surface


def vtk_to_surface(vtk: Union[pyvista.PolyData, pyvista.UnstructuredGrid], workspace: Workspace, name: str) -> ObjectBase:
    """Convert a ``pyvista.PolyData`` object to a ``geoh5py.objects.surface.Surface`` object.

    This is a wrapper for ``vtk_geom_to_surface`` and is intended to be the
    main entry point for this conversion. In the future, it will also handle
    transferring data from the VTK object to the geoh5py object.

    Parameters
    ----------
    vtk : pyvista.PolyData
        The VTK object to convert.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new surface to.
    name : str
        The name of the new surface.

    Returns
    -------
    geoh5py.objects.surface.Surface
        The newly created surface.

    """
    surface = vtk_geom_to_surface(vtk=vtk, workspace=workspace, name=name)
    surface = add_data_to_geoh5(surface, vtk)
    return surface


# Now set up the display names for the docs
surface_to_vtk.__displayname__ = "Surface to VTK" # type: ignore
surface_geom_to_vtk.__displayname__ = "Surface Geometry to VTK" # type: ignore
vtk_geom_to_surface.__displayname__ = "VTK Geometry to Surface" # type: ignore
vtk_to_surface.__displayname__ = "VTK to Surface" # type: ignore
