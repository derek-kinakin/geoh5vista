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


def curve_geom_to_vtk(crv):
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

    return output


def curve_to_vtk(crv):
    """Convert the curve to a :class:`pyvista.PolyData` data object.

    Args:
        crv (:class:`geoh5py.objects.curve.Curve`): The curve to convert

    Return:
        :class:`pyvista.PolyData`
    """
   
    # Now add data to lines:
    output = curve_geom_to_vtk(crv)
    output = add_data_to_vtk(output, crv)
    output = add_entity_metadata(output, crv)

    return output


def vtk_geom_to_curve(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Curve:
    """Convert a VTK object to a geoh5py Curve object."""

    points = vtk.points
    if isinstance(vtk, pyvista.PolyData) and vtk.lines is not None:
        lines = vtk.lines.reshape(-1, 3)[:, 1:]
    else:
        raise ValueError("VTK object should be a PolyData object with lines.")

    curve = Curve.create(workspace=workspace, name=name, vertices=points, cells=lines)
    return curve


def vtk_to_curve(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Curve:
    """Convert a VTK object to a geoh5py Curve object."""
    curve = vtk_geom_to_curve(vtk=vtk, workspace=workspace, name=name)
    return curve


curve_geom_to_vtk.__displayname__ = "Curve to VTK" # type: ignore
curve_to_vtk.__displayname__ = "Curve to VTK" # type: ignore
vtk_geom_to_curve.__displayname__ = "VTK Geometry to Curve" # type: ignore
vtk_to_curve.__displayname__ = "VTK to Curve" # type: ignore
