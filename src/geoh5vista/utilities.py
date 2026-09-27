"""Utilities for geoh5vista."""

from __future__ import annotations

import warnings
from typing import Any, Final

import numpy as np
from geoh5py.objects.object_base import ObjectBase

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "check_orientation",
    "check_orthogonal",
    "get_gh5_entity_colour",
    "normalize_visibility",
)


MODULE_DISPLAY_NAME: Final[str] = "Utilities"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "check_orientation": "Check Orientation",
    "check_orthogonal": "Check Orthogonal",
    "get_gh5_entity_colour": "Get GH5 Entity Colour",
    "normalize_visibility": "Normalize Visibility",
}


def check_orientation(
    axis_u: np.ndarray, axis_v: np.ndarray, axis_w: np.ndarray
) -> bool:
    """Check if the given axes form a rectilinear cartesian reference frame.

    Parameters
    ----------
    axis_u : numpy.ndarray
        The first axis vector.
    axis_v : numpy.ndarray
        The second axis vector.
    axis_w : numpy.ndarray
        The third axis vector.

    Returns
    -------
    bool
        ``True`` if the axes form a rectilinear frame, ``False`` otherwise.

    """
    if (
        np.allclose(axis_u, (1, 0, 0))
        and np.allclose(axis_v, (0, 1, 0))
        and np.allclose(axis_w, (0, 0, 1))
    ):
        return True
    return False


def check_orthogonal(
    axis_u: np.ndarray, axis_v: np.ndarray, axis_w: np.ndarray
) -> bool:
    """Check if the three input vectors are orthogonal.

    Parameters
    ----------
    axis_u : numpy.ndarray
        The first axis vector.
    axis_v : numpy.ndarray
        The second axis vector.
    axis_w : numpy.ndarray
        The third axis vector.

    Returns
    -------
    bool
        ``True`` if the axes are orthogonal, ``False`` otherwise.

    """
    if not (
        np.abs(axis_u.dot(axis_v) < 1e-6)
        and np.abs(axis_v.dot(axis_w) < 1e-6)
        and np.abs(axis_w.dot(axis_u) < 1e-6)
    ):
        # raise ValueError('axis_u, axis_v, and axis_w must be orthogonal')
        return False
    return True


def get_gh5_entity_colour(gh5_entity: ObjectBase) -> list[int]:
    """Get the color of a geoh5py entity from its visual parameters.

    Parameters
    ----------
    gh5_entity : geoh5py.objects.base_object.BaseObject
        The geoh5py entity to get the color of.

    Returns
    -------
    list[int]
        The RGB color as a list of three integers.

    """
    data_list = gh5_entity.get_data("Visual Parameters")
    if not data_list:
        return [0, 0, 0]  # Return a default color if no visual parameters

    a = data_list[0]
    if a.colour is None:
        return [0, 0, 0]

    c = a.colour  # Colour order was BGR before geoh5py 0.12.1
    true_color = [c[0], c[1], c[2]]  # Convert to RGB order
    return true_color


def normalize_visibility(value: Any) -> bool:
    """Convert a geoh5py visibility value to a Python ``bool``.

    geoh5py may report visibility in several forms depending on the entity
    type and how it was loaded (e.g. ``np.int8(0)`` when read from file).

    Rules:

    * ``None`` (not set) -> ``True``.
    * Python/NumPy booleans and integers -> ``False`` if zero, else ``True``.
    * Dicts with a ``"Visible"`` key -> the ``"Visible"`` entry normalized.
    * Arrays/sequences -> ``True`` if any element is non-zero; empty -> ``False``.
    * Any other value -> ``True`` with a ``UserWarning``.

    Parameters
    ----------
    value : Any
        The visibility value, typically ``entity.visible``.

    Returns
    -------
    bool
        ``True`` if the entity should be considered visible.

    """
    if value is None:
        return True
    if isinstance(value, dict):
        if "Visible" in value:
            return normalize_visibility(value["Visible"])
    elif isinstance(value, (bool, int, np.bool_, np.integer)):
        return bool(value)
    elif isinstance(value, (np.ndarray, list, tuple)):
        arr = np.asarray(value)
        if arr.size == 0:
            return False
        if arr.dtype.kind in "biu":
            return bool(arr.any())

    warnings.warn(
        f"Unrecognized visibility value {value!r} ({type(value).__name__}); "
        "treating as visible.",
        UserWarning,
        stacklevel=2,
    )
    return True
