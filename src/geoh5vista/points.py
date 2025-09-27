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
    """Convert the points to a :class:`pyvista.PointSet` data object.
    Args:
        pts: The points to convert
    Return:
        A :class:`pyvista.PointSet`
    """
    points = pts.vertices
    output = pyvista.PointSet(points)

    return output


def points_to_vtk(pts: Points) -> pyvista.PointSet:
    """Convert the points to a :class:`pyvista.PointSet` data object.
    Args:
        pts: The points to convert
    Return:
        A :class:`pyvista.PointSet`
    """
    output = points_geom_to_vtk(pts)

    # Now add point data:
    output = add_data_to_vtk(output, pts)
    output = add_entity_metadata(output, pts)

    return output


def vtk_geom_to_points(vtk: pyvista.PointSet, workspace: Workspace, name: str) -> Points:
    """Convert a VTK object to a geoh5py Points object."""

    points = Points.create(workspace=workspace, name=name, vertices=vtk.points)
    return points


def vtk_to_points(vtk: pyvista.PointSet, workspace: Workspace, name: str) -> Points:
    """Convert a VTK object to a geoh5py Points object."""
    points = vtk_geom_to_points(vtk=vtk, workspace=workspace, name=name)
    return points


points_geom_to_vtk.__displayname__ = "Points Geometry to VTK"  # type: ignore
points_to_vtk.__displayname__ = "Points to VTK"  # type: ignore
vtk_geom_to_points.__displayname__ = "VTK Geometry to Points" # type: ignore
vtk_to_points.__displayname__ = "VTK to Points" # type: ignore
