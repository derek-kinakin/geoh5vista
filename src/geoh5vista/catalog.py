"""Metadata-only discovery, without constructing geoh5py entities or VTK objects.

Opening a geoh5py Workspace eagerly loads payload arrays, so discovery reads
only the specific HDF5 metadata structures used below.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import h5py
import numpy as np

from .hierarchy import dataset as _dataset
from .hierarchy import group as _group
from .hierarchy import read_hierarchy
from .hierarchy import text as _text
from .hierarchy import uid as _uid
from .visibility import project_group, stored_visibility

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


def _read_catalog(file: h5py.File) -> list[EntityMetadata]:
    project = project_group(file)
    _, nodes = read_hierarchy(project)
    result = []
    property_ids: dict[str, set[str]] = {}
    for node in nodes[1:]:
        if node.concatenator is not None and "Property:Visual Parameters" in node.attributes:
            property_ids.setdefault(node.parent_uid, set()).add(
                _uid(node.attributes["Property:Visual Parameters"])
            )
    concatenated_colours = {}
    for node in nodes[1:]:
        try:
            entity_type, supported = node.entity_type, node.conversion_supported
            if node.is_object or supported:
                name = _text(node.attributes["Name"])
                if node.concatenator is not None:
                    name = name.replace("\u2044", "/")
                    if node.parent_uid not in concatenated_colours:
                        concatenated_colours[node.parent_uid] = _concatenated_colours(
                            node.concatenator, property_ids.get(node.parent_uid, set()),
                        )
                    colour = (
                        concatenated_colours[node.parent_uid].get(
                            _uid(node.attributes["Property:Visual Parameters"])
                        ) if "Property:Visual Parameters" in node.attributes else None
                    )
                elif node.is_object and node.group is not None:
                    colour = _object_colour(node.group)
                else:
                    colour = None
                result.append(
                    EntityMetadata(
                        uid=node.uid,
                        name=name,
                        entity_type=entity_type,
                        parent_uid=node.parent_uid,
                        visible=stored_visibility(
                            node.attributes, context=f"Entity {node.uid}"
                        ),
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
    Visibility is the stored entity checkbox, never per-view or ancestor state.
    A missing Visible attribute defaults to True; malformed values raise ValueError.
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
