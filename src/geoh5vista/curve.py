"""This module provides functions for converting geoh5py Curve objects to and from PyVista data objects."""


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
from geoh5vista.data import add_data_to_vtk, add_entity_metadata


def curve_geom_to_vtk(crv: Curve) -> pyvista.PolyData:
    """Convert the curve geometry to a ``pyvista.PolyData`` object.

    Parameters
    ----------
    crv : geoh5py.objects.curve.Curve
        The curve to convert.

    Returns
    -------
    pyvista.PolyData
        The curve geometry as a PolyData object.

    """
    ids = crv.cells
    lines = np.c_[np.full(len(ids), 2, dtype=np.int_), ids]

    output = pyvista.PolyData()
    output.points = crv.vertices
    output.lines = lines

    indices = output.connectivity().cell_data["RegionId"]
    output["Line Index"] = indices

    return output


def curve_to_vtk(crv: Curve) -> pyvista.PolyData:
    """Convert a ``geoh5py.objects.curve.Curve`` to a ``pyvista.PolyData`` object.

    This function converts the curve geometry and transfers all associated data.

    Parameters
    ----------
    crv : geoh5py.objects.curve.Curve
        The curve to convert.

    Returns
    -------
    pyvista.PolyData
        The converted curve.

    """
   
    # Now add data to lines:
    output = curve_geom_to_vtk(crv)
    output = add_data_to_vtk(output, crv)
    output = add_entity_metadata(output, crv)

    return output


def vtk_geom_to_curve(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Curve:
    """Convert a ``pyvista.PolyData`` object to a ``geoh5py.objects.curve.Curve`` object.

    Parameters
    ----------
    vtk : pyvista.PolyData
        The VTK object to convert. It must have lines.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new curve to.
    name : str
        The name of the new curve.

    Returns
    -------
    geoh5py.objects.curve.Curve
        The newly created curve.

    Raises
    ------
    ValueError
        If the VTK object is not a PolyData object with lines.

    """

    points = vtk.points
    if isinstance(vtk, pyvista.PolyData) and vtk.lines is not None:
        lines = vtk.lines.reshape(-1, 3)[:, 1:]
    else:
        raise ValueError("VTK object should be a PolyData object with lines.")

    curve = Curve.create(workspace=workspace, name=name, vertices=points, cells=lines)
    return curve


def vtk_to_curve(vtk: pyvista.PolyData, workspace: Workspace, name: str) -> Curve:
    """Convert a ``pyvista.PolyData`` object to a ``geoh5py.objects.curve.Curve`` object.

    This is a wrapper for ``vtk_geom_to_curve`` and is intended to be the
    main entry point for this conversion. In the future, it will also handle
    transferring data from the VTK object to the geoh5py object.

    Parameters
    ----------
    vtk : pyvista.PolyData
        The VTK object to convert.
    workspace : geoh5py.workspace.Workspace
        The geoh5py workspace to add the new curve to.
    name : str
        The name of the new curve.

    Returns
    -------
    geoh5py.objects.curve.Curve
        The newly created curve.

    """
    curve = vtk_geom_to_curve(vtk=vtk, workspace=workspace, name=name)
    return curve


curve_geom_to_vtk.__displayname__ = "Curve to VTK" # type: ignore
curve_to_vtk.__displayname__ = "Curve to VTK" # type: ignore
vtk_geom_to_curve.__displayname__ = "VTK Geometry to Curve" # type: ignore
vtk_to_curve.__displayname__ = "VTK to Curve" # type: ignore
