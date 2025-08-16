"""``geoh5vista``: 3D visualization for the Geoh5 format (geoh5)
"""

from geoh5vista.curve import curve_to_vtk
from geoh5vista.points import points_to_vtk
from geoh5vista.surface import surface_geom_to_vtk, surface_to_vtk
from geoh5vista.utilities import (
    add_data_to_vtk,
    add_data_to_vtk_grid,
    add_texture_coordinates,
    check_orientation,
    check_orthogonal,
    texture_to_vtk,
)
from geoh5vista.blockmodel import blockmodel_grid_geom_to_vtk, blockmodel_to_vtk
from geoh5vista.wrapper import load_project, project_to_vtk, wrap

# Package meta data
__author__ = "Derek Kinakin"
__license__ = "BSD-3-Clause"
__copyright__ = "2024, Derek Kinakin"
__version__ = "0.0.1"
__displayname__ = "GEOH5-VTK"
__name__ = "geoh5vista"


def ignore_warnings():
    """Sets a warning filter for pillow's annoying ``DecompressionBombWarning``"""
    import warnings

    from PIL import Image

    warnings.simplefilter(action="ignore", category=Image.DecompressionBombWarning)


ignore_warnings()
