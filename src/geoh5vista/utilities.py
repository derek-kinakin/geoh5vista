__all__ = [
    "check_orientation",
    "check_orthogonal",
    "get_gh5_entity_colour",
]


#import pyvista
import numpy as np

#try:
#    from pyvista import is_pyvista_obj as is_pyvista_dataset
#except ImportError:
#    from pyvista import is_pyvista_dataset


def check_orientation(axis_u, axis_v, axis_w):
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


def check_orthogonal(axis_u, axis_v, axis_w):
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


def RGB_from_GA(ga_int):
    """Convert a Geoscience ANALYST integer color to an RGB tuple.

    See: https://levelup.gitconnected.com/how-to-convert-argb-integer-into-rgba-tuple-in-python-eeb851d65a88

    Parameters
    ----------
    ga_int : int
        The Geoscience ANALYST integer color.

    Returns
    -------
    list
        The RGB color as a list of three integers.

    """
    c_string = (ga_int).to_bytes(4, byteorder="little").hex()
    rgb = [int(c_string[i : i + 2], 16) for i in range(0, 8, 2)][:3]
    return rgb


def get_gh5_entity_colour(gh5_entity):
    """Get the color of a geoh5py entity from its visual parameters.

    Parameters
    ----------
    ga_entity : geoh5py.objects.base_object.BaseObject
        The geoh5py entity to get the color of.

    Returns
    -------
    list
        The RGB color as a list of three integers.

    """
    a = gh5_entity.get_data("Visual Parameters")[0]
    c = a.colour # Colour order is BGR
    true_color = [c[2],c[1],c[0]] # Convert to RGB order
    return true_color

