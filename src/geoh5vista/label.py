"""This module provides functions for converting geoh5py Label objects to PyVista data objects.

A geoh5 label is an annotation consisting of a text anchor (the label
position) connected by a leader line to a point of interest (the target
position). It is represented in PyVista as a two-point ``pyvista.PolyData``
line running from the label position to the target position.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Final

import numpy as np
import pyvista
from geoh5py.objects.label import Label

from geoh5vista.data import add_entity_metadata

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "get_label_text",
    "label_geom_to_vtk",
    "label_to_vtk",
)


MODULE_DISPLAY_NAME: Final[str] = "Label"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "get_label_text": "Get Label Text",
    "label_geom_to_vtk": "Label Geometry to VTK",
    "label_to_vtk": "Label to VTK",
}

_LABEL_POSITION_KEY: Final[str] = "Label position"
_TARGET_POSITION_KEY: Final[str] = "Target position"


def _get_raw_attribute(label: Label, key: str) -> Any:
    """Return a raw geoh5 attribute that geoh5py stores on the entity ``__dict__``.

    geoh5py does not yet implement ``Label`` attributes, so unrecognised
    attributes read from file (e.g. ``"Label position"``) are set directly on
    the instance under their original geoh5 names.
    """
    value = label.__dict__.get(key)
    if value is None:
        value = getattr(label, key.lower().replace(" ", "_"), None)
    return value


def _to_xyz(value: Any, key: str) -> np.ndarray:
    """Convert a geoh5 ``(x, y, z)`` compound value to a float array of shape ``(3,)``."""
    if value is None:
        raise ValueError(f"Label is missing the '{key}' attribute.")
    if isinstance(value, np.void) or (
        isinstance(value, np.ndarray) and value.dtype.names is not None
    ):
        value = tuple(value.item() if isinstance(value, np.ndarray) else value)
    xyz = np.asarray(value, dtype=float).ravel()
    if xyz.shape != (3,):
        raise ValueError(f"Label '{key}' must contain three coordinates, got {xyz.shape}.")
    return xyz


def get_label_text(label: Label) -> str | None:
    """Return the user-entered text of a geoh5 label.

    The text is stored in the ``<Text>`` element of the label's
    Visual Parameters XML.

    Parameters
    ----------
    label : geoh5py.objects.label.Label
        The label to read.

    Returns
    -------
    str or None
        The label text, or ``None`` if no text is stored.

    """
    data_list = label.get_data("Visual Parameters")
    if not data_list:
        return None

    xml = getattr(data_list[0], "xml", None)
    if xml is None:
        raw = data_list[0].values
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            xml = ET.fromstring(str(raw))
        except ET.ParseError:
            return None

    text_elem = xml.find(".//Text")
    if text_elem is None:
        return None
    return text_elem.text or ""


def label_geom_to_vtk(label: Label) -> pyvista.PolyData:
    """Convert the label geometry to a two-point ``pyvista.PolyData`` line.

    The first point is the label position and the second point is the
    target position.

    Parameters
    ----------
    label : geoh5py.objects.label.Label
        The label to convert.

    Returns
    -------
    pyvista.PolyData
        A single line segment from the label position to the target position.

    """
    label_position = _to_xyz(_get_raw_attribute(label, _LABEL_POSITION_KEY), _LABEL_POSITION_KEY)
    target_position = _to_xyz(_get_raw_attribute(label, _TARGET_POSITION_KEY), _TARGET_POSITION_KEY)

    output = pyvista.PolyData()
    output.points = np.vstack([label_position, target_position])
    output.lines = np.array([2, 0, 1], dtype=np.int_)
    return output


def label_to_vtk(label: Label) -> pyvista.PolyData:
    """Convert a ``geoh5py.objects.label.Label`` to a ``pyvista.PolyData`` line.

    The entity name (e.g. ``"Label1"``) is used as the display name, matching
    other entities. The standard entity metadata (including the colour) is
    stored in ``user_dict["geoh5"]``, and the user-entered label text is
    stored as a string in ``user_dict["geoh5"]["label"]``.

    Parameters
    ----------
    label : geoh5py.objects.label.Label
        The label to convert.

    Returns
    -------
    pyvista.PolyData
        The label as a line from the label position to the target position.

    """
    output = label_geom_to_vtk(label)
    output = add_entity_metadata(output, label)

    # Reassign so the pyvista user_dict change is persisted.
    metadata = output.user_dict["geoh5"]
    metadata["label"] = get_label_text(label)
    output.user_dict["geoh5"] = metadata

    return output
