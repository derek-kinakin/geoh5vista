"""Converter dispatch and assembly of PyVista visualization blocks."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Final, Literal

import pyvista
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.objects.drillhole import Drillhole
from geoh5py.objects.object_base import ObjectBase
from geoh5py.workspace.workspace import Workspace

from ..visibility import entity_visibility
from .blockmodel import vtk_to_blockmodel
from .curve import vtk_to_curve
from .drillholes import drillhole_to_vtk, drillholes_to_vtk
from .grid2d import vtk_to_grid2d
from .points import vtk_to_points
from .registry import CONVERTERS
from .surface import vtk_to_surface

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "GEOH5WRAPPERS",
    "MODULE_DISPLAY_NAME",
    "VTKWRAPPERS",
    "entities_to_vtk",
    "geoh5wrap",
    "vtkwrap",
)


MODULE_DISPLAY_NAME: Final[str] = "Dispatch"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "geoh5wrap": "Geoh5 Wrap",
    "vtkwrap": "VTK Wrap",
}


def geoh5wrap(
    data: ObjectBase | DrillholeGroup | None,
) -> pyvista.DataSet | pyvista.MultiBlock | None:
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


GEOH5WRAPPERS = {
    name: getattr(import_module(f".{module}", __package__), function)
    for name, (module, function) in CONVERTERS.items()
}


def vtkwrap(
        data: pyvista.DataSet | None,
        workspace_path: str | Path | Workspace,
        name: str | None = None
) -> ObjectBase | None:
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
        cell_type = data.get_cell(0).type
        if len(data.distinct_cell_types) > 1:
            # extract_cells_by_type rounds PolyData points to float32.
            is_polydata = isinstance(data, pyvista.PolyData)
            grid = data.cast_to_unstructured_grid()
            data = grid.extract_cells(
                grid.celltypes == cell_type, pass_cell_ids=False, pass_point_ids=False,
            )
            if is_polydata:
                data = data.extract_surface(
                    pass_pointid=False, pass_cellid=False, algorithm="dataset_surface",
                )
        key = f"{data.__class__.__name__}_{cell_type.name}"
    try:
        return VTKWRAPPERS[key](data, workspace_path, name=name)
    except KeyError:
        raise RuntimeError(f"Data of type ({key}) is not currently supported.")


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
