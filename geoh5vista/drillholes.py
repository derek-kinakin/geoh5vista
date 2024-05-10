"""Methods to convert drillhole objects to VTK data objects"""


__all__ = [
    "drillhole_to_vtk",
]

__displayname__ = "Drillholes"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data

#TO DO
