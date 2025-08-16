"""Methods to convert curve objects to VTK data objects"""


__all__ = [
    "curve_to_vtk",
]

__displayname__ = "Curve"

import numpy as np
import pyvista

from geoh5vista.utilities import add_data_to_vtk


def curve_to_vtk(crv, origin=(0.0, 0.0, 0.0)):
    """Convert the curve to a :class:`pyvista.PolyData` data object.

    Args:
        crv (:class:`geoh5py.objects.curve.Curve`): The curve to convert

    Return:
        :class:`pyvista.PolyData`
    """
    ids = crv.cells
    lines = np.c_[np.full(len(ids), 2, dtype=np.int_), ids]

    output = pyvista.PolyData()
    output.points = crv.vertices
    output.lines = lines

    indices = output.connectivity().cell_data["RegionId"]
    output["Line Index"] = indices

    # Now add data to lines:
    add_data_to_vtk(output, crv)

    output.points += np.array(origin)
    return output


curve_to_vtk.__displayname__ = "Curve to VTK"
