"""This module provides a wrapper that will work for any GEOH5 data object or
project files.

"""

__all__ = [
    "wrap",
    "project_to_vtk",
    "load_project",
]

__displayname__ = "Wrapper"

import numpy as np
import geoh5py
from geoh5py.workspace import Workspace

import pyvista

import geoh5vista
from geoh5vista.curve import curve_to_vtk
from geoh5vista.data import text_data_to_vtk, float_data_to_vtk, referenced_data_to_vtk, integer_data_to_vtk, filename_data_to_vtk
from geoh5vista.points import points_to_vtk
from geoh5vista.surface import surface_geom_to_vtk, surface_to_vtk
from geoh5vista.grid2d import grid2d_to_vtk
from geoh5vista.geoimage import geoimage_to_vtk
from geoh5vista.utilities import get_textures, texture_to_vtk
from geoh5vista.blockmodel import blockmodel_grid_geom_to_vtk, blockmodel_to_vtk
from geoh5vista.group import group_to_vtk


def wrap(data, origin=(0.0, 0.0, 0.0)):
    """Wraps the GEOH5 data object/project as a VTK data object. This is the
    primary function that an end user will harness.

    Args:
        data: any GEOH5 data object

    """
    # Allow recursion
    if isinstance(data, (list, tuple)):
        multi = pyvista.MultiBlock()
        for i, item in enumerate(data):
            multi.append(wrap(item))
            multi.set_block_name(i, item.name)
        return multi
    # get the class name
    key = data.__class__.__name__
    try:
        if key != "Project":
            return WRAPPERS[key](data, origin=origin)
        else:
            # Project is a special case
            return WRAPPERS[key](data)
    except KeyError:
        raise RuntimeError("Data of type ({}) is not supported currently.".format(key))


def project_to_vtk(project, load_textures=False):
    """Converts an Geoh5 workspace (:class:`geoh5py.workspace.workspace.Workspace`) to a
    :class:`pyvista.MultiBlock` data oject
    """
    # Iterate over the elements and add converted VTK objects a MultiBlock
    data = pyvista.MultiBlock()
    textures = {}
    origin = np.array([0,0,0])
    for e in project:
        key = e.__class__.__name__
        if key in SKIP:
            pass
        else:
            d = geoh5vista.wrap(e, origin=origin)
            data[e.name] = d
            if hasattr(e, "textures") and e.textures:
                textures[e.name] = get_textures(e)
    if load_textures:
        return data, textures
    return data


def load_project(filename, load_textures=False):
    """Loads an Geoh5 file into a :class:`pyvista.MultiBlock` dataset"""
    wp = Workspace(filename)
    project = wp.fetch_children(wp.root, recursively=True)
        
    return project_to_vtk(project, load_textures=load_textures)



WRAPPERS = {
    "Curve": curve_to_vtk,
    "Points": points_to_vtk,
    #"ReferencedData": referenced_data_to_vtk,
    #"TextData": text_data_to_vtk,
    #"FloatData": float_data_to_vtk,
    #"IntegerData": integer_data_to_vtk,
    #"FilenameData": filename_data_to_vtk,
    "Points": points_to_vtk,
    # Surfaces
    "SurfaceGeometry": surface_geom_to_vtk,
    "Grid2D": grid2d_to_vtk,
    "GeoImage": geoimage_to_vtk,
    "Surface": surface_to_vtk,
    #"ImageTexture": texture_to_vtk,
    # Volumes
    "BlockModelGeometry": blockmodel_grid_geom_to_vtk,
    "BlockModel": blockmodel_to_vtk,
    "Project": project_to_vtk,
    #"ContainerGroup": group_to_vtk,
}


SKIP = [
    "ReferencedData",
    "TextData",
    "FloatData",
    "IntegerData",
    "FilenameData",
    "ContainerGroup"
]

# Now set up the display names for the docs
load_project.__displayname__ = "Load Project File"
project_to_vtk.__displayname__ = "Project to VTK"
wrap.__displayname__ = "The Wrapper"
