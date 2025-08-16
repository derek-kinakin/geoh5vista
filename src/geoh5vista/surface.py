"""Methods to convert surface objects to VTK data objects"""


__all__ = [
    "surface_to_vtk",
]

__displayname__ = "Surface"

import numpy as np
import pyvista
from geoh5py.workspace import Workspace
from geoh5py.objects import Surface

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


def vtk_geom_to_surface_geom(vtk_obj, gh5wkspc, obj_nm):
    """Convert a VTK object to a surface geometry object

    Args:
        vtk_obj (:class:`pyvista.PolyData` or :class:'pyvista.UnstructuredGrid'): the VTK object to convert
    """
    vrts = vtk_obj.points
    if isinstance(vtk_obj, pyvista.PolyData):
        clls = vtk_obj.faces.reshape((vtk_obj.n_faces, 4))[:, 1:]
    elif isinstance(vtk_obj, pyvista.UnstructuredGrid):
        clls = vtk_obj.cells.reshape((vtk_obj.n_cells, 4))[:, 1:]
    else:
        raise ValueError("Mesh type not supported.")
    
    srfc = Surface.create(gh5wkspc, vertices=vrts, cells=clls, name=obj_nm)
    return srfc


surface_to_vtk.__displayname__ = "Surface to VTK"
surface_geom_to_vtk.__displayname__ = "Surface Geometry to VTK"
surface_to_vtk.__displayname__ = "Surface to VTK"
vtk_geom_to_surface_geom.__displayname__ = "VTK to Surface Geometry"
