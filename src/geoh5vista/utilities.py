"""Utilities for geoh5vista."""

from __future__ import annotations

from typing import Final
import numpy as np
from geoh5py.objects.object_base import ObjectBase


__all__ = (
    "check_orientation",
    "check_orthogonal",
    "get_gh5_entity_colour",
    "MODULE_DISPLAY_NAME",
    "FUNCTION_DISPLAY_NAMES"
)


MODULE_DISPLAY_NAME: Final[str] = "Utilities"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "check_orientation": "Check Orientation",
    "check_orthogonal": "Check Orthogonal",
    "get_gh5_entity_colour": "Get GH5 Entity Colour",
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
