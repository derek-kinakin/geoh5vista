"""Experimental H5Reader-based conversion without opening the source workspace."""

from __future__ import annotations

import warnings
from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

import h5py
import numpy as np
import pyvista
from geoh5py.data import Data
from geoh5py.groups import Group
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.io import H5Reader
from geoh5py.io.h5_reader import safe_load_dataset
from geoh5py.objects import ObjectBase
from geoh5py.shared import FLOAT_NDV
from geoh5py.shared.concatenation.concatenator import Concatenator
from geoh5py.shared.entity import Entity
from geoh5py.shared.utils import INV_KEY_MAP, str_json_to_dict
from geoh5py.workspace import Workspace
from geoh5py.workspace.workspace import TYPE_UID_TO_CLASS

from .hierarchy import concatenated_object_type, concatenated_records, read_hierarchy
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
    conversion_supported: bool = False


def _uuid(value: object) -> UUID:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return UUID(str(value).strip("{}"))


def _index(project: h5py.Group) -> tuple[UUID, dict[UUID, _Entry]]:
    _, nodes = read_hierarchy(project)
    entries = {}
    for node in nodes:
        uid = UUID(node.uid)
        entries[uid] = _Entry(
            uid=uid,
            family="root" if node.parent_uid is None else "object" if node.is_object else "group",
            parent=UUID(node.parent_uid) if node.parent_uid is not None else None,
            group=node.group,
            concatenated=node.concatenator is not None,
            conversion_supported=node.conversion_supported,
        )
    return UUID(nodes[0].uid), entries


def _attributes(group: h5py.Group) -> dict:
    attributes = {
        INV_KEY_MAP.get(key, key): value for key, value in group.attrs.items()
    }
    attributes["visible"] = stored_visibility(group.attrs, context=group.name)
    return attributes


def _native_attributes(source: h5py.File, handle: h5py.Group, family: str):
    """Use H5Reader when indexed; otherwise decode the reachable handle."""
    project = project_group(source)
    collection = {"object": "Objects", "data": "Data"}[family]
    key = "{" + str(_uuid(handle.attrs["ID"])) + "}"
    if collection in project and key in project[collection]:
        if project[collection][key].id != handle.id:
            raise ValueError(f"{handle.name}: conflicting indexed definition.")
        return H5Reader.fetch_attributes(source, _uuid(handle.attrs["ID"]), family)
    attributes = {
        INV_KEY_MAP.get(key, key): value for key, value in handle.attrs.items()
    }
    if family != "data":
        for key, value in handle.items():
            if key.lower() in ("metadata", "options"):
                attributes[INV_KEY_MAP[key]] = str_json_to_dict(np.r_[value][0])
            elif key in INV_KEY_MAP and isinstance(value, h5py.Dataset) and value.ndim > 0:
                attributes[INV_KEY_MAP[key]] = safe_load_dataset(value, value.name)
    properties = {}
    if "PropertyGroups" in handle:
        for key, value in handle["PropertyGroups"].items():
            properties[key] = {
                INV_KEY_MAP.get(label, label): item for label, item in value.attrs.items()
            }
    return attributes, H5Reader.fetch_type_attributes(handle["Type"]), properties


def _native_values(source: h5py.File, handle: h5py.Group):
    project = project_group(source)
    key = "{" + str(_uuid(handle.attrs["ID"])) + "}"
    if "Data" in project and key in project["Data"]:
        return H5Reader.fetch_values(source, _uuid(handle.attrs["ID"]))
    if "Data" not in handle:
        return None
    values = safe_load_dataset(handle["Data"], handle.name)
    if len(values) and isinstance(values[0], (str, bytes)):
        values = np.asarray([
            value.decode("utf-8") if isinstance(value, bytes) else value for value in values
        ])
        return values[0] if len(values) == 1 else values
    if values.dtype.kind == "f":
        values[values == FLOAT_NDV] = np.nan
    return values


