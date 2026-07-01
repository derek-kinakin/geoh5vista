"""``geoh5vista``: 3D visualization and geometry processing for Geoh5 format (geoh5) objects.
"""

from importlib.metadata import PackageNotFoundError, version

from geoh5vista.blockmodel import blockmodel_to_vtk
from geoh5vista.curve import curve_to_vtk, vtk_to_curve
from geoh5vista.drillholes import drillholes_to_vtk
from geoh5vista.grid2d import grid2d_to_vtk
from geoh5vista.points import points_to_vtk, vtk_to_points
from geoh5vista.surface import surface_to_vtk, vtk_to_surface
from geoh5vista.wrapper import geoh5wrap, read_geoh5, vtkwrap, write_geoh5

# Package meta data
__author__ = "Derek Kinakin"
__license__ = "BSD-3-Clause"
__copyright__ = "2024, Derek Kinakin"
try:
    __version__ = version("geoh5vista")
except PackageNotFoundError:
    # Fallback for non-installed, source-only execution contexts.
    __version__ = "0.0.0"
__displayname__ = "GEOH5-VTK"
__name__ = "geoh5vista"


__all__ = [
    "blockmodel_to_vtk",
    "curve_to_vtk",
    "drillholes_to_vtk",
    "grid2d_to_vtk",
    "points_to_vtk",
    "surface_to_vtk",
    "vtk_to_curve",
    "vtk_to_points",
    "vtk_to_surface",
    "read_geoh5",
    "geoh5wrap",
    "write_geoh5",
    "vtkwrap"
]

