"""This module provides a wrapper that will work for any GEOH5 data object or file.

"""

__all__ = [
    "geoh5wrap",
    "entities_to_vtk",
    "read_workspace",
]

__displayname__ = "Wrapper"

import pyvista
import numpy as np
from geoh5py.workspace.workspace import Workspace

from geoh5vista.curve import curve_to_vtk
from geoh5vista.points import points_to_vtk
from geoh5vista.surface import surface_to_vtk
from geoh5vista.grid2d import grid2d_to_vtk
from geoh5vista.geoimage import geoimage_to_vtk
#from geoh5vista.utilities import get_textures, texture_to_vtk
from geoh5vista.blockmodel import blockmodel_to_vtk
from geoh5vista.octree import octree_to_vtk
#from geoh5vista.group import group_to_vtk


def geoh5wrap(data, origin=(0.0, 0.0, 0.0)):
    """Wraps the GEOH5 data object as a VTK data object. This is the
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
        return GEOH5WRAPPERS[key](data, origin=origin)
    except KeyError:
        raise RuntimeError(f"Data of type ({key}) is not  currently supported.")


def entities_to_vtk(entity_list):
#def entities_to_vtk(entity_list, load_textures=False):
    """Converts an list of GEOH5 entities to collection in a :class:`pyvista.MultiBlock` data object

    """
    # Iterate over the elements and add converted VTK objects a MultiBlock
    data = pyvista.MultiBlock()
    #textures = {}
    origin = np.array([0,0,0])
    #for e in project.elements:
    for e in entity_list:
        key = e.__class__.__name__
        if key in GEOH5SKIP:
            pass
        else:
            d = geoh5wrap(e, origin=origin)
            data[d.user_dict["name"]] = d
            #if hasattr(e, "textures") and e.textures:
            #    textures[d.user_dict["name"]] = get_textures(e)
    #if load_textures:
    #    return data, textures
    return data


def read_workspace(filename, load_textures=False):
    """Loads an Geoh5 workspace from a filepath to return a list of child entities.

    """
    wp = Workspace(filename)
    entities = wp.fetch_children(wp.root, recursively=True)

    #return entities_to_vtk(entities, load_textures=load_textures)
    return entities_to_vtk(entities)


GEOH5WRAPPERS = {
    ## Basic entities
    "Points": points_to_vtk,
    "Curve": curve_to_vtk,
    "Surface": surface_to_vtk,
    ## Grid entities
    "Grid2D": grid2d_to_vtk,
    "GeoImage": geoimage_to_vtk,
    ## Volume entities
    "BlockModel": blockmodel_to_vtk,
    "Octree": octree_to_vtk,
    ## Container entities
    #"Drillholes": group_to_vtk,
    #"ContainerGroup": group_to_vtk,
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
read_workspace.__displayname__ = "Load a GEOH5 Workspace File" # type: ignore
entities_to_vtk.__displayname__ = "Entities to VTK" # type: ignore
geoh5wrap.__displayname__ = "GEOH5 Entity Wrapper" # type: ignore
