"""Methods to convert surface objects to VTK data objects"""


__all__ = [
    "surface_to_vtk",
]

__displayname__ = "Surface"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data_to_vtk, add_ga_entity_colour #, add_texture_coordinates 


def surface_geom_to_vtk(trisurf, origin=(0.0, 0.0, 0.0)):
    """Convert the triangulated surface to a :class:`pyvista.PolyData`
    object

    Args:
        trisurf (:class:`geoh5py.objects.surface.Surface`): the surface to
            convert
    """
    pts = trisurf.vertices
    pts += np.array(origin, dtype=np.float64)
    faces = trisurf.cells
    output = pyvista.make_tri_mesh(pts, faces)
    return output


def surface_to_vtk(trisurf, origin=(0.0, 0.0, 0.0)):
    """Convert the surface to a its appropriate VTK data object type.

    Args:
        trisurf (:class:`geoh5py.objects.surface.Surface`): the surface element to
            convert
    """

    output = surface_geom_to_vtk(trisurf, origin=origin)

    # Now add point data:
    add_data_to_vtk(output, trisurf)

    # Add the GA entity colour
    add_ga_entity_colour(output, trisurf)
    #add_texture_coordinates(output, trisurf.textures, trisurf.name)

    return output

# Now set up the display names for the docs
surface_to_vtk.__displayname__ = "Surface to VTK" # type: ignore
surface_geom_to_vtk.__displayname__ = "Surface Geometry to VTK" # type: ignore
surface_to_vtk.__displayname__ = "Surface to VTK" # type: ignore
