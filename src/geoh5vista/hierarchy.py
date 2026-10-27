"""Shared metadata-only hierarchy discovery for cataloging and selective reads."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from uuid import UUID

import h5py
import numpy as np
from geoh5py.workspace.workspace import TYPE_UID_TO_CLASS

from .constants import CONVERTERS


def text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError(f"Expected text metadata, got {type(value).__name__}.")


def uid(value: object) -> str:
    return str(UUID(text(value)))


def group(parent: h5py.Group, key: str) -> h5py.Group:
    value = parent[key]
    if not isinstance(value, h5py.Group):
        raise ValueError(f"{value.name}: expected an HDF5 group.")  # noqa: TRY004
    return value


def dataset(parent: h5py.Group, key: str) -> h5py.Dataset:
    value = parent[key]
    if not isinstance(value, h5py.Dataset):
        raise ValueError(f"{value.name}: expected an HDF5 dataset.")  # noqa: TRY004
    return value


@dataclass
class HierarchyNode:
    uid: str
    attributes: dict
    type_attributes: dict
    is_object: bool
    group: h5py.Group | None = None
    concatenator: h5py.Group | None = None
    parent_uid: str | None = None
    entity_type: str = ""
    conversion_supported: bool = False

    def type_name(self, version: float, parent_type: str) -> tuple[str, bool]:
        type_uid = UUID(uid(self.type_attributes["ID"]))
        member = TYPE_UID_TO_CLASS.get(type_uid)
        if member is None:
            return text(self.type_attributes.get("Name", str(type_uid))), False
        name = member.__name__
        if version > 1.0:
            if name in ("DrillholeGroup", "IntegratorDrillholeGroup"):
                name = f"Concatenator{name}"
            elif name == "Drillhole" and parent_type in (
                "ConcatenatorDrillholeGroup",
                "ConcatenatorIntegratorDrillholeGroup",
            ):
                name = "ConcatenatedDrillhole"
        return name, name in CONVERTERS


def _native_node(handle: h5py.Group, is_object: bool) -> HierarchyNode:
    try:
        attributes = {key: handle.attrs[key] for key in ("ID", "Name")}
        if "Visible" in handle.attrs:
            attributes["Visible"] = handle.attrs["Visible"]
        entity_type = group(handle, "Type")
        type_attributes = {key: entity_type.attrs[key] for key in ("ID", "Name")}
        return HierarchyNode(
            uid(attributes["ID"]), attributes, type_attributes, is_object, handle
        )
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError(f"{handle.name}: {error}") from error


def concatenated_records(handle: h5py.Group, version: float) -> list[dict]:
    """Read attribute records through their reachable concatenator handle."""
    storage = group(handle, "Concatenated Data")
    label = "Attributes Jsons" if version > 2.0 else "Attributes"
    raw = dataset(storage, label)[()]
    if version > 2.0:
        records = [json.loads(text(value)) for value in raw]
    else:
        if isinstance(raw, np.ndarray):
            if raw.size != 1:
                raise ValueError("Expected one concatenated Attributes JSON document.")
            raw = raw.item()
        records = json.loads(text(raw))["Attributes"]
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("Concatenated attributes must be a list of metadata dictionaries.")
    return records


def concatenated_object_type(project: h5py.Group, type_uid: str) -> dict:
    """Resolve stored type attributes, or an explicitly identified native type."""
    location = f"Types/Object types/{{{type_uid}}}"
    if location in project:
        handle = group(project, location)
        if uid(handle.attrs["ID"]) != type_uid:
            raise ValueError(f"{handle.name}: conflicting object type ID.")
        return dict(handle.attrs)
    member = TYPE_UID_TO_CLASS.get(UUID(type_uid))
    name = member.__name__ if member is not None else type_uid
    warnings.warn(
        f"{project.name}/{location}: missing object type record; "
        + (
            f"using registered native type {name!r}. Stored type metadata is unavailable."
            if member is not None else
            "retaining the unknown type ID as unsupported."
        ),
        UserWarning, stacklevel=2,
    )
    return {"ID": "{" + type_uid + "}", "Name": name}


def _concatenated_nodes(
    project: h5py.Group, handle: h5py.Group, version: float,
) -> list[HierarchyNode]:
    if "Concatenated object IDs" not in handle:
        return []
    object_ids = dataset(handle, "Concatenated object IDs")[()]
    if not len(object_ids):
        return []
    records = concatenated_records(handle, version)
    by_uid = {uid(record["ID"]): record for record in records}
    if len(by_uid) != len(records):
        raise ValueError("Duplicate concatenated metadata UIDs.")
    nodes = []
    types = {}
    for value in object_ids:
        object_uid = uid(value)
        attributes = by_uid[object_uid]
        type_uid = uid(attributes["Object Type ID"])
        if type_uid not in types:
            types[type_uid] = concatenated_object_type(project, type_uid)
        type_attributes = types[type_uid]
        nodes.append(HierarchyNode(
            object_uid, attributes, type_attributes, True, concatenator=handle,
        ))
    return nodes


def _children(
    project: h5py.Group, handle: h5py.Group, version: float, root_uid: str,
) -> list[HierarchyNode]:
    children = []
    for family in ("Groups", "Objects"):
        if family not in handle:
            continue
        collection = group(handle, family)
        for key in collection:
            child = _native_node(group(collection, key), family == "Objects")
            if uid(key) != child.uid:
                raise ValueError(f"{collection.name}/{key}: link and entity UID differ.")
            if child.uid == root_uid:
                raise ValueError(f"Entity {child.uid}: cyclic hierarchy links back to root.")
            indexed = (
                group(group(project, family), "{" + child.uid + "}")
                if family in project and "{" + child.uid + "}" in group(project, family)
                else None
            )
            if indexed is not None and indexed.id != child.group.id:
                raise ValueError(
                    f"Entity {child.uid}: conflicting native definitions at "
                    f"{child.group.name} and {indexed.name}."
                )
            if indexed is not None:
                child.group = indexed
            children.append(child)
    children.extend(_concatenated_nodes(project, handle, version))
    return children


def read_hierarchy(project: h5py.Group) -> tuple[float, list[HierarchyNode]]:
    """Resolve root aliases and return a UID-sorted depth-first native tree.

    Root attributes come from /Root. A distinct indexed root must match its
    ID and type ID; its child links are unioned, not its attributes. Only root
    aliases may have distinct physical definitions. Non-root definitions must
    match the flat index when present. Hierarchy-only entities are supported.
    Multiple parents and cycles are rejected.
    No geometry, channel values, or display XML is read.
    """
    try:
        version = float(project.attrs["Version"])
        if not np.isfinite(version) or version <= 0:
            raise ValueError("Invalid geoh5 format version.")
        root = _native_node(group(project, "Root"), False)
        roots = [root.group]
        key = "{" + root.uid + "}"
        if "Groups" in project and key in group(project, "Groups"):
            indexed = _native_node(group(group(project, "Groups"), key), False)
            if indexed.uid != root.uid:
                raise ValueError("Conflicting root identities: /Root and indexed root IDs differ.")
            if uid(indexed.type_attributes["ID"]) != uid(root.type_attributes["ID"]):
                raise ValueError("Conflicting root type identities.")
            if indexed.group.id != root.group.id:
                roots.append(indexed.group)
        root.entity_type, root.conversion_supported = root.type_name(version, "")
        result = []
        seen = {root.uid}
        pending = [(root, roots)]
        while pending:
            parent, handles = pending.pop()
            result.append(parent)
            children: dict[str, HierarchyNode] = {}
            for handle in handles:
                for child in _children(project, handle, version, root.uid):
                    if child.uid in children:
                        previous = children[child.uid]
                        if (
                            child.is_object != previous.is_object
                            or child.group is None or previous.group is None
                            or child.group.id != previous.group.id
                        ):
                            raise ValueError(f"Entity {child.uid}: conflicting native definitions.")
                        continue
                    children[child.uid] = child
            ordered = sorted(children.values(), key=lambda node: node.uid)
            for child in ordered:
                if child.uid in seen:
                    raise ValueError(
                        f"Entity {child.uid}: repeated UID, conflicting parents or cyclic hierarchy."
                    )
                seen.add(child.uid)
                child.parent_uid = parent.uid
                child.entity_type, child.conversion_supported = child.type_name(
                    version, parent.entity_type,
                )
            for child in reversed(ordered):
                pending.append((child, [child.group] if child.group is not None else []))
        return version, result
    except (KeyError, ValueError, TypeError, OverflowError) as error:
        raise ValueError(f"Cannot discover hierarchy in {project.name}: {error}") from error
