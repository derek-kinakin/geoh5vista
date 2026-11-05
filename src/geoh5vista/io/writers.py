"""Geoh5 file export orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pyvista
from geoh5py.workspace.workspace import Workspace

from ..converters.dispatch import vtkwrap

__all__ = ("FUNCTION_DISPLAY_NAMES", "MODULE_DISPLAY_NAME", "vtk_to_entities", "write_geoh5")

MODULE_DISPLAY_NAME: Final[str] = "Writers"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {"write_geoh5": "Write Geoh5"}


def vtk_to_entities(
    data: list[pyvista.DataSet] | pyvista.MultiBlock | pyvista.DataSet,
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
    item: pyvista.DataSet, data_list: list[pyvista.DataSet], entity_name: str | None,
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
    """Write PyVista objects without reducing input coordinate precision.

    Float32 coordinates retain their existing values; lost precision cannot be
    recovered by writing them as float64. For mixed-cell datasets, only cells
    matching the first cell's type are exported.
    """
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
    with Workspace(workspace_path) if workspace_exists else Workspace.create(
        workspace_path
    ) as wp:
        for item in data_list:
            name = _get_entity_name(item, data_list, entity_name)
            vtkwrap(data=item, workspace_path=wp, name=name)
