"""Methods to convert surface objects to VTK data objects"""


__all__ = [
    "surface_geom_to_vtk",
    "surface_to_vtk",
    "vtk_geom_to_surface",
    "vtk_to_surface"
]

__displayname__ = "Surface"

import numpy as np
import pyvista
from geoh5py.objects.surface import Surface
from geoh5py.workspace.workspace import Workspace
from geoh5vista.utilities import add_data_to_vtk, add_entity_metadata #, add_texture_coordinates


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
    output = add_data_to_vtk(output, trisurf)
    output = add_entity_metadata(output, trisurf)
    #add_texture_coordinates(output, trisurf.textures, trisurf.name)

    return output


def vtk_geom_to_surface(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Surface:
    """Convert a VTK object to a geoh5py Surface object."""
    if name:
        name = name
    else:
        name = vtk.user_dict["name"]

    surface = Surface.create(workspace=workspace, vertices=vtk.points, name=name)
    return surface


def vtk_to_surface(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Surface:
    """Convert a VTK object to a geoh5py Surface object."""
    surface = vtk_geom_to_surface(vtk=vtk, workspace=workspace, name=name)
    return surface


# Now set up the display names for the docs
surface_to_vtk.__displayname__ = "Surface to VTK" # type: ignore
surface_geom_to_vtk.__displayname__ = "Surface Geometry to VTK" # type: ignore
vtk_geom_to_surface.__displayname__ = "VTK Geometry to Surface" # type: ignore
vtk_to_surface.__displayname__ = "VTK to Surface" # type: ignore
