"""Methods for converting volumetric data objects"""

__all__ = [
    "octree_grid_geom_to_vtk",
    "octree_to_vtk",
]

__displayname__ = "Octree"

import numpy as np
import pyvista

from geoh5vista.utilities import check_orientation


def octree_grid_geom_to_vtk(gi, origin=(0.0, 0.0, 0.0)):
    pass

def octree_to_vtk(gi, origin=(0.0, 0.0, 0.0)):
    pass

# Now set up the display names for the docs
octree_grid_geom_to_vtk.__displayname__ = "Octree Geometry to VTK" # type: ignore
octree_to_vtk.__displayname__ = "Octree to VTK" # type: ignore
