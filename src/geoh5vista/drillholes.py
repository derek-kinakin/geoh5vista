"""This module provides functions for converting geoh5py Drillhole objects to and from PyVista data objects."""

from __future__ import annotations

from typing import Final

import numpy as np
import pyvista
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.objects.drillhole import Drillhole

from geoh5vista.data import add_drillhole_interval_data_to_vtk

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "drillholes_to_vtk"
)


MODULE_DISPLAY_NAME: Final[str] = "Drillholes"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "drillholes_to_vtk": "Drillholes to VTK",
}


def drillholes_to_vtk(dhgrp: DrillholeGroup) -> pyvista.PolyData:
    """Convert a ``geoh5py.groups.drillhole.DrillholeGroup`` to a ``pyvista.PolyData``.

    Each drillhole in the group is converted to a ``pyvista.PolyData`` line
    object, and the collection is returned as a ``pyvista.PolyData``.

    Parameters
    ----------
    dhgrp : geoh5py.groups.drillhole.DrillholeGroup
        The drillhole group to convert.

    Returns
    -------
    pyvista.PolyData
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
            dh_multi += line
        elif isinstance(dh, Drillhole) and dh.trace is not None and dh.trace_depth is not None:
            line = pyvista.lines_from_points(dh.trace)
            line["depth"] = dh.trace_depth
            line["dh_name"] = np.repeat(dh.name, line.n_points)
            dh_multi += line

    dh_multi.user_dict["geoh5"] = {
        "schema_version": 1,
        "source": {
            "uid": str(dhgrp.uid),
            "entity_type": "Drillholes",
            "parent_uid": str(dhgrp.parent.uid) if dhgrp.parent else None,
        },
        "display": {
            "name": dhgrp.name,
            "colour": [255, 255, 255],
            "visible": True,
        },
    }
    
    return dh_multi
