"""Full-workspace loading through geoh5py and the shared native hierarchy."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal

import h5py
import pyvista
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.objects.drillhole import Drillhole
from geoh5py.workspace.workspace import Workspace

from ..converters.dispatch import entities_to_vtk
from ..converters.registry import SUPPORTED
from ..models import HierarchyEntity
from ..visibility import entity_visibility
from ._hdf5 import project_group
from .hierarchy import read_hierarchy, snapshot_hierarchy

__all__ = ("FUNCTION_DISPLAY_NAMES", "MODULE_DISPLAY_NAME", "read_geoh5")

MODULE_DISPLAY_NAME: Final[str] = "Readers"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {"read_geoh5": "Read Geoh5"}


def _apply_hierarchy_parent_uids(
    block: pyvista.DataObject | None, hierarchy: Mapping[str, HierarchyEntity],
) -> None:
    if block is None:
        return
    if isinstance(block, pyvista.MultiBlock):
        for index in range(block.n_blocks):
            _apply_hierarchy_parent_uids(block[index], hierarchy)
    metadata = block.user_dict.get("geoh5", {})
    source = metadata.get("source", {})
    node = hierarchy.get(source.get("uid"))
    if node is not None:
        source["parent_uid"] = node.parent_uid


def read_geoh5(
    workspace_path: str | Path, load_only_visible: bool = False, mode: str = "r",
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
        The mode ("r+","r","w", etc.) in which to open the workspace. Default is ``"r"``.
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
    if not Path(workspace_path).exists():
        raise FileNotFoundError(f"Workspace file {workspace_path} not found.")
    with h5py.File(workspace_path, "r") as source:
        version, nodes = read_hierarchy(project_group(source))
        hierarchy = snapshot_hierarchy(version, nodes)

    with Workspace(workspace_path, mode=mode) as wp:
        entities = wp.fetch_children(wp.root, recursively=True)
        supported_entities = [
            entity for entity in entities
            if entity.__class__.__name__ in SUPPORTED
            and str(entity.uid) in hierarchy.by_uid
        ]
        supported_entities = [
            entity
            for entity in supported_entities
            if not (
                isinstance(entity, Drillhole)
                and isinstance(entity.parent, DrillholeGroup)
            )
        ]
        if load_only_visible:
            supported_entities = [
                entity
                for entity in supported_entities
                if entity_visibility(entity)
            ]
        result = entities_to_vtk(
            supported_entities, drillhole_representation=drillhole_representation,
            curve_tolerance=curve_tolerance, load_only_visible=load_only_visible,
        )
        _apply_hierarchy_parent_uids(result, hierarchy.by_uid)
        return result
