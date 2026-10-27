"""This module provides a high-level wrapper for converting geoh5py objects to PyVista objects."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Final, Literal

import pyvista
from geoh5py.objects.object_base import ObjectBase
from geoh5py.objects.drillhole import Drillhole
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.workspace.workspace import Workspace

from geoh5vista.blockmodel import vtk_to_blockmodel
from geoh5vista.constants import CONVERTERS, SUPPORTED
from geoh5vista.curve import vtk_to_curve
from geoh5vista.drillholes import drillhole_to_vtk, drillholes_to_vtk
from geoh5vista.grid2d import vtk_to_grid2d
from geoh5vista.points import vtk_to_points
from geoh5vista.surface import vtk_to_surface
from geoh5vista.visibility import entity_visibility

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "geoh5wrap",
    "read_geoh5",
    "vtkwrap",
    "write_geoh5",
)


MODULE_DISPLAY_NAME: Final[str] = "Wrapper"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "geoh5wrap": "Geoh5 Wrap",
    "read_geoh5": "Read Geoh5",
    "vtkwrap": "VTK Wrap",
    "write_geoh5": "Write Geoh5",
}


def geoh5wrap(data: ObjectBase | DrillholeGroup) -> pyvista.DataSet | pyvista.MultiBlock | None:
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
        converter = GEOH5WRAPPERS.get(key)
        if converter is None:
            raise RuntimeError(f"Data of type ({key}) is not  currently supported.")
        return converter(data)


def entities_to_vtk(
    entity_list: list[ObjectBase | DrillholeGroup], *,
    drillhole_representation: Literal["composite", "merged"] = "composite",
    curve_tolerance: float = 0.01, load_only_visible: bool = False,
) -> pyvista.MultiBlock:
    """Convert a list of geoh5py entities to a ``pyvista.MultiBlock`` object.

    Visible-only filtering uses each entity's stored checkbox, with missing
    attributes defaulting to True, independently of view records and ancestors.

    Parameters
    ----------
    entity_list : list
        A list of geoh5py entities to convert.

    Returns
    -------
    pyvista.MultiBlock
        A MultiBlock object containing the converted entities.

    """
    data = pyvista.MultiBlock()
    for item in entity_list:
        if load_only_visible and not entity_visibility(item):
            continue
        if isinstance(item, DrillholeGroup):
            e = drillholes_to_vtk(
                item, representation=drillhole_representation,
                curve_tolerance=curve_tolerance, load_only_visible=load_only_visible,
            )
        elif isinstance(item, Drillhole):
            e = drillhole_to_vtk(
                item, curve_tolerance=curve_tolerance, representation=drillhole_representation,
            )
        else:
            e = geoh5wrap(item)
        if e is not None:
            name = e.user_dict["geoh5"]["display"]["name"]
            if name in data.keys():
                name = f"{name} [{item.uid}]"
            data.append(e, name=name)
    return data


def read_geoh5(
    workspace_path: str | Path, load_only_visible: bool = False, mode: str = "r+",
    *, drillhole_representation: Literal["composite", "merged"] = "composite",
    curve_tolerance: float = 0.01,
) -> pyvista.MultiBlock:
    """Load a geoh5 workspace and convert its entities to a ``pyvista.MultiBlock``.

    Parameters
    ----------
    workspace_path : str or pathlib.Path
        The path to the geoh5 workspace file.
    load_only_visible : bool, optional
        If ``True``, filter by each entity's stored Visible checkbox, not
        per-view or inherited visibility. Missing attributes default to visible.
        Existing drillhole group selection/nesting is preserved. Default is ``False``.
    mode : str, optional
        The mode ("r+","r","w", etc.) in which to open the workspace. Default is ``"r+"``.
    drillhole_representation : {"composite", "merged"}, optional
        Preserve individual holes and sampling tables by default. ``merged``
        requests a line visualization and rejects incompatible tables.
    curve_tolerance : float, optional
        Maximum drillhole circular-arc chord error in workspace distance units.

    Returns
    -------
    pyvista.MultiBlock
        A MultiBlock object containing the converted entities.

    """
    if drillhole_representation not in ("composite", "merged"):
        raise ValueError("drillhole_representation must be 'composite' or 'merged'.")
    # Check for workspace existence
    if not Path(workspace_path).exists():
        raise FileNotFoundError(f"Workspace file {workspace_path} not found.")
    else:
        #wp = Workspace(workspace_path)
        with Workspace(workspace_path, mode=mode) as wp:
            entities = wp.fetch_children(wp.root, recursively=True)
            supported_entities = [e for e in entities if e.__class__.__name__ in SUPPORTED]
            supported_entities = [
                e for e in supported_entities
                if not (isinstance(e, Drillhole) and isinstance(e.parent, DrillholeGroup))
            ]

            if load_only_visible:
                supported_entities = [
                    e
                    for e in supported_entities
                    if entity_visibility(e)
                ]

            return entities_to_vtk(
                supported_entities, drillhole_representation=drillhole_representation,
                curve_tolerance=curve_tolerance, load_only_visible=load_only_visible,
            )


GEOH5WRAPPERS = {
    name: getattr(import_module(f".{module}", __package__), function)
    for name, (module, function) in CONVERTERS.items()
}


def vtkwrap(
        data: pyvista.DataSet | None, 
        workspace_path: str | Path, 
        name: str | None = None
) -> None:
    if data is None:
        return None
    if isinstance(data, pyvista.MultiBlock) or (
        data.user_dict.get("geoh5", {}).get("drillhole", {}).get("role")
        in ("collar", "trace", "intervals", "points")
    ):
        raise ValueError("Drillhole composite export is not supported.")
    if isinstance(data, pyvista.PointSet):
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
    data: list[pyvista.DataSet] | pyvista.MultiBlock | pyvista.DataSet
) -> list[pyvista.DataSet]:
    """Ensure that data is a list of pyvista DataSet objects."""

    if isinstance(data, pyvista.MultiBlock):
        if data.is_nested:
            data = data.flatten(user_dict_mode="nested")
        return [data[k] for k in data.keys()]

    elif isinstance(data, pyvista.DataSet):
        return [data]

    elif isinstance(data, list):
        return data
    else:
        raise TypeError("Unsupported data type.")


def _get_entity_name(
    item: pyvista.DataSet,
    data_list: list[pyvista.DataSet],
    entity_name: str | None
) -> str:
    """Determine the name for a geoh5 entity."""
    if entity_name:
        return entity_name

    display = item.user_dict.get("geoh5", {}).get("display", {})
    if "name" in display:
        return display["name"]

    if "gh5_name" in item.user_dict:
        return item.user_dict["gh5_name"]
    
    name = f"{item.__class__.__name__}_{data_list.index(item)}"
    print(f"Object name not found. Using default name: {name}")
    return name


def write_geoh5(
    data: list[pyvista.DataSet] | pyvista.MultiBlock | pyvista.DataSet,
    workspace_path: str | Path,
    entity_name: str | None = None,
) -> None:
    """Write PyVista objects to a geoh5 workspace."""
    data_list = vtk_to_entities(data)
    if any(item.user_dict.get("geoh5", {}).get("drillhole", {}).get("role")
           in ("collar", "trace", "intervals", "points") for item in data_list):
        raise ValueError(
            "Drillhole composite export is not supported. Use an explicit merged "
            "representation to export line geometry as curves."
        )

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
    "ImageData_12": vtk_to_blockmodel,
    "ImageData_VOXEL": vtk_to_blockmodel,
    "StructuredGrid_12": vtk_to_blockmodel,
    "StructuredGrid_HEXAHEDRON": vtk_to_blockmodel,
}
