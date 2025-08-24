"""This module provides a wrapper that will work for any GEOH5 data object or file.

"""

__all__ = [
    "geoh5wrap",
    "entities_to_vtk",
    "read_workspace",
]

__displayname__ = "Wrapper"

import pyvista
from geoh5py.workspace.workspace import Workspace

from geoh5vista.curve import curve_to_vtk
from geoh5vista.points import points_to_vtk
from geoh5vista.surface import surface_to_vtk
from geoh5vista.grid2d import grid2d_to_vtk
from geoh5vista.geoimage import geoimage_to_vtk
from geoh5vista.blockmodel import blockmodel_to_vtk
from geoh5vista.octree import octree_to_vtk
from geoh5vista.drillholes import drillholes_to_vtk
#from geoh5vista.utilities import get_textures, texture_to_vtk


def geoh5wrap(data):
    """Wraps the GEOH5 data object as a VTK data object. This is the
    primary function that an end user will harness.

    """
    if data is None:
        return None
    else:
        key = data.__class__.__name__ # get the class name
        try:
            return GEOH5WRAPPERS[key](data)
        except KeyError:
            raise RuntimeError(f"Data of type ({key}) is not  currently supported.")


def entities_to_vtk(entity_list):
#def entities_to_vtk(entity_list, load_textures=False):
    """Converts an list of GEOH5 entities to collection in a :class:`pyvista.MultiBlock` 
    data object.

    """
    # Iterate over the elements and add converted VTK objects a MultiBlock
    data = pyvista.MultiBlock()
    #textures = {}
    for item in entity_list:
        key = item.__class__.__name__
        if key in SUPPORTED:
            e = geoh5wrap(item)
            data.append(e, name=e.user_dict["name"])
            #if hasattr(e, "textures") and e.textures:
            #    textures[d.user_dict["name"]] = get_textures(e)
        else:
            pass
    #if load_textures:
    #    return data, textures
    return data


def read_workspace(workspace_path, load_textures=False):
    """Loads an GEOH5 workspace from a filepath to return a list of child entities.

    """
    wp = Workspace(workspace_path)
    entities = wp.fetch_children(wp.root, recursively=True)
    supported_entities = [e for e in entities if e.__class__.__name__ in SUPPORTED]

    #return entities_to_vtk(entities, load_textures=load_textures)
    return entities_to_vtk(supported_entities)


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
    "Drillholes": drillholes_to_vtk,
    #"ContainerGroup": group_to_vtk,
}


SUPPORTED = [
    "Points",
    "Curve",
    "Surface",
    "Grid2D",
    "BlockModel",
    "Octree",
    "Drillholes",
]

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
    "Drillholes",
    "DrapeModel",
    "AirborneMagnetics",
    "PotentialElectrode",
    "AirborneEMSurvey",
    "AirborneTEMSurvey",
    "AirborneTEMReceivers",
    "AirborneFEMTransmitters",
    "VP Model",
    "UIJsonGroup",
    "InterpretationSection",
    "Slicer",
    "BooleanData",
    "PropertyGroup",
    "CommentsData",
    "ConcatenatorDrillholeGroup",
    "ConcatenatedDrillhole",
    "CustomGroup"
]

# Now set up the display names for the docs
read_workspace.__displayname__ = "Load a GEOH5 Workspace File" # type: ignore
entities_to_vtk.__displayname__ = "Entities to VTK" # type: ignore
geoh5wrap.__displayname__ = "GEOH5 Entity Wrapper" # type: ignore
