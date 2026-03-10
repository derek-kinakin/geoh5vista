"""This module provides functions for converting geoh5py Drillhole objects to and from PyVista data objects."""


__all__ = [
    "drillholes_to_vtk",
]

__displayname__ = "Drillholes"

import numpy as np
import pyvista

from geoh5py.objects.drillhole import Drillhole
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5vista.data import add_drillhole_interval_data_to_vtk


def drillholes_to_vtk(dhgrp: DrillholeGroup) -> pyvista.MultiBlock:
    """Convert a ``geoh5py.groups.drillhole.DrillholeGroup`` to a ``pyvista.MultiBlock``.

    Each drillhole in the group is converted to a ``pyvista.PolyData`` line
    object, and the collection is returned as a ``pyvista.MultiBlock``.

    Parameters
    ----------
    dhgrp : geoh5py.groups.drillhole.DrillholeGroup
        The drillhole group to convert.

    Returns
    -------
    pyvista.Polydata
        All the drillholes as PolyData line objects.

    """
    dh_multi = pyvista.PolyData()
    for dh in dhgrp.children:
        if isinstance(dh, Drillhole) and len(dh.to_) > 0 and dh.trace_depth is not None:
            data_intervals = np.sort(
                np.unique(
                    np.concatenate([dh.to_[0].values, dh.from_[0].values, dh.trace_depth])
                )
            )
            data_intervals_locations = dh.desurvey(data_intervals)
            line = pyvista.lines_from_points(data_intervals_locations)
            line["depth"] = data_intervals
            line = add_drillhole_interval_data_to_vtk(line, dh)
            line["dh_name"] = np.repeat(dh.name, line.n_points)
            dh_multi = dh_multi.merge(line)
        elif isinstance(dh, Drillhole) and dh.trace is not None and dh.trace_depth is not None:
            line = pyvista.lines_from_points(dh.trace)
            line["depth"] = dh.trace_depth
            line["dh_name"] = np.repeat(dh.name, line.n_points)
            dh_multi = dh_multi.merge(line)

    dh_multi.field_data["gh5_name"] = dhgrp.name
    dh_multi.field_data["gh5_colour"] = "black"
    dh_multi.field_data["gh5_entity_type"] = "Drillholes"
    return dh_multi


# Now set up the display names for the docs
drillholes_to_vtk.__displayname__ = "Drillholes to VTK" # type: ignore
