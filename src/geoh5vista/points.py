"""This module provides functions for converting geoh5py Point objects to and from PyVista data objects."""

import pyvista
from geoh5py.objects.points import Points
from geoh5py.workspace.workspace import Workspace
from geoh5vista.data import add_data_to_vtk, add_entity_metadata

__all__ = [
    "points_geom_to_vtk",
    "points_to_vtk",
    "vtk_geom_to_points",
    "vtk_to_points"
]
__displayname__ = "Points"


def points_geom_to_vtk(pts: Points) -> pyvista.PointSet:
    """Convert the points geometry to a ``pyvista.PointSet`` object.

    Parameters
    ----------
    pts : geoh5py.objects.points.Points
        The points to convert.

    Returns
    -------
    pyvista.PointSet
        The points geometry as a PointSet object.

    """
    points = pts.vertices
    output = pyvista.PointSet(points)

    return output


def points_to_vtk(pts: Points) -> pyvista.PointSet:
    """Convert a ``geoh5py.objects.points.Points`` object to a ``pyvista.PointSet``.

    This function converts the points geometry and transfers all associated
    data.

    Parameters
    ----------
    pts : geoh5py.objects.points.Points
        The points to convert.

    Returns
    -------
    pyvista.PointSet
        The converted points.

    """
    output = points_geom_to_vtk(pts)

    # Now add point data:
    output = add_data_to_vtk(output, pts)
    output = add_entity_metadata(output, pts)

    return output


def vtk_geom_to_points(vtk: pyvista.PointSet, workspace: Workspace, name: str) -> Points:
    """Convert a ``pyvista.PointSet`` object to a ``geoh5py.objects.points.Points`` object.

    Parameters
    ----------
    vtk : pyvista.PointSet
        The VTK object to convert.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new points to.
    name : str
        The name of the new points.

    Returns
    -------
    geoh5py.objects.points.Points
        The newly created points.

    """

    points = Points.create(workspace=workspace, name=name, vertices=vtk.points)
    return points


def vtk_to_points(vtk: pyvista.PointSet, workspace: Workspace, name: str) -> Points:
    """Convert a ``pyvista.PointSet`` object to a ``geoh5py.objects.points.Points`` object.

    This is a wrapper for ``vtk_geom_to_points`` and is intended to be the
    main entry point for this conversion. In the future, it will also handle
    transferring data from the VTK object to the geoh5py object.

    Parameters
    ----------
    vtk : pyvista.PointSet
        The VTK object to convert.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new points to.
    name : str
        The name of the new points.

    Returns
    -------
    geoh5py.objects.points.Points
        The newly created points.

    """
    points = vtk_geom_to_points(vtk=vtk, workspace=workspace, name=name)
    return points


points_geom_to_vtk.__displayname__ = "Points Geometry to VTK"  # type: ignore
points_to_vtk.__displayname__ = "Points to VTK"  # type: ignore
vtk_geom_to_points.__displayname__ = "VTK Geometry to Points" # type: ignore
vtk_to_points.__displayname__ = "VTK to Points" # type: ignore
