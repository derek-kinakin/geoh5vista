"""Methods to convert points objects to VTK data objects"""


__all__ = [
    "points_to_vtk",
]

__displayname__ = "Points"

import numpy as np
import pyvista
from geoh5py.objects.points import Points

from geoh5vista.utilities import add_data, add_texture_coordinates


def points_to_vtk(pts, origin=(0.0, 0.0, 0.0)):
    """Convert the points to a :class:`pyvista.PolyData` data object.

    Args:
        pts (:class:`geoh5py.objects.points.Points`): The points to convert

    Return:
        :class:`pyvista.PolyData`
    """
    points = pts.vertices
    output = pyvista.PolyData(points)

    # Now add point data:
    add_data(output, pts)

    output.points += np.array(origin)
    return output


#def vtk_to_points(vtk, workspace, name):
#    points = Points.create(
#        workspace=workspace,
#        vertices=vtk.points,
#        name=name)
#    return points
    

points_to_vtk.__displayname__ = "Points to VTK"
#vtk_to_points.__displayname__ = "VTK to Points"
