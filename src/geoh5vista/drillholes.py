"""Methods to convert drillhole objects to VTK data objects"""


__all__ = [
    "drillhole_to_vtk",
]

__displayname__ = "Drillholes"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data_to_vtk

def drillholes_to_vtk(dh, origin=(0.0, 0.0, 0.0)):
    #TO DO
    pass

# Now set up the display names for the docs
drillholes_to_vtk.__displayname__ = "Drillholes to VTK"
