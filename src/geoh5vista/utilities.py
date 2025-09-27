__all__ = [
    "check_orientation",
    "check_orthogonal",
    "get_ga_entity_colour",
    #"add_texture_coordinates",
]


#import pyvista
import numpy as np
#from PIL import Image


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


#def add_texture_coordinates(output, textures, elname):
#    """Add texture coordinates to a pyvista data object."""
#    if not is_pyvista_dataset(output):
#        output = pyvista.wrap(output)
#    for i, tex in enumerate(textures):
#        # Now map the coordinates for the texture
#        tmp = output.texture_map_to_plane(
#            origin=tex.origin,
#            point_u=tex.origin + tex.axis_u,
#            point_v=tex.origin + tex.axis_v,
#        )
#        # Grab the texture coordinates
#        tcoord = tmp.GetPointData().GetTCoords()
#        name = tex.name
#        if name is None or name == "":
#            name = "{}-texture-{}".format(elname, i)
#        tcoord.SetName(name)
#        # Add these coordinates to the PointData of the output
#        # NOTE: Let pyvista handle setting the TCoords because of how VTK cleans
#        #       up old TCoords
#        output.GetPointData().AddArray(tcoord)
#    return output


#def texture_to_vtk(texture):
#    """Convert an OMF texture to a VTK texture."""
#    img = np.array(Image.open(texture.image))
#    texture.image.seek(0)  # Reset the image bytes in case it is accessed again
#    if img.shape[2] > 3:
#        img = img[:, :, 0:3]
#    vtexture = pyvista.numpy_to_texture(img)
#    return vtexture


#def get_textures(element):
#    """Get a dictionary of textures for a given element."""
#    return [texture_to_vtk(tex) for tex in element.textures]


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

