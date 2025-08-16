"""
This example demonstrates how to load and visualize an entities from a geoh5 file.

Example geoh5 files are available in the `assets` directory.

"""

import geoh5vista
import pyvista as pv

from pathlib import Path

path_root = Path(__file__).parents[1]
project_path = path_root / "assets" / "test_1_file.geoh5"

###############################################################################
# Load the project into an :class:`pyvista.MultiBlock` dataset
project = geoh5vista.load_project(project_path)

###############################################################################
# Once the data is loaded as a :class:`pyvista.MultiBlock` dataset from
# ``geoh5vista``, then that object can be directly used for interactive 3D
# visualization from ``pyvista``:
project.plot(multi_colors=True)

###############################################################################
# Or an interactive scene can be created and manipulated to create a compelling
# figure. First, grab the entities from the project:
vol = project["Block Model"]
assay = project["wolfpass_WP_assay"]
topo = project["Topography"]
dacite = project["Dacite"]
diorite = project["Early Diorite"]

assay.set_active_scalars("DENSITY")

# Then apply a filtering tool from ``pyvista`` to the volumetric data:
# Threshold the volumetric data
thresh_vol = vol.threshold([1.09, 4.20])
print(thresh_vol)

###############################################################################
# Then you can put it all in one environment!

# Create a plotting window
p = pv.Plotter()

# Add our datasets
p.add_mesh(
    topo,
    color=topo.user_dict["colour"],
    opacity=0.5,
    label=topo.user_dict["name"],
)

p.add_mesh(
    dacite,
    color=dacite.user_dict["colour"],
    opacity=0.6,
    label=dacite.user_dict["name"],
)

p.add_mesh(
    diorite,
    color=diorite.user_dict["colour"],
    opacity=0.6,
    label=diorite.user_dict["name"],
)

p.add_mesh_threshold(
    thresh_vol,
    cmap="coolwarm",
    pointa=(0.05, 0.9),
    pointb=(0.4, 0.9),
)

# Add the assay logs: use a tube filter that varius the radius by an attribute
p.add_mesh(
    assay.tube(radius=3),
    cmap="viridis",
    label="assay",
)

# Plotter settings
p.set_viewup([0, 1, 0])
p.add_axes()
p.add_legend(size=(0.1, 0.1))
p.enable_parallel_projection()
p.show()
