"""Methods for converting volumetric data objects"""

__all__ = [
    "geoimage_to_vtk",
]

__displayname__ = "GeoImage"

import numpy as np
import pyvista

from geoh5vista.utilities import check_orientation


def geoimage_to_vtk(gi, origin=(0.0, 0.0, 0.0)):
    return print("GeoImages not yet implemented by geoh5py")

# Now set up the display names for the docs
geoimage_to_vtk.__displayname__ = "GeoImage to VTK" # type: ignore
