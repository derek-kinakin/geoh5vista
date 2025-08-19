"""Methods to convert points objects to VTK data objects"""

import numpy as np
import pyvista
from geoh5py.objects.points import Points
from geoh5py.workspace.workspace import Workspace
from typing import Tuple

from geoh5vista.utilities import add_data_to_vtk, add_entity_metadata
# from geoh5vista.utilities import add_texture_coordinates

__all__ = ["points_to_vtk", "vtk_to_points"]
__displayname__ = "Points"


def points_geom_to_vtk(
    pts: Points, origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
) -> pyvista.PointSet:
    """Convert the points to a :class:`pyvista.PointSet` data object.
    Args:
        pts: The points to convert
    Return:
        A :class:`pyvista.PointSet`
    """
    points = pts.vertices
    output = pyvista.PointSet(points)

    return output


def points_to_vtk(
    pts: Points, origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
) -> pyvista.PointSet:
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

    # add_texture_coordinates(output, pts.textures, pts.name)

    output.points += np.array(origin)
    return output


def vtk_geom_to_points(vtk: pyvista.PointSet, workspace: Workspace, name: str) -> Points:
    """Convert a VTK object to a geoh5py Points object."""
    if name:
        name = name
    else:
        name = vtk.user_dict["name"]

    points = Points.create(workspace=workspace, vertices=vtk.points, name=name)
    return points


def vtk_to_points(vtk: pyvista.PointSet, workspace: Workspace, name: str) -> Points:
    """Convert a VTK object to a geoh5py Points object."""
    points = vtk_geom_to_points(vtk=vtk, workspace=workspace, name=name)
    return points


points_geom_to_vtk.__displayname__ = "Points Geometry to VTK"  # type: ignore
points_to_vtk.__displayname__ = "Points to VTK"  # type: ignore
vtk_geom_to_points.__displayname__ = "VTK Geometry to Points" # type: ignore
vtk_to_points.__displayname__ = "VTK to Points" # type: ignore