def _load_concatenator(
    source: h5py.File, group: Concatenator, uids: set[UUID],
    handle: h5py.Group,
) -> dict[UUID, ObjectBase]:
    """Populate public caches with compact slices, never file-wide payloads."""
    metadata = {"Attributes": concatenated_records(handle, group.workspace.version)}
    if not isinstance(metadata, dict) or not isinstance(metadata.get("Attributes"), list):
        raise ValueError(f"Concatenator {group.uid}: missing attribute records.")  # noqa: TRY004
    records = {}
    for record in metadata["Attributes"]:
        if not isinstance(record, dict) or "ID" not in record:
            raise ValueError(f"Concatenator {group.uid}: invalid attribute record.")
        uid = _uuid(record["ID"])
        if uid in records:
            raise ValueError(f"Concatenator {group.uid}: duplicate record {uid}.")
        records[uid] = record
    needed = set(uids)
    channels: dict[UUID, UUID] = {}
    for uid in uids:
        if uid not in records:
            raise ValueError(f"Concatenator {group.uid}: missing drillhole record {uid}.")
        record = records[uid]
        member = TYPE_UID_TO_CLASS.get(_uuid(record["Object Type ID"]))
        if member is None or member.__name__ != "Drillhole":
            raise NotImplementedError(f"Concatenated entity {uid} is not a drillhole.")
        stored_visibility(record, context=f"Entity {uid}")
        for key, value in record.items():
            if not key.startswith("Property:"):
                continue
            child_uid = _uuid(value)
            if child_uid in channels:
                raise ValueError(f"Concatenator {group.uid}: repeated data reference {child_uid}.")
            channels[child_uid] = uid
    needed.update(channels)
    storage = handle["Concatenated Data"]
    data, indices = {}, {}
    if "Index" in storage:
        for field in sorted(storage["Index"]):
            dataset = storage["Index"][field]
            if not isinstance(dataset, h5py.Dataset):
                raise ValueError(f"{dataset.name}: expected an index dataset.")  # noqa: TRY004
            fields = dataset.dtype.names or ()
            if dataset.ndim != 1 or not {
                "Object ID", "Data ID", "Start index", "Size",
            }.issubset(fields):
                raise ValueError(f"{dataset.name}: invalid concatenation index schema.")
            if any(dataset.dtype[name].kind not in "iu" for name in ("Start index", "Size")):
                raise ValueError(f"{dataset.name}: offsets must be integers.")
            rows = dataset[()]
            mask = np.array([_uuid(row["Object ID"]) in uids for row in rows], dtype=bool)
            selected = rows[mask].copy()
            if not len(selected):
                continue
            if "Data" in storage and field in storage["Data"]:
                values = storage["Data"][field]
            elif field in storage:
                values = storage[field]
            else:
                warnings.warn(
                    f"Concatenated field '{field}' of group {group.uid} is indexed "
                    "but has no stored data; ignoring it.",
                    UserWarning, stacklevel=2,
                )
                continue
            if not isinstance(values, h5py.Dataset) or values.ndim != 1:
                raise ValueError(f"{dataset.name}: expected a one-dimensional payload.")
            pieces = []
            offset = 0
            seen = set()
            unrelated = sorted(
                (int(row["Start index"]), int(row["Start index"]) + int(row["Size"]))
                for row in rows[~mask] if int(row["Size"]) > 0
            )
            starts, ends = [], []
            maximum_end = 0
            for start, end in unrelated:
                starts.append(start)
                maximum_end = max(maximum_end, end)
                ends.append(maximum_end)
            for row in selected:
                start, size = int(row["Start index"]), int(row["Size"])
                data_uid = _uuid(row["Data ID"])
                identity = data_uid if data_uid.int else _uuid(row["Object ID"])
                if identity in seen:
                    raise ValueError(f"{dataset.name}: duplicate index for {identity}.")
                seen.add(identity)
                if data_uid.int and channels.get(data_uid) != _uuid(row["Object ID"]):
                    raise ValueError(f"{dataset.name}: invalid data owner for {data_uid}.")
                if start < 0 or size < 0 or start + size > len(values):
                    raise ValueError(f"{dataset.name}: invalid payload slice.")
                position = bisect_left(starts, start + size) - 1
                if size and position >= 0 and ends[position] > start:
                    raise ValueError(f"{dataset.name}: slice overlaps an unrelated object.")
                pieces.append(values[start : start + size])
                row["Start index"] = offset
                offset += size
            compact = np.concatenate(pieces)
            if compact.dtype.kind == "f":
                compact[compact == FLOAT_NDV] = np.nan
            if compact.dtype == object and len(compact) and isinstance(compact[0], bytes):
                compact = np.array([value.decode("utf-8") for value in compact])
            name = field.replace("\u2044", "/")
            data[name], indices[name] = compact, selected
    for value in data.get("Property Group IDs", []):
        uid = _uuid(value)
        needed.add(uid)
        if uid not in records:
            raise ValueError(f"Concatenator {group.uid}: missing property group record {uid}.")
        if any(_uuid(prop) not in channels for prop in records[uid].get("Properties", [])):
            raise ValueError(f"Property group {uid}: references unselected data.")
    missing = needed - records.keys()
    if missing:
        raise ValueError(f"Concatenator {group.uid}: missing records {sorted(map(str, missing))}.")
    group.data = data
    group.index = indices
    group.concatenated_attributes = {
        "Attributes": [records[uid].copy() for uid in sorted(needed, key=str)]
    }
    group.concatenated_object_ids = [
        ("{" + str(uid) + "}").encode() for uid in sorted(uids, key=str)
    ]
    result = {}
    for uid in sorted(uids, key=str):
        attributes = records[uid].copy()
        type_uid = _uuid(attributes.pop("Object Type ID"))
        attributes["Name"] = attributes["Name"].replace("\u2044", "/")
        attributes["parent"] = group
        project = project_group(source)
        location = f"Types/Object types/{{{type_uid}}}"
        type_attributes = (
            H5Reader.fetch_type(source, type_uid, "Object")
            if location in project else {
                INV_KEY_MAP.get(key, key): value
                for key, value in concatenated_object_type(project, str(type_uid)).items()
            }
        )
        hole = group.workspace.create_entity(
            ObjectBase, entity=attributes,
            entity_type=type_attributes,
            save_on_creation=False,
        )
        if not isinstance(hole, ObjectBase):
            raise ValueError(f"Cannot reconstruct concatenated drillhole {uid}.")  # noqa: TRY004
        hole.on_file = True
        for key, value in records[uid].items():
            if not key.startswith("Property:"):
                continue
            attrs = records[_uuid(value)].copy()
            type_uid = _uuid(attrs.pop("Type ID"))
            attrs["Name"] = attrs["Name"].replace("\u2044", "/")
            attrs["parent"] = hole
            child = group.workspace.create_entity(
                Data, entity=attrs,
                entity_type=H5Reader.fetch_type(source, type_uid, "Data"),
                save_on_creation=False,
            )
            child.on_file = True
        result[uid] = hole
    return result


