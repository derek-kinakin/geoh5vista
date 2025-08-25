"""Methods to convert drillhole objects to VTK data objects"""


__all__ = [
    "drillholes_to_vtk",
]

__displayname__ = "Drillholes"

import numpy as np
import pyvista

from geoh5py.objects.drillhole import Drillhole
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.groups.drillhole import IntegratorDrillholeGroup
from geoh5vista.utilities import add_drillhole_interval_data_to_vtk

def drillholes_to_vtk(dhgrp):
    #TO DO
    print(dhgrp.name)
    dh_multi = pyvista.MultiBlock()
    for dh in dhgrp.children:
        if len(dh.to_[0].values)>0:
            data_intervals = np.sort(np.unique(np.concatenate([dh.to_[0].values, dh.from_[0].values, dh.trace_depth])))
            data_intervals_locations = dh.desurvey(data_intervals)
            line = pyvista.lines_from_points(data_intervals_locations)
            line["depth"] = data_intervals
            line = add_drillhole_interval_data_to_vtk(line, dh)
            dh_multi.append(line, name=dh.name)
        else:
            line = pyvista.lines_from_points(dh.trace)
            line["depth"] = dh.trace_depth
            dh_multi.append(line, name=dh.name)

    dh_multi.user_dict["name"] = dhgrp.name
    dh_multi.user_dict["colour"] = "black"
    dh_multi.user_dict["entity_type"] = "Drillholes"
    return dh_multi


# Now set up the display names for the docs
drillholes_to_vtk.__displayname__ = "Drillholes to VTK" # type: ignore
