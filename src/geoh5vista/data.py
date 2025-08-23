"""Methods to convert points objects to VTK data objects"""


__all__ = [
    "data_to_vtk",
]

__displayname__ = "Data"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data_to_vtk, add_texture_coordinates


def text_data_to_vtk(pts, origin=(0.0, 0.0, 0.0)):
    pass


def float_data_to_vtk(pts, origin=(0.0, 0.0, 0.0)):
    pass

def referenced_data_to_vtk(pts, origin=(0.0, 0.0, 0.0)):
    pass

def integer_data_to_vtk(pts, origin=(0.0, 0.0, 0.0)):
    pass

def filename_data_to_vtk(pts, origin=(0.0, 0.0, 0.0)):
    pass

text_data_to_vtk.__displayname__ = "Text Data to VTK"  # type: ignore
float_data_to_vtk.__displayname__ = "Float Data to VTK"  # type: ignore
referenced_data_to_vtk.__displayname__ = "Referenced Data to VTK"  # type: ignore
integer_data_to_vtk.__displayname__ = "Integer Data to VTK"  # type: ignore
filename_data_to_vtk.__displayname__ = "Filename Data to VTK"  # type: ignore
