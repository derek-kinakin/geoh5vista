"""Methods to convert surface objects to VTK data objects"""


__all__ = [
    "surface_to_vtk",
]

__displayname__ = "Surface"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data, add_texture_coordinates


def surface_geom_to_vtk(trisurf, origin=(0.0, 0.0, 0.0)):
    """Convert the triangulated surface to a :class:`pyvista.PolyData`
    object

    Args:
        trisurf (:class:`geoh5py.objects.surface.Surface`): the surface to
            convert
    """
    pts = trisurf.vertices
    faces = trisurf.cells
    output = pyvista.make_tri_mesh(pts, faces)
    output.points += np.array(origin)
    return output


def surface_to_vtk(trisurf, origin=(0.0, 0.0, 0.0)):
    """Convert the surface to a its appropriate VTK data object type.

    Args:
        trisurf (:class:`geoh5py.objects.surface.Surface`): the surface element to
            convert
    """

    output = surface_geom_to_vtk(trisurf, origin=origin)

    # Now add point data:
    add_data(output, trisurf)

    return output


surface_to_vtk.__displayname__ = "Surface to VTK"
surface_geom_to_vtk.__displayname__ = "Surface Geometry to VTK"

surface_to_vtk.__displayname__ = "Surface to VTK"
