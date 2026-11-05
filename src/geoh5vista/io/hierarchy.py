"""Shared metadata-only hierarchy discovery for cataloging and selective reads.

geoh5py supplies type records (``H5Reader.fetch_type_attributes``/``fetch_type``),
indexed concatenated attributes (``H5Reader.fetch_concatenated_attributes``), and
class identity (``TYPE_UID_TO_CLASS`` plus its Concatenator naming rules). Child
links are walked here because ``H5Reader.fetch_children``/``fetch_uuids`` only
resolve flat-index entries, and opening a ``Workspace`` eagerly loads geometry.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from uuid import UUID

import h5py
import numpy as np
from geoh5py.groups import DrillholeGroup, IntegratorDrillholeGroup, RootGroup
from geoh5py.io import H5Reader
from geoh5py.objects import Drillhole
from geoh5py.shared.concatenation import ConcatenatedDrillhole
from geoh5py.workspace.workspace import TYPE_UID_TO_CLASS

from ..converters.registry import CONVERTERS
from ..models import HierarchyEntity, WorkspaceHierarchy
from ._hdf5 import dataset, group, project_group, text, uid

_CONCATENATOR_MEMBERS = (DrillholeGroup, IntegratorDrillholeGroup)
_CONCATENATOR_NAMES = frozenset(f"Concatenator{m.__name__}" for m in _CONCATENATOR_MEMBERS)

__all__ = (
    "HierarchyNode",
    "concatenated_object_type",
    "concatenated_records",
    "read_hierarchy",
    "snapshot_hierarchy",
)


@dataclass
class HierarchyNode:
    """Internal discovery record; HDF5 handles are valid only while the source is open."""

    uid: str
    attributes: dict
    type_attributes: dict
    is_object: bool
    is_root: bool = False
    group: h5py.Group | None = None
    concatenator: h5py.Group | None = None
    parent_uid: str | None = None
    entity_type: str = ""
    conversion_supported: bool = False

    def type_name(self, version: float, parent_type: str) -> tuple[str, bool]:
        """Mirror ``Workspace.create_object_or_group`` class selection by type UID."""
        type_uid = UUID(uid(self.type_attributes["uid"]))
        member = TYPE_UID_TO_CLASS.get(type_uid)
        if member is None:
            return text(self.type_attributes.get("name", str(type_uid))), False
        name = member.__name__
        if version > 1.0:
            if member in _CONCATENATOR_MEMBERS:
                name = f"Concatenator{name}"
            elif member is Drillhole and parent_type in _CONCATENATOR_NAMES:
                name = ConcatenatedDrillhole.__name__
        return name, name in CONVERTERS


def snapshot_hierarchy(version: float, nodes: list[HierarchyNode]) -> WorkspaceHierarchy:
    """Detach validated discovery records from their HDF5 storage handles."""
    return WorkspaceHierarchy(
        version=version,
        nodes=tuple(
            HierarchyEntity(
                uid=node.uid,
                name=(
                    text(node.attributes["Name"]).replace("\u2044", "/")
                    if node.concatenator is not None else text(node.attributes["Name"])
                ),
                entity_type=node.entity_type,
                parent_uid=node.parent_uid,
                is_object=node.is_object,
                is_root=node.is_root,
                conversion_supported=node.conversion_supported,
            )
            for node in nodes
        ),
    )


def _native_node(handle: h5py.Group, is_object: bool) -> HierarchyNode:
    try:
        attributes = {key: handle.attrs[key] for key in ("ID", "Name")}
        if "Visible" in handle.attrs:
            attributes["Visible"] = handle.attrs["Visible"]
        type_attributes = H5Reader.fetch_type_attributes(group(handle, "Type"))
        missing = {"uid", "name"} - type_attributes.keys()
        if missing:
            raise KeyError(f"Type is missing {sorted(missing)}")
        return HierarchyNode(
            uid(attributes["ID"]), attributes, type_attributes, is_object, group=handle
        )
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError(f"{handle.name}: {error}") from error


def _is_indexed(handle: h5py.Group, family: str) -> bool:
    """Whether ``handle`` is the flat-index definition H5Reader resolves by UID."""
    project = project_group(handle.file)
    key = "{" + uid(handle.attrs["ID"]) + "}"
    return family in project and key in project[family] and project[family][key].id == handle.id


def concatenated_records(handle: h5py.Group, version: float) -> list[dict]:
    """Read attribute records through their reachable concatenator handle.

    Indexed concatenators use ``H5Reader.fetch_concatenated_attributes``;
    hierarchy-only handles, which H5Reader cannot address, are decoded directly.
    """
    # Mirrors Concatenator.concat_attr_str.
    label = "Attributes Jsons" if version > 2.0 else "Attributes"
    fetched = (
        H5Reader.fetch_concatenated_attributes(
            handle.file, UUID(uid(handle.attrs["ID"])), "group", label,
        )
        if _is_indexed(handle, "Groups") else None
    )
    if fetched is not None:
        records = fetched.get("Attributes") if isinstance(fetched, dict) else None
    else:
        raw = dataset(group(handle, "Concatenated Data"), label)[()]
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
    """Resolve stored type attributes via ``H5Reader.fetch_type``, or a registered type.

    Keys follow geoh5py's attribute names (``uid``, ``name``, ...).
    """
    location = f"Types/Object types/{{{type_uid}}}"
    if location in project:
        attributes = H5Reader.fetch_type(project.file, UUID(type_uid), "Object")
        if uid(attributes["uid"]) != type_uid:
            raise ValueError(f"{project.name}/{location}: conflicting object type ID.")
        return attributes
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
    return {"uid": "{" + type_uid + "}", "name": name}


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
    project: h5py.Group, handle: h5py.Group, version: float, root_uid: str | None,
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
            if root_uid is not None and child.uid == root_uid:
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


def _indexed_nodes(project: h5py.Group) -> dict[str, HierarchyNode]:
    """Read native entities from the flat indexes when no root is stored."""
    nodes = {}
    for family in ("Groups", "Objects"):
        if family not in project:
            continue
        collection = group(project, family)
        for key in collection:
            handle = group(collection, key)
            node = _native_node(handle, family == "Objects")
            if uid(key) != node.uid:
                raise ValueError(f"{collection.name}/{key}: link and entity UID differ.")
            if node.uid in nodes:
                raise ValueError(f"Entity {node.uid}: duplicate flat index entry.")
            nodes[node.uid] = node
    return nodes


def _is_registered_root(node: HierarchyNode) -> bool:
    return TYPE_UID_TO_CLASS.get(UUID(uid(node.type_attributes["uid"]))) is RootGroup


def _rootless_hierarchy(
    project: h5py.Group, version: float, indexed_nodes: dict[str, HierarchyNode],
) -> list[HierarchyNode]:
    """Resolve all indexed entities and hierarchy-only descendants as a forest."""
    nodes = indexed_nodes.copy()
    children: dict[str, list[str]] = {}
    parents: dict[str, set[str]] = {}
    expanded = set()
    pending = list(indexed_nodes.values())
    while pending:
        parent = pending.pop()
        if parent.uid in expanded:
            continue
        expanded.add(parent.uid)
        immediate: dict[str, HierarchyNode] = {}
        for child in _children(project, parent.group, version, None):
            previous = immediate.get(child.uid)
            if previous is not None:
                if (
                    child.is_object != previous.is_object
                    or child.group is None or previous.group is None
                    or child.group.id != previous.group.id
                ):
                    raise ValueError(f"Entity {child.uid}: conflicting native definitions.")
                continue
            indexed = nodes.get(child.uid)
            if indexed is not None:
                if (
                    child.is_object != indexed.is_object
                    or child.group is None and indexed.group is not None
                    or child.group is not None and indexed.group is None
                    or child.group is not None and child.group.id != indexed.group.id
                ):
                    raise ValueError(f"Entity {child.uid}: conflicting native definitions.")
                child = indexed
            else:
                nodes[child.uid] = child
            immediate[child.uid] = child
            parents.setdefault(child.uid, set()).add(parent.uid)
            if child.group is not None:
                pending.append(child)
        children[parent.uid] = sorted(immediate)

    conflicting = next(
        (uid_ for uid_, parent_uids in parents.items() if len(parent_uids) > 1),
        None,
    )
    if conflicting is not None:
        raise ValueError(f"Entity {conflicting}: conflicting parents in rootless hierarchy.")

    starts = sorted(
        (node for uid_, node in nodes.items() if uid_ not in parents),
        key=lambda node: node.uid,
    )
    result = []
    seen = set()
    pending_nodes = [(node, None, "") for node in reversed(starts)]
    while pending_nodes:
        node, parent_uid, parent_type = pending_nodes.pop()
        if node.uid in seen:
            raise ValueError(
                f"Entity {node.uid}: repeated UID, conflicting parents or cyclic hierarchy."
            )
        seen.add(node.uid)
        node.parent_uid = parent_uid
        node.entity_type, node.conversion_supported = node.type_name(version, parent_type)
        result.append(node)
        for child_uid in reversed(children.get(node.uid, [])):
            pending_nodes.append((nodes[child_uid], node.uid, node.entity_type))

    if seen != set(nodes):
        unresolved = min(set(nodes) - seen)
        raise ValueError(f"Entity {unresolved}: cyclic hierarchy has no top-level parent.")
    return result


def read_hierarchy(project: h5py.Group) -> tuple[float, list[HierarchyNode]]:
    """Resolve root aliases and return UID-sorted depth-first native entities.

    The indexed root supplies attributes and child links when present; /Root
    is only a fallback. Both representations must match in ID and type ID.
    If neither representation exists, the flat Groups and Objects indexes define
    a forest, and their native child links define parentage. Non-root definitions
    must match the flat index when present. Hierarchy-only entities are supported.
    Multiple parents and cycles are rejected. No geometry, channel values, or
    display XML is read.
    """
    try:
        version = float(project.attrs["Version"])
        if not np.isfinite(version) or version <= 0:
            raise ValueError("Invalid geoh5 format version.")
        if "Root" in project:
            root = _native_node(group(project, "Root"), False)
            key = "{" + root.uid + "}"
            if "Groups" in project and key in group(project, "Groups"):
                indexed = _native_node(group(group(project, "Groups"), key), False)
                if indexed.uid != root.uid:
                    raise ValueError(
                        "Conflicting root identities: /Root and indexed root IDs differ."
                    )
                if uid(indexed.type_attributes["uid"]) != uid(root.type_attributes["uid"]):
                    raise ValueError("Conflicting root type identities.")
                root = indexed
        else:
            indexed_nodes = _indexed_nodes(project)
            indexed_roots = [node for node in indexed_nodes.values() if _is_registered_root(node)]
            if len(indexed_roots) > 1:
                raise ValueError("Multiple indexed RootGroup entities.")
            if not indexed_roots:
                return version, _rootless_hierarchy(project, version, indexed_nodes)
            root = indexed_roots[0]

        root.is_root = True
        root.entity_type, root.conversion_supported = root.type_name(version, "")
        starts = [(root, [root.group])]

        result = []
        seen = {node.uid for node, _ in starts}
        pending = list(reversed(starts))
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
