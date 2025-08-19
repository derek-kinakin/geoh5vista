"""Methods to convert curve objects to VTK data objects"""


__all__ = [
    "curve_to_vtk",
    "curve_geom_to_vtk",
    "vtk_geom_to_curve",
    "vtk_to_curve"
]

__displayname__ = "Curve"

import numpy as np
import pyvista
from geoh5py.objects.curve import Curve
from geoh5py.workspace.workspace import Workspace
from geoh5vista.utilities import add_data_to_vtk, add_entity_metadata


def curve_geom_to_vtk(crv, origin=(0.0, 0.0, 0.0)):
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

    output.points += np.array(origin)
    return output


def curve_to_vtk(crv, origin=(0.0, 0.0, 0.0)):
    """Convert the curve to a :class:`pyvista.PolyData` data object.

    Args:
        crv (:class:`geoh5py.objects.curve.Curve`): The curve to convert

    Return:
        :class:`pyvista.PolyData`
    """
   
    # Now add data to lines:
    output = curve_geom_to_vtk(crv, origin=origin)
    output = add_data_to_vtk(output, crv)
    output = add_entity_metadata(output, crv)

    return output


def vtk_geom_to_curve(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Curve:
    """Convert a VTK object to a geoh5py Curve object."""
    if name:
        name = name
    else:
        name = vtk.user_dict["name"]

    curve = Curve.create(workspace=workspace, vertices=vtk.points, name=name)
    return curve


def vtk_to_curve(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Curve:
    """Convert a VTK object to a geoh5py Curve object."""
    curve = vtk_geom_to_curve(vtk=vtk, workspace=workspace, name=name)
    return curve


curve_geom_to_vtk.__displayname__ = "Curve to VTK" # type: ignore
curve_to_vtk.__displayname__ = "Curve to VTK" # type: ignore
vtk_geom_to_curve.__displayname__ = "VTK Geometry to Curve" # type: ignore
vtk_to_curve.__displayname__ = "VTK to Curve" # type: ignore
