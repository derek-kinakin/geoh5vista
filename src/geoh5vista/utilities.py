__all__ = [
    "check_orientation",
    "check_orthogonal",
    "add_data_to_vtk",
    "add_data_to_vtk_grid",
    #"add_texture_coordinates",
]


#import pyvista
import numpy as np
#from PIL import Image
from geoh5py.data.referenced_data import ReferencedData
from geoh5py.data.float_data import FloatData
from geoh5py.data.integer_data import IntegerData

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


def add_data_to_vtk(output, entity):
    """Adds data arrays to an output VTK data object. Assigns data to cells or points
    based on number of data values compared to number of cells or points."""

    fields = [f for f in entity.get_data_list() if f not in SKIPDATA]
    #fields = [i.name for i in entity.children]
    #if "Visual Parameters" in fields:
    #    fields.remove("Visual Parameters")
    #if "UserComments" in fields:
    #    fields.remove("UserComments")
    
    for f in fields:
        data_obj = entity.get_data(f)
        if data_obj:
            data = data_obj[0]
            if isinstance(data, ReferencedData):
                data_value_map = data.value_map
                output[f] = data.values
                output[f"{f}_names"] = data_value_map.map_values(output[f])
            elif isinstance(data, FloatData):
                output[f] = data.values
            elif isinstance(data, IntegerData):
                output[f] = data.values
            else:
                pass
        else:
            pass
    
    return output


def add_drillhole_interval_data_to_vtk(output, entity):
    """Adds data arrays to Polydata line objects. Assigns data to cells or points
    based on number of data values compared to number of cells or points."""

    if 'depth' not in output.point_data:
        raise ValueError("The line object must have a 'depth' point data array.")

    point_depths = output.point_data['depth']
    cell_depth_midpoints = (point_depths[:-1] + point_depths[1:]) / 2.0

    fields = [f for f in entity.get_data_list() if f not in SKIPDATA]
    interval_from = entity.from_[0].values
    interval_to = entity.to_[0].values

    for f in fields:
        data_obj = entity.get_data(f)
        if not data_obj:
            continue
        
        data = data_obj[0]
        data_values = data.values

        if isinstance(data, FloatData):
            new_cell_data = np.full(output.n_cells, np.nan, dtype=float)
        elif isinstance(data, IntegerData):
            new_cell_data = np.full(output.n_cells, -1, dtype=int)
        elif isinstance(data, ReferencedData):
            new_cell_data = np.full(output.n_cells, -1, dtype=int)
        else:
            continue

        for i in range(len(interval_from)):
            start, end = interval_from[i], interval_to[i]
            mask = (cell_depth_midpoints >= start) & (cell_depth_midpoints < end)
            new_cell_data[mask] = data_values[i]

        output.cell_data[f] = new_cell_data

        if isinstance(data, ReferencedData):
            value_map = data.value_map
            names_array = np.full(output.n_cells, "N/A", dtype=object)
            valid_mask = new_cell_data != -1
            names_array[valid_mask] = value_map.map_values(new_cell_data[valid_mask])
            output.cell_data[f"{f}_names"] = names_array

    return output


def add_data_to_vtk_grid(output, entity):
    """Adds data arrays to an output VTK data object. Assigns data to cells or points
    based on number of data values compared to number of cells or points."""

    fields = [f for f in entity.get_data_list() if f not in SKIPDATA]
    #fields = [i.name for i in entity.children]
    #if "Visual Parameters" in fields:
    #    fields.remove("Visual Parameters")
    #if "UserComments" in fields:
    #    fields.remove("UserComments")
    
    for f in fields:
        data = entity.get_data(f)[0]
        values = data.values
        
        # For block models, we need to reshape to match the grid structure
        # geoh5 uses (n_u, n_v, n_z) ordering, but we need to match PyVista's cell ordering
        n_u, n_v, n_z = entity.shape
        
        # Reshape values to 3D array with proper dimensions
        # This order seems to be the inverse of what one might expect
        # but it works to get the correct orientation in PyVista when
        # combined with the transpose below
        values_3d = values.reshape((n_v, n_u, n_z), order='C')
        
        # PyVista structured grids expect cell data in a specific order
        # We need to transpose and flatten to match VTK cell ordering
        values_vtk = values_3d.transpose(1, 0, 2).flatten(order='F')
        
        if isinstance(data, ReferencedData):
            data_value_map = data.value_map
            output[f] = values_vtk
            output[f"{f}_names"] = data_value_map.map_values(output.cell_data[f])
        elif isinstance(data, FloatData):
            output[f] = values_vtk
        else:
            # Handle other data types if needed
            output[f] = values_vtk
    
    return output


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


def add_entity_metadata(output, entity):
    """Add the GA entity colour to the output VTK object."""
    colour = get_ga_entity_colour(entity)
    output.user_dict["colour"] = colour
    output.user_dict["name"] = entity.name
    output.user_dict["entity_type"] = entity.__class__.__name__
    return output


def add_data_to_geoh5(output, data):
    """Add data to the output VTK object."""
    pass


SKIPDATA = [
    'Azimuth',
    'DEPTH (Static-Survey)',
    'Dip',
    'Visual Parameters',
    'UserComments'
]
