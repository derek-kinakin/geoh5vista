"""``geoh5vista``: 3D visualization for the Geoh5 format (geoh5)
"""

from geoh5vista.wrapper import read_workspace, entities_to_vtk

# Package meta data
__author__ = "Derek Kinakin"
__license__ = "BSD-3-Clause"
__copyright__ = "2024, Derek Kinakin"
__version__ = "0.0.5"
__displayname__ = "GEOH5-VTK"
__name__ = "geoh5vista"


def ignore_warnings():
    """Sets a warning filter for pillow's annoying ``DecompressionBombWarning``"""
    import warnings
    from PIL import Image
    warnings.simplefilter(action="ignore", category=Image.DecompressionBombWarning)

ignore_warnings()
