"""This module provides a high-level wrapper for converting geoh5py objects to PyVista objects."""

from typing import List, Optional, Union
from pathlib import Path

import pyvista
from geoh5py.objects.object_base import ObjectBase
from geoh5py.workspace.workspace import Workspace

from geoh5vista.blockmodel import blockmodel_to_vtk, vtk_to_blockmodel
from geoh5vista.curve import curve_to_vtk, vtk_to_curve
from geoh5vista.drillholes import drillholes_to_vtk
from geoh5vista.grid2d import grid2d_to_vtk, vtk_to_grid2d
from geoh5vista.points import points_to_vtk, vtk_to_points
from geoh5vista.surface import surface_to_vtk, vtk_to_surface
from geoh5vista.slicer import slicer_to_vtk_plane
from geoh5vista.constants import SUPPORTED


__all__ = [
    "geoh5wrap",
    "read_geoh5",
    "vtkwrap",
    "write_geoh5",
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


def read_geoh5(
    workspace_path: Union[str, Path], load_only_visible: bool = False
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
    # Check for workspace existence
    if not Path(workspace_path).exists():
        raise FileNotFoundError(f"Workspace file {workspace_path} not found.")
    else:
        #wp = Workspace(workspace_path)
        with Workspace(workspace_path) as wp:
            entities = wp.fetch_children(wp.root, recursively=True)
            # entities = wp.objects # This approach doesn't include drillholes
            # TODO: check if there is an issue with drillholes that don't have downhole surveys.
            # It may be that the workspace reader fails if the drillholes where created from a collar
            # only and don't have a downhole survey. This is because the reader expects a downhole survey to be present for drillholes, and if it's not, it may raise an error or fail to read the drillhole data correctly. To address this issue, you could implement a check in the workspace reader to handle drillholes without downhole surveys gracefully, perhaps by assigning default values or skipping those drillholes while still allowing the rest of the workspace to be read successfully.

            supported_entities = [e for e in entities if e.__class__.__name__ in SUPPORTED]

            if load_only_visible:
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
    ## Slicer entities
    "Slicer": slicer_to_vtk_plane,
}


def vtkwrap(data: Optional[pyvista.DataSet], workspace_path: Union[str, Path], name: Optional[str] = None) -> None:
    if data is None:
        return None
    elif isinstance(data, pyvista.PointSet):
        key = "PointSet"
    else:
        cell_type = data.get_cell(0).type # Check that the cell types are consistent
        data = data.extract_cells_by_type(cell_type) 
        if data is None:
            print("The cell types of the object are not consistent. Skipping object.")
            pass
        key = f"{data.__class__.__name__}_{cell_type.name}"
    try:
        return VTKWRAPPERS[key](data, workspace_path, name=name)
    except KeyError:
        raise RuntimeError(f"Data of type ({key}) is not currently supported.")


def vtk_to_entities(
    data: Union[List[pyvista.DataSet], pyvista.MultiBlock, pyvista.DataSet]
) -> List[pyvista.DataSet]:
    """Ensure that data is a list of pyvista DataSet objects."""

    if isinstance(data, pyvista.MultiBlock):
        if data.is_nested:
            data = data.flatten()
        return [data[k] for k in data.keys()]

    elif isinstance(data, pyvista.DataSet):
        return [data]

    elif isinstance(data, list):
        return data
    else:
        raise TypeError("Unsupported data type.")


def _get_entity_name(
    item: pyvista.DataSet, data_list: List[pyvista.DataSet], entity_name: Optional[str]
) -> str:
    """Determine the name for a geoh5 entity."""
    if entity_name:
        return entity_name

    if "gh5_name" in item.field_data:
        return item.field_data["gh5_name"]
    
    name = f"{item.__class__.__name__}_{data_list.index(item)}"
    print(f"Object name not found. Using default name: {name}")
    return name


def write_geoh5(
    data: Union[List[pyvista.DataSet], pyvista.MultiBlock, pyvista.DataSet],
    workspace_path: Union[str, Path],
    entity_name: Optional[str] = None,
) -> None:
    """Write PyVista objects to a geoh5 workspace."""
    data_list = vtk_to_entities(data)

    workspace_exists = Path(workspace_path).exists()
    print(
        f"Workspace {workspace_path} {'exists. Adding data.' if workspace_exists else 'Creating new workspace.'}"
    )

    # Use a single context manager to handle both cases
    with Workspace(workspace_path) if workspace_exists else Workspace.create(
        workspace_path
    ) as wp:
        for item in data_list:
            name = _get_entity_name(item, data_list, entity_name)
            vtkwrap(data=item, workspace_path=wp, name=name)


VTKWRAPPERS = {
    ## key is combination of VTK class and cell type
    ## Basic entities
    "PointSet": vtk_to_points,
    "PolyData_1": vtk_to_points,
    "PolyData_VERTEX": vtk_to_points,
    "PolyData_2": vtk_to_points,
    "PolyData_POLY_VERTEX": vtk_to_points,
    "PolyData_3": vtk_to_curve,
    "PolyData_LINE": vtk_to_curve,
    "UnstructuredGrid_3": vtk_to_curve,
    "UnstructuredGrid_LINE": vtk_to_curve,
    "PolyData_4": vtk_to_curve,
    "PolyData_POLY_LINE": vtk_to_curve,
    "UnstructuredGrid_4": vtk_to_curve,
    "UnstructuredGrid_POLY_LINE": vtk_to_curve,
    "PolyData_5": vtk_to_surface,
    "PolyData_TRIANGLE": vtk_to_surface,
    "UnstructuredGrid_5": vtk_to_surface,
    "UnstructuredGrid_TRIANGLE": vtk_to_surface,
    ## Grid entities
    "ImageData_8": vtk_to_grid2d,
    "ImageData_PIXEL": vtk_to_grid2d,
    ## Volume entities
    #"StructuredGrid_12": vtk_to_blockmodel,
    #"StructuredGrid_HEXAHEDRON": vtk_to_blockmodel,
    "ImageData_12": vtk_to_blockmodel,
    "ImageData_VOXEL": vtk_to_blockmodel,
}


# Now set up the display names for the docs
read_geoh5.__displayname__ = "Load a GEOH5 Workspace File" # type: ignore
geoh5wrap.__displayname__ = "GEOH5 Entity Wrapper" # type: ignore
write_geoh5.__displayname__ = "Write a GEOH5 Workspace File" # type: ignore
vtkwrap.__displayname__ = "VTK Object Wrapper" # type: ignore
