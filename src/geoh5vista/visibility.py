"""Entity-level visibility, independent of view records and ancestor state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

import h5py
import numpy as np

if TYPE_CHECKING:
    from geoh5py.shared.entity import Entity


def project_group(file: h5py.File) -> h5py.Group:
    """Resolve the single project group required by the existing reader."""
    if len(file) != 1:
        raise ValueError("Expected one geoh5 project group.")
    project = file[next(iter(file))]
    if not isinstance(project, h5py.Group):
        raise ValueError(f"{project.name}: expected an HDF5 group.")  # noqa: TRY004
    return project


def stored_visibility(
    attributes: Mapping[str, object] | h5py.AttributeManager, *, context: str
) -> bool:
    """Read the entity checkbox; missing means visible, malformed means an error.

    geoh5 stores booleans as integers. Preserve zero/nonzero normalization for
    scalar integers, but never aggregate arrays or interpret per-view records.
    """
    if "Visible" not in attributes:
        return True
    value = attributes["Visible"]
    if isinstance(value, np.ndarray) and value.ndim == 0:
        value = value.item()
    if not isinstance(value, (bool, int, np.bool_, np.integer)):
        raise ValueError(  # noqa: TRY004 - malformed file metadata, not a caller type error
            f"{context}: malformed entity Visible attribute; "
            "expected a scalar boolean or integer."
        )
    return bool(value)


def entity_visibility(entity: Entity) -> bool:
    """Resolve an entity's own visibility through its open workspace.

    Native entity properties can be overwritten by the per-view Visible dataset
    during geoh5py loading. Read only the stored attribute instead. Concatenated
    objects expose their original attribute records through their concatenator.
    Unsaved entities have no stored state, so use their explicit in-memory value.
    """
    from geoh5py.groups.base import Group
    from geoh5py.objects.object_base import ObjectBase
    from geoh5py.shared.concatenation.object import ConcatenatedObject

    context = f"Entity {entity.uid}"
    if not entity.on_file:
        return stored_visibility({"Visible": entity.visible}, context=context)

    project = project_group(entity.workspace.geoh5)
    if isinstance(entity, ConcatenatedObject):
        # Unlike get_concatenated_attributes(), this accessor does not append
        # missing records as a side effect of lookup.
        metadata = entity.parent.concatenated_attributes
        records = metadata["Attributes"] if metadata is not None else []
        try:
            matches = [
                record
                for record in records
                if UUID(str(record["ID"]).strip("{}")) == entity.uid
            ]
        except (KeyError, ValueError, TypeError) as error:
            raise ValueError(
                f"{context}: malformed concatenated attribute record."
            ) from error
        if len(matches) != 1:
            raise ValueError(f"{context}: expected one concatenated attribute record.")
        return stored_visibility(matches[0], context=context)

    if entity.uid == entity.workspace.root.uid:
        location = "Root"
    elif isinstance(entity, Group):
        location = f"Groups/{{{entity.uid}}}"
    elif isinstance(entity, ObjectBase):
        location = f"Objects/{{{entity.uid}}}"
    else:
        raise TypeError(f"{context}: unsupported visibility entity type.")

    group = project.get(location)
    if not isinstance(group, h5py.Group):
        raise ValueError(  # noqa: TRY004 - missing/malformed file metadata
            f"{context}: missing entity group at {project.name}/{location}."
        )
    try:
        stored_uid = UUID(str(group.attrs["ID"]).strip("{}"))
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError(f"{context}: malformed entity UID at {group.name}.") from error
    if stored_uid != entity.uid:
        raise ValueError(f"{context}: stored entity UID differs at {group.name}.")
    return stored_visibility(group.attrs, context=f"{context} ({group.name})")
