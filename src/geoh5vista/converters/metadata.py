"""Transfer source and display metadata between geoh5py entities and PyVista objects."""

from __future__ import annotations

from typing import Final, TypeVar

import pyvista
from geoh5py.groups.base import Group
from geoh5py.groups.root import RootGroup
from geoh5py.objects.object_base import ObjectBase

from ..utilities import get_gh5_entity_colour
from ..visibility import entity_visibility

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "add_entity_metadata",
    "restore_entity_metadata",
)

MODULE_DISPLAY_NAME: Final[str] = "Metadata"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "add_entity_metadata": "Add Entity Metadata",
    "restore_entity_metadata": "Restore Entity Metadata",
}

_DataObject = TypeVar("_DataObject", bound=pyvista.DataObject)


def add_entity_metadata(output: _DataObject, entity: ObjectBase | Group) -> _DataObject:
    """Add geoh5 entity metadata to a VTK object as a user_dict.

    The metadata is stored in ``output.user_dict["geoh5"]`` as a nested
    dictionary containing schema version, source, and display information.
    Visibility is the entity's stored checkbox, independent of views and parents.
    A missing attribute defaults to True; malformed stored values raise ValueError.

    Parameters
    ----------
    output : pyvista.DataObject
        The VTK data object to add the metadata to.
    entity : geoh5py.objects.object_base.ObjectBase or geoh5py.groups.base.Group
        The geoh5py entity to source the metadata from.

    Returns
    -------
    pyvista.DataObject
        The VTK data object with added metadata.
    """
    parent_uid = (
        str(entity.parent.uid)
        if entity.parent is not None
        and not (isinstance(entity.parent, RootGroup) and not entity.parent.on_file)
        else None
    )
    output.user_dict["geoh5"] = {
        "schema_version": 1,
        "source": {
            "uid": str(entity.uid),
            "entity_type": entity.__class__.__name__,
            "parent_uid": parent_uid,
        },
        "display": {
            "name": entity.name,
            "colour": get_gh5_entity_colour(entity) if isinstance(entity, ObjectBase)
            else [255, 255, 255],
            "visible": entity_visibility(entity),
        },
    }
    return output


def restore_entity_metadata(
    output: ObjectBase, data: pyvista.DataSet, *, name: str | None = None,
) -> ObjectBase:
    """Restore geoh5 display metadata onto an existing geoh5 entity.

    Reads schema version 1 from ``data.user_dict["geoh5"]``. Missing
    metadata or display fields leave the corresponding entity defaults
    unchanged. All supported fields are validated before applying changes.
    Source UID, parent UID, and entity type are not restored.

    Parameters
    ----------
    output : geoh5py.objects.object_base.ObjectBase
        The newly created entity to update in place.
    data : pyvista.DataSet
        The PyVista object containing geoh5 metadata.
    name : str or None, optional
        An explicit name overriding the stored display name.
        Only applied when geoh5 metadata is present.

    Returns
    -------
    geoh5py.objects.object_base.ObjectBase
        The updated entity.

    Raises
    ------
    ValueError
        If the metadata schema or a supported display value is invalid.
    """
    if "geoh5" not in data.user_dict:
        return output
    metadata = data.user_dict["geoh5"]
    if not isinstance(metadata, dict):
        raise TypeError("geoh5 metadata must be a dictionary.")
    version = metadata.get("schema_version")
    if type(version) is not int or version != 1:
        raise TypeError("geoh5.schema_version must be the integer 1.")
    display = metadata.get("display", {})
    if not isinstance(display, dict):
        raise TypeError("geoh5.display must be a dictionary.")
    restored_name = name if name is not None else display.get("name")
    if (name is not None or "name" in display) and not isinstance(restored_name, str):
        raise TypeError("geoh5.display.name must be a string.")
    if "visible" in display and not isinstance(display["visible"], bool):
        raise TypeError("geoh5.display.visible must be a boolean.")
    if "colour" in display:
        colour = display["colour"]
        if (
            not isinstance(colour, (list, tuple))
            or len(colour) != 3
            or not all(type(value) is int and 0 <= value <= 255 for value in colour)
        ):
            raise TypeError(
                "geoh5.display.colour must contain three RGB integers between 0 and 255."
            )
    if restored_name is not None:
        output.name = restored_name
    if "visible" in display:
        output.visible = display["visible"]
    if "colour" in display:
        visual_parameters = output.visual_parameters
        if visual_parameters is None:
            visual_parameters = output.add_default_visual_parameters()
        visual_parameters.colour = list(display["colour"])
    return output
