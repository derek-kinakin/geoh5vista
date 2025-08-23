"""This module provides a wrapper that will work for any GEOH5 data object or file.

"""

__all__ = [
    "wrap",
    "workspace_to_vtk",
    "read_workspace",
]

__displayname__ = "Wrapper"

import pyvista
import numpy as np
from geoh5py.workspace.workspace import Workspace

from geoh5vista.curve import curve_to_vtk
from geoh5vista.points import points_to_vtk
from geoh5vista.surface import surface_geom_to_vtk, surface_to_vtk
from geoh5vista.grid2d import grid2d_to_vtk
from geoh5vista.geoimage import geoimage_to_vtk
#from geoh5vista.utilities import get_textures, texture_to_vtk
from geoh5vista.blockmodel import blockmodel_to_vtk
from geoh5vista.octree import octree_to_vtk
#from geoh5vista.group import group_to_vtk


def geoh5wrap(data, origin=(0.0, 0.0, 0.0)):
    """Wraps the GEOH5 data object/project as a VTK data object. This is the
    primary function that an end user will harness.

    """
    # Allow recursion
    if isinstance(data, (list, tuple)):
        multi = pyvista.MultiBlock()
        for i, item in enumerate(data):
            multi.append(geoh5wrap(item))
            multi.set_block_name(i, item.name)
        return multi
    # get the class name
    key = data.__class__.__name__
    try:
        if key != "Project":
            return GEOH5WRAPPERS[key](data, origin=origin)
        else:
            # Project is a special case
            return GEOH5WRAPPERS[key](data)
    except KeyError:
        raise RuntimeError(f"Data of type ({key}) is not supported currently.")


def workspace_to_vtk(workspace, load_textures=False):
    """Converts an GEOH5 workspace (:class:`geoh5py.workspace.workspace.Workspace`) to a
    :class:`pyvista.MultiBlock` data object
    """
    # Iterate over the elements and add converted VTK objects a MultiBlock
    data = pyvista.MultiBlock()
    textures = {}
    origin = np.array([0,0,0])
    #for e in project.elements:
    for e in workspace:
        key = e.__class__.__name__
        if key in GEOH5SKIP:
            pass
        else:
            d = geoh5wrap(e, origin=origin)
            data[d.user_dict["name"]] = d
            if hasattr(e, "textures") and e.textures:
                textures[d.user_dict["name"]] = get_textures(e)
    #if load_textures:
    #    return data, textures
    return data


def read_workspace(filename, load_textures=False):
    """Loads an Geoh5 workspace from a filepath into a :class:`pyvista.MultiBlock` dataset"""
    wp = Workspace(filename)
    project = wp.fetch_children(wp.root, recursively=True)

    return workspace_to_vtk(project, load_textures=load_textures)


GEOH5WRAPPERS = {
    "Points": points_to_vtk,
    "Curve": curve_to_vtk,
    # Surfaces
    "SurfaceGeometry": surface_geom_to_vtk,
    "Surface": surface_to_vtk,
    # Grids
    "Grid2D": grid2d_to_vtk,
    "GeoImage": geoimage_to_vtk,
    # Volumes
    "BlockModel": blockmodel_to_vtk,
    "Octree": octree_to_vtk,
    # Containers
    "Workspace": workspace_to_vtk,
    #"ContainerGroup": group_to_vtk,
    #"Drillholes": group_to_vtk,
}


GEOH5SKIP = [
    "ReferencedData",
    "TextData",
    "FloatData",
    "IntegerData",
    "FilenameData",
    "ContainerGroup",
    "VisualParameters",
    "GeometricDataConstants",
    "GeoImage",
    "Drillholes"
]

# Now set up the display names for the docs
read_workspace.__displayname__ = "Load Workspace File" # type: ignore
workspace_to_vtk.__displayname__ = "Workspace to VTK" # type: ignore
geoh5wrap.__displayname__ = "GEOH5 Entity Wrapper" # type: ignore
