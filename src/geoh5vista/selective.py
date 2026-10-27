"""Experimental H5Reader-based conversion without opening the source workspace."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

import h5py
import pyvista
from geoh5py.data import Data
from geoh5py.groups import Group
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.io import H5Reader
from geoh5py.objects import ObjectBase
from geoh5py.shared.entity import Entity
from geoh5py.shared.utils import INV_KEY_MAP
from geoh5py.workspace import Workspace
from geoh5py.workspace.workspace import TYPE_UID_TO_CLASS

from .constants import CONVERTERS
from .visibility import project_group, stored_visibility
from .wrapper import entities_to_vtk

__all__ = ("read_geoh5_entities",)


@dataclass
class _Entry:
    uid: UUID
    family: str
    parent: UUID | None
    group: h5py.Group | None
    concatenated: bool = False


def _uuid(value: object) -> UUID:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return UUID(str(value).strip("{}"))


def _index(project: h5py.Group) -> tuple[UUID, dict[UUID, _Entry]]:
    root = project["Root"]
    root_uid = _uuid(root.attrs["ID"])
    entries = {root_uid: _Entry(root_uid, "root", None, root)}
    pending = [root_uid]
    while pending:
        parent_uid = pending.pop()
        parent = entries[parent_uid]
        for uid, family in H5Reader.fetch_children(
            project.file, parent_uid, "group" if parent.family == "root" else parent.family
        ).items():
            if family not in ("group", "object"):
                continue
            if uid in entries:
                raise ValueError(f"Repeated entity UID or cyclic hierarchy: {uid}.")
            group = project["Groups" if family == "group" else "Objects"][
                "{" + str(uid) + "}"
            ]
            if _uuid(group.attrs["ID"]) != uid:
                raise ValueError(f"{group.name}: link and entity UID differ.")
            entries[uid] = _Entry(uid, family, parent_uid, group)
            pending.append(uid)
        if parent.group is not None and "Concatenated object IDs" in parent.group:
            for value in parent.group["Concatenated object IDs"][()]:
                uid = _uuid(value)
                if uid in entries:
                    raise ValueError(f"Repeated concatenated entity UID: {uid}.")
                entries[uid] = _Entry(uid, "object", parent_uid, None, True)
    return root_uid, entries


def _class_name(entry: _Entry) -> str:
    if entry.concatenated:
        return "ConcatenatedDrillhole"
    if entry.group is None:
        raise ValueError(f"Missing native entity group for {entry.uid}.")
    member = TYPE_UID_TO_CLASS.get(_uuid(entry.group["Type"].attrs["ID"]))
    return member.__name__ if member is not None else "Unknown"


def _attributes(group: h5py.Group) -> dict:
    attributes = {
        INV_KEY_MAP.get(key, key): value for key, value in group.attrs.items()
    }
    attributes["visible"] = stored_visibility(group.attrs, context=group.name)
    return attributes


def read_geoh5_entities(
    workspace_path: str | Path,
    uids: UUID | str | Iterable[UUID | str],
    *,
    drillhole_representation: Literal["composite", "merged"] = "composite",
    curve_tolerance: float = 0.01,
) -> pyvista.MultiBlock:
    """Read selected entities without opening the source as a Workspace.

    Experimental: ordinary supported objects and legacy drillholes only.
    Concatenated selections raise NotImplementedError before reading geometry.
    Organizational groups select all supported descendant objects; drillhole
    groups retain their existing conversion nesting. Unsupported descendants
    are skipped, but an explicitly selected unsupported object raises an error.
    Overlaps are deduplicated and results use deterministic hierarchy order.
    All channels of selected objects are reconstructed using H5Reader.

    The source is opened read-only. Entities are reconstructed in an owned
    in-memory workspace using public APIs; only detached PyVista blocks escape.
    Ancestors retain source identities and display attributes, not their payloads.
    This prototype scans hierarchy metadata, not just the selected branch.
    """
    if drillhole_representation not in ("composite", "merged"):
        raise ValueError("drillhole_representation must be 'composite' or 'merged'.")
    if not 0 < curve_tolerance < float("inf"):
        raise ValueError("curve_tolerance must be finite and positive.")
    requested = list(dict.fromkeys(
        _uuid(value) for value in ([uids] if isinstance(uids, (UUID, str)) else uids)
    ))
    if not requested:
        raise ValueError("At least one entity UID is required.")

    with h5py.File(Path(workspace_path), "r") as source:
        project = project_group(source)
        version = float(project.attrs["Version"])
        if not 0 < version < float("inf"):
            raise ValueError("Invalid geoh5 format version.")
        root_uid, entries = _index(project)
        children: dict[UUID, list[UUID]] = {uid: [] for uid in entries}
        for entry in entries.values():
            if entry.parent is not None:
                children[entry.parent].append(entry.uid)
        selected: set[UUID] = set()
        for uid in requested:
            if uid not in entries:
                raise ValueError(f"Entity {uid} is not reachable from the workspace root.")
            entry = entries[uid]
            if entry.family == "object" and _class_name(entry) not in CONVERTERS:
                raise ValueError(f"No converter is registered for entity {uid}.")
            pending = [uid]
            while pending:
                current = pending.pop()
                if current in selected:
                    continue
                selected.add(current)
                pending.extend(children[current])
        for uid in selected:
            entry = entries[uid]
            if entry.concatenated or (
                version > 1
                and _class_name(entry) in ("DrillholeGroup", "IntegratorDrillholeGroup")
            ):
                raise NotImplementedError(
                    "Selective concatenated storage is not supported by this prototype "
                    f"(entity {uid}). No source geometry has been read."
                )

        with Workspace(version=version) as workspace:
            workspace.root.uid = root_uid
            workspace.root.name = project["Root"].attrs["Name"]
            workspace.root.visible = stored_visibility(
                project["Root"].attrs, context=project["Root"].name
            )
            reconstructed = {root_uid: workspace.root}

            def reconstruct(uid: UUID) -> Entity:
                if uid in reconstructed:
                    return reconstructed[uid]
                entry = entries[uid]
                if entry.parent is None or entry.group is None:
                    raise ValueError(f"Missing native hierarchy for entity {uid}.")
                parent = reconstruct(entry.parent)
                is_payload = uid in selected and entry.family == "object"
                if is_payload:
                    attributes, type_attributes, property_groups = H5Reader.fetch_attributes(
                        source, uid, entry.family
                    )
                    if attributes is None or type_attributes is None or property_groups is None:
                        raise ValueError(f"Cannot fetch attributes for entity {uid}.")
                    attributes["visible"] = stored_visibility(
                        entry.group.attrs, context=entry.group.name
                    )
                else:
                    attributes = _attributes(entry.group)
                    type_attributes = H5Reader.fetch_type_attributes(entry.group["Type"])
                    property_groups = {}
                attributes["parent"] = parent
                entity = workspace.create_entity(
                    ObjectBase if entry.family == "object" else Group,
                    entity=attributes,
                    entity_type=type_attributes,
                    save_on_creation=False,
                )
                if entity is None:
                    raise ValueError(f"Cannot reconstruct entity {uid}.")
                reconstructed[uid] = entity
                if is_payload:
                    for child_uid, family in H5Reader.fetch_children(
                        source, uid, entry.family
                    ).items():
                        if family != "data":
                            continue
                        attrs, data_type, _ = H5Reader.fetch_attributes(
                            source, child_uid, "data"
                        )
                        if attrs is None or data_type is None:
                            raise ValueError(f"Cannot fetch data attributes for {child_uid}.")
                        attrs["parent"] = entity
                        attrs["values"] = H5Reader.fetch_values(source, child_uid)
                        workspace.create_entity(
                            Data, entity=attrs, entity_type=data_type,
                            save_on_creation=False,
                        )
                    for attributes in property_groups.values():
                        entity.create_property_group(**attributes)
                return entity

            ordered = []
            pending = [root_uid]
            while pending:
                uid = pending.pop()
                entry = entries[uid]
                if uid in selected and _class_name(entry) in CONVERTERS:
                    ordered.append(reconstruct(uid))
                pending.extend(sorted(children[uid], key=str, reverse=True))
            selected_groups = {
                entity.uid for entity in ordered if isinstance(entity, DrillholeGroup)
            }
            ordered = [
                entity for entity in ordered
                if not (
                    isinstance(entity, ObjectBase) and entity.parent.uid in selected_groups
                )
            ]
            return entities_to_vtk(
                ordered, drillhole_representation=drillhole_representation,
                curve_tolerance=curve_tolerance,
            )
