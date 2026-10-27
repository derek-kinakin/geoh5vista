"""Metadata-only discovery, without constructing geoh5py entities or VTK objects.

Opening a geoh5py Workspace eagerly loads payload arrays, so discovery reads
only the specific HDF5 metadata structures used below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
from xml.etree import ElementTree

import h5py
import numpy as np
from geoh5py.workspace.workspace import TYPE_UID_TO_CLASS

from .constants import CONVERTERS
from .utilities import normalize_visibility

__all__ = ("EntityMetadata", "catalog_geoh5")


@dataclass(frozen=True, slots=True)
class EntityMetadata:
    """Detached native entity metadata returned by :func:`catalog_geoh5`.

    UIDs are canonical UUID strings. Colour is RGB, or ``None`` if absent.
    Conversion support describes the type, not the validity of its geometry.
    ``parent_uid`` may identify a root or organizational group not cataloged.
    """

    uid: str
    name: str
    entity_type: str
    parent_uid: str | None
    visible: bool
    colour: tuple[int, int, int] | None
    conversion_supported: bool
    unsupported_reason: str | None


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError(f"Expected text metadata, got {type(value).__name__}.")


def _uid(value: object) -> str:
    return str(UUID(_text(value)))


def _group(parent: h5py.Group, key: str) -> h5py.Group:
    value = parent[key]
    if not isinstance(value, h5py.Group):
        raise ValueError(f"{value.name}: expected an HDF5 group.")
    return value


def _dataset(parent: h5py.Group, key: str) -> h5py.Dataset:
    value = parent[key]
    if not isinstance(value, h5py.Dataset):
        raise ValueError(f"{value.name}: expected an HDF5 dataset.")
    return value


def _colour(value: object) -> tuple[int, int, int] | None:
    if isinstance(value, np.ndarray):
        if value.size != 1:
            raise ValueError("Visual Parameters must contain one XML string.")
        value = value.item()
    xml = ElementTree.fromstring(_text(value))
    element = xml.find("Colour")
    if element is None or not element.text:
        return None
    packed = int(element.text).to_bytes(4, byteorder="little")
    return packed[2], packed[1], packed[0]


def _object_colour(entity: h5py.Group) -> tuple[int, int, int] | None:
    if "Data" not in entity:
        return None
    children = _group(entity, "Data")
    for key in sorted(children):
        child = _group(children, key)
        if _text(child.attrs["Name"]) == "Visual Parameters":
            if "Data" not in child:
                return None
            return _colour(_dataset(child, "Data")[()])
    return None


def _concatenated_colours(
    group: h5py.Group,
    property_ids: set[str],
) -> dict[str, tuple[int, int, int] | None]:
    if not property_ids:
        return {}
    storage = _group(group, "Concatenated Data")
    if "Index" not in storage:
        return {}
    index = _group(storage, "Index")
    if "Visual Parameters" not in index:
        return {}
    dataset = _dataset(index, "Visual Parameters")
    fields = dataset.dtype.names or ()
    if dataset.ndim != 1 or not {"Data ID", "Start index", "Size"}.issubset(fields):
        raise ValueError(f"{dataset.name}: invalid Visual Parameters index schema.")
    if any(dataset.dtype[field].kind not in "iu" for field in ("Start index", "Size")):
        raise ValueError(f"{dataset.name}: concatenation offsets must be integers.")
    rows = dataset[()]
    colours = {}
    for row in rows:
        uid = _uid(row["Data ID"])
        if uid not in property_ids:
            continue
        if uid in colours:
            raise ValueError(f"Duplicate Visual Parameters index for {uid}.")
        start, size = int(row["Start index"]), int(row["Size"])
        if "Data" in storage and "Visual Parameters" in _group(storage, "Data"):
            values = _dataset(_group(storage, "Data"), "Visual Parameters")
        else:
            values = _dataset(storage, "Visual Parameters")
        if values.ndim != 1 or start < 0 or size != 1 or start + size > values.shape[0]:
            raise ValueError("Invalid Visual Parameters concatenation slice.")
        colours[uid] = _colour(values[start : start + size])
    return colours


@dataclass
class _Node:
    uid: str
    attributes: dict
    type_attributes: dict
    is_object: bool
    group: h5py.Group | None = None
    concatenator: h5py.Group | None = None
    colour: tuple[int, int, int] | None = None

    def type_name(self, version: float, parent_type: str) -> tuple[str, bool]:
        type_uid = UUID(_uid(self.type_attributes["ID"]))
        member = TYPE_UID_TO_CLASS.get(type_uid)
        if member is None:
            return _text(self.type_attributes.get("Name", str(type_uid))), False
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


def _native_node(group: h5py.Group, is_object: bool) -> _Node:
    try:
        attributes = {key: group.attrs[key] for key in ("ID", "Name")}
        attributes["Visible"] = group.attrs.get("Visible")
        entity_type = _group(group, "Type")
        type_attributes = {key: entity_type.attrs[key] for key in ("ID", "Name")}
        return _Node(
            _uid(attributes["ID"]), attributes, type_attributes, is_object, group
        )
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError(f"{group.name}: {error}") from error


def _concatenated_nodes(
    project: h5py.Group,
    group: h5py.Group,
    version: float,
) -> list[_Node]:
    if "Concatenated object IDs" not in group:
        return []
    object_ids = _dataset(group, "Concatenated object IDs")[()]
    if not len(object_ids):
        return []
    storage = _group(group, "Concatenated Data")
    label = "Attributes Jsons" if version > 2.0 else "Attributes"
    raw = _dataset(storage, label)[()]
    if version > 2.0:
        records = [json.loads(_text(value)) for value in raw]
    else:
        if isinstance(raw, np.ndarray):
            if raw.size != 1:
                raise ValueError("Expected one concatenated Attributes JSON document.")
            raw = raw.item()
        records = json.loads(_text(raw))["Attributes"]
    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        raise ValueError(
            "Concatenated attributes must be a list of metadata dictionaries."
        )
    by_uid = {_uid(record["ID"]): record for record in records}
    if len(by_uid) != len(records):
        raise ValueError("Duplicate concatenated metadata UIDs.")
    nodes = []
    types = _group(_group(project, "Types"), "Object types")
    for value in object_ids:
        uid = _uid(value)
        attributes = by_uid[uid]
        type_uid = _uid(attributes["Object Type ID"])
        entity_type = _group(types, "{" + type_uid + "}")
        type_attributes = {key: entity_type.attrs[key] for key in ("ID", "Name")}
        nodes.append(_Node(uid, attributes, type_attributes, True, concatenator=group))
    property_ids = {
        _uid(node.attributes["Property:Visual Parameters"])
        for node in nodes
        if "Property:Visual Parameters" in node.attributes
    }
    colours = _concatenated_colours(group, property_ids)
    for node in nodes:
        if "Property:Visual Parameters" in node.attributes:
            node.colour = colours.get(
                _uid(node.attributes["Property:Visual Parameters"])
            )
    return nodes


def _children(project: h5py.Group, node: _Node, version: float) -> list[_Node]:
    if node.group is None:
        return []
    children = []
    for family in ("Groups", "Objects"):
        if family not in node.group:
            continue
        collection = _group(node.group, family)
        for key in collection:
            child = _native_node(_group(collection, key), family == "Objects")
            if _uid(key) != child.uid:
                raise ValueError(
                    f"{collection.name}/{key}: link and entity UID differ."
                )
            children.append(child)
    children.extend(_concatenated_nodes(project, node.group, version))
    return sorted(children, key=lambda item: item.uid)


def _read_catalog(file: h5py.File) -> list[EntityMetadata]:
    if len(file) != 1:
        raise ValueError("Expected one geoh5 project group.")
    project = _group(file, next(iter(file)))
    version = float(project.attrs["Version"])
    if not np.isfinite(version) or version <= 0:
        raise ValueError("Invalid geoh5 format version.")
    root = _native_node(_group(project, "Root"), False)
    result = []
    seen = {root.uid}
    pending = [
        (node, root.uid, "") for node in reversed(_children(project, root, version))
    ]
    while pending:
        node, parent_uid, parent_type = pending.pop()
        try:
            if node.uid in seen:
                raise ValueError("Repeated entity UID or cyclic hierarchy.")
            seen.add(node.uid)
            entity_type, supported = node.type_name(version, parent_type)
            if node.is_object or supported:
                name = _text(node.attributes["Name"])
                if node.concatenator is not None:
                    name = name.replace("\u2044", "/")
                    colour = node.colour
                elif node.is_object and node.group is not None:
                    colour = _object_colour(node.group)
                else:
                    colour = None
                result.append(
                    EntityMetadata(
                        uid=node.uid,
                        name=name,
                        entity_type=entity_type,
                        parent_uid=parent_uid,
                        visible=normalize_visibility(node.attributes.get("Visible")),
                        colour=colour,
                        conversion_supported=supported,
                        unsupported_reason=None
                        if supported
                        else (
                            f"No converter is registered for native type {entity_type!r} "
                            f"({node.type_attributes['ID']})."
                        ),
                    )
                )
            pending.extend(
                (child, node.uid, entity_type)
                for child in reversed(_children(project, node, version))
            )
        except (
            KeyError,
            ValueError,
            TypeError,
            OverflowError,
            ElementTree.ParseError,
        ) as error:
            raise ValueError(f"Entity {node.uid}: {error}") from error
    return result


def catalog_geoh5(workspace_path: str | Path) -> list[EntityMetadata]:
    """List root-reachable objects and convertible groups without reading payload arrays.

    Includes unsupported objects, hidden objects, and individual drillholes.
    Excludes data channels, property groups, organizational groups, the root,
    and generated conversion components. Immediate parent UIDs are retained.
    Ordering is depth-first, with siblings sorted by canonical UID.

    Only hierarchy/type/display metadata, concatenated attribute JSON and IDs,
    and Visual Parameters XML (and its own index, when concatenated) are read.
    Geometry, surveys and observation values are never read; counts are omitted.
    Missing colour is ``None`` rather than a converter's default colour.
    Visibility uses the existing normalization policy without ancestor folding.
    No geoh5py entities or PyVista objects are constructed or returned.

    Parameters
    ----------
    workspace_path : str or pathlib.Path
        Existing geoh5 file. Opened read-only and closed before returning.

    Returns
    -------
    list[EntityMetadata]
        Detached, immutable records; duplicate display names are preserved.

    Raises
    ------
    OSError
        If the file cannot be opened, including missing or non-HDF5 files.
    ValueError
        If required geoh5 hierarchy or metadata is malformed.
    """
    path = Path(workspace_path)
    with h5py.File(path, "r") as file:
        try:
            return _read_catalog(file)
        except (
            KeyError,
            ValueError,
            TypeError,
            OverflowError,
            ElementTree.ParseError,
        ) as error:
            raise ValueError(f"Cannot catalog geoh5 file {path}: {error}") from error
