__all__ = [
    "check_orientation",
    "check_orthogonal",
    "get_ga_entity_colour",
]


#import pyvista
import numpy as np

#try:
#    from pyvista import is_pyvista_obj as is_pyvista_dataset
#except ImportError:
#    from pyvista import is_pyvista_dataset


def check_orientation(axis_u, axis_v, axis_w):
    """This will check if the given ``axis_*`` vectors are the typical
    cartesian refernece frame (i.e. rectilinear).
    """
    if (
        np.allclose(axis_u, (1, 0, 0))
        and np.allclose(axis_v, (0, 1, 0))
        and np.allclose(axis_w, (0, 0, 1))
    ):
        return True
    return False


def check_orthogonal(axis_u, axis_v, axis_w):
    """Makes sure that the three input vectors are orthogonal"""
    if not (
        np.abs(axis_u.dot(axis_v) < 1e-6)
        and np.abs(axis_v.dot(axis_w) < 1e-6)
        and np.abs(axis_w.dot(axis_u) < 1e-6)
    ):
        # raise ValueError('axis_u, axis_v, and axis_w must be orthogonal')
        return False
    return True


def RGB_from_GA(ga_int):
    """https://levelup.gitconnected.com/how-to-convert-argb-integer-into-rgba-tuple-in-python-eeb851d65a88

    Args:
        argb_int (_type_): _description_

    Returns:
        _type_: _description_
    """
    c_string = (ga_int).to_bytes(4, byteorder="little").hex()
    rgb = [int(c_string[i : i + 2], 16) for i in range(0, 8, 2)][:3]
    return rgb


def get_ga_entity_colour(ga_entity):
    a = ga_entity.get_data("Visual Parameters")[0]
    c = a.colour # Colour order is BGR
    true_color = [c[2],c[1],c[0]] # Convert to RGB order
    return true_color

