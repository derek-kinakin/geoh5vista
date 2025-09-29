"""This module provides a high-level wrapper for converting geoh5py objects to PyVista objects."""

from typing import List, Optional, Union
from pathlib import Path

import pyvista
from geoh5py.objects.object_base import ObjectBase
from geoh5py.workspace.workspace import Workspace

from geoh5vista.blockmodel import blockmodel_to_vtk
from geoh5vista.curve import curve_to_vtk
from geoh5vista.drillholes import drillholes_to_vtk
from geoh5vista.grid2d import grid2d_to_vtk
from geoh5vista.points import points_to_vtk
from geoh5vista.surface import surface_to_vtk
from geoh5vista.constants import SUPPORTED


__all__ = [
    "geoh5wrap",
    "read_workspace",
]

__displayname__ = "Wrapper"


def geoh5wrap(data: ObjectBase) -> Optional[pyvista.DataSet]:
    """Wrap a geoh5py data object as a PyVista data object.

    This is the primary function that an end user will harness. It takes
    any supported geoh5py object and returns the corresponding PyVista
    object with all data transferred.

    Parameters
    ----------
    data : geoh5py.objects.object_base.ObjectBase
        The geoh5py data object to wrap.

    Returns
    -------
    pyvista.DataSet
        The wrapped PyVista data object.

    Raises
    ------
    RuntimeError
        If the data object type is not supported.

    """
    if data is None:
        return None
    else:
        key = data.__class__.__name__  # get the class name
        try:
            return GEOH5WRAPPERS[key](data)
        except KeyError:
            raise RuntimeError(f"Data of type ({key}) is not  currently supported.")


def entities_to_vtk(entity_list: List[ObjectBase]) -> pyvista.MultiBlock:
    """Convert a list of geoh5py entities to a ``pyvista.MultiBlock`` object.

    Parameters
    ----------
    entity_list : list
        A list of geoh5py entities to convert.

    Returns
    -------
    pyvista.MultiBlock
        A MultiBlock object containing the converted entities.

    """
    # Iterate over the elements and add converted VTK objects a MultiBlock
    data = pyvista.MultiBlock()
    for item in entity_list:
        e = geoh5wrap(item)
        if e is not None and "gh5_name" in e.field_data:
            data.append(e, name=e.field_data["gh5_name"])
    else:
        pass
    return data


def read_workspace(
    workspace_path: Union[str, Path], load_visible: bool = True
) -> pyvista.MultiBlock:
    """Load a geoh5 workspace and convert its entities to a ``pyvista.MultiBlock``.

    Parameters
    ----------
    workspace_path : str or pathlib.Path
        The path to the geoh5 workspace file.
    load_visible : bool, optional
        If ``True``, only entities that are marked as visible in the
        workspace will be loaded. Default is ``False``.

    Returns
    -------
    pyvista.MultiBlock
        A MultiBlock object containing the converted entities.

    """
    wp = Workspace(workspace_path)
    entities = wp.fetch_children(wp.root, recursively=True)
    # entities = wp.objects # This approach doesn't include drillholes
    supported_entities = [e for e in entities if e.__class__.__name__ in SUPPORTED]
    if load_visible:
        supported_entities = [
            e
            for e in supported_entities
            if e.visible["Visible"].any()
        ]

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
    ## Container entities
    "Drillhole": drillholes_to_vtk,
    "DrillholeGroup": drillholes_to_vtk,
    "ConcatenatorDrillholeGroup": drillholes_to_vtk,
    "ConcatenatedDrillhole": drillholes_to_vtk,
}


# Now set up the display names for the docs
read_workspace.__displayname__ = "Load a GEOH5 Workspace File" # type: ignore
geoh5wrap.__displayname__ = "GEOH5 Entity Wrapper" # type: ignore
