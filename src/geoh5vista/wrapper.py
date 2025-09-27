"""This module provides a high-level wrapper for converting geoh5py objects to PyVista objects."""

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
from geoh5vista.blockmodel import blockmodel_to_vtk
from geoh5vista.octree import octree_to_vtk
from geoh5vista.drillholes import drillholes_to_vtk


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
    """Converts an list of GEOH5 entities to collection in a :class:`pyvista.MultiBlock` 
    data object.

    """
    # Iterate over the elements and add converted VTK objects a MultiBlock
    data = pyvista.MultiBlock()
    for item in entity_list:
        key = item.__class__.__name__
        if key in SUPPORTED:
            e = geoh5wrap(item)
            data.append(e, name=e.user_dict["name"])
        else:
            pass
    return data


def read_workspace(workspace_path, load_visible=False):
    """Loads an GEOH5 workspace from a filepath to return a list of child entities.

    """
    wp = Workspace(workspace_path)
    #entities = wp.fetch_children(wp.root, recursively=True)
    entities = wp.objects
    supported_entities = [e for e in entities if e.__class__.__name__ in SUPPORTED]
    if load_visible:
        supported_entities = [e for e in supported_entities if e.visible["Visible"].any()]

    return entities_to_vtk(supported_entities)


GEOH5WRAPPERS = {
    ## Basic entities
    "Points": points_to_vtk,
    "Curve": curve_to_vtk,
    "Surface": surface_to_vtk,
    ## Grid entities
    "Grid2D": grid2d_to_vtk,
    ## Volume entities
    "BlockModel": blockmodel_to_vtk,
    "Octree": octree_to_vtk,
    ## Container entities
    "Drillhole": drillholes_to_vtk,
    "DrillholeGroup": drillholes_to_vtk,
    "ConcatenatorDrillholeGroup": drillholes_to_vtk,
    "ConcatenatedDrillhole": drillholes_to_vtk,
}


SUPPORTED = [
    "Points",
    "Curve",
    "Surface",
    "Grid2D",
    "BlockModel",
    "Octree",
    "DrillholeGroup",
    "ConcatenatorDrillholeGroup",
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