def read_geoh5_entities(
    workspace_path: str | Path,
    uids: UUID | str | Iterable[UUID | str],
    *,
    drillhole_representation: Literal["composite", "merged"] = "composite",
    curve_tolerance: float = 0.01,
) -> pyvista.MultiBlock:
    """Read selected entities without opening the source as a Workspace.

    Experimental: ordinary supported objects and legacy/concatenated drillholes.
    Shared concatenated payloads are read only at selected holes' index slices.
    Organizational groups select all supported descendant objects; drillhole
    groups retain their existing conversion nesting. Unsupported descendants
    are skipped, but an explicitly selected unsupported object raises an error.
    Overlaps are deduplicated and results use deterministic hierarchy order.
    H5Reader supplies native attributes and types; concatenated indices and
    selected payload slices are read with h5py. All selected channels are retained.

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
            if entry.family == "object" and not entry.conversion_supported:
                raise ValueError(f"No converter is registered for entity {uid}.")
            pending = [uid]
            while pending:
                current = pending.pop()
                if current in selected:
                    continue
                selected.add(current)
                pending.extend(children[current])
        with Workspace(
            version=version, distance_unit=project.attrs.get("Distance unit", "meter"),
        ) as workspace:
            workspace.root.uid = root_uid
            root = entries[root_uid].group
            workspace.root.name = root.attrs["Name"]
            workspace.root.visible = stored_visibility(
                root.attrs, context=root.name
            )
            reconstructed = {root_uid: workspace.root}

            def reconstruct(uid: UUID) -> Entity:
                if uid in reconstructed:
                    return reconstructed[uid]
                entry = entries[uid]
                if entry.concatenated:
                    parent = reconstruct(entry.parent)
                    if not isinstance(parent, Concatenator) or not isinstance(parent, DrillholeGroup):
                        raise NotImplementedError("Only concatenated drillhole groups are supported.")
                    reconstructed.update(_load_concatenator(
                        source, parent, {
                            child for child in children[entry.parent]
                            if child in selected and entries[child].concatenated
                        },
                        entries[entry.parent].group,
                    ))
                    return reconstructed[uid]
                if entry.parent is None or entry.group is None:
                    raise ValueError(f"Missing native hierarchy for entity {uid}.")
                parent = reconstruct(entry.parent)
                is_payload = uid in selected and entry.family == "object"
                if is_payload:
                    attributes, type_attributes, property_groups = _native_attributes(
                        source, entry.group, entry.family
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
                    channels = entry.group.get("Data")
                    for child_key in channels if channels is not None else ():
                        child = channels[child_key]
                        child_uid = _uuid(child.attrs["ID"])
                        if _uuid(child_key) != child_uid:
                            raise ValueError(f"{child.name}: link and entity UID differ.")
                        attrs, data_type, _ = _native_attributes(
                            source, child, "data"
                        )
                        if attrs is None or data_type is None:
                            raise ValueError(f"Cannot fetch data attributes for {child_uid}.")
                        attrs["parent"] = entity
                        attrs["values"] = _native_values(source, child)
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
                if uid in selected and entry.conversion_supported:
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
