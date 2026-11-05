"""Metadata-only discovery, without constructing geoh5py entities or VTK objects.

Opening a geoh5py Workspace eagerly loads payload arrays, so discovery reads
only the specific HDF5 metadata structures used below.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

import h5py

from ..models import EntityMetadata
from ._hdf5 import project_group
from .hierarchy import read_colours, read_hierarchy, snapshot_hierarchy

__all__ = ("EntityMetadata", "catalog_geoh5")


def _read_catalog(file: h5py.File) -> list[EntityMetadata]:
    version, nodes = read_hierarchy(project_group(file))
    hierarchy = snapshot_hierarchy(version, nodes, read_colours(nodes))
    type_uids = {node.uid: node.type_attributes["uid"] for node in nodes}
    return [
        EntityMetadata(
            uid=entity.uid,
            name=entity.name,
            entity_type=entity.entity_type,
            parent_uid=entity.parent_uid,
            visible=entity.visible,
            colour=entity.colour,
            conversion_supported=entity.conversion_supported,
            unsupported_reason=None
            if entity.conversion_supported
            else (
                f"No converter is registered for native type {entity.entity_type!r} "
                f"({type_uids[entity.uid]})."
            ),
        )
        for entity in hierarchy.nodes
        if not entity.is_root and (entity.is_object or entity.conversion_supported)
    ]

def catalog_geoh5(workspace_path: str | Path) -> list[EntityMetadata]:
    """List native-hierarchy objects and convertible groups without payload arrays.

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
