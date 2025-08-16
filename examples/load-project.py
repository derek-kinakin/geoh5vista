"""
Load Project
------------

Load and visualize an GEOH5 project file
"""

import geoh5vista
import pyvista as pv

from pathlib import Path

path_root = Path(__file__).parents[1]
project_path = path_root / "assets" / "test_1_file.geoh5"
###############################################################################
# Load the project into an :class:`pyvista.MultiBlock` dataset

project = geoh5vista.load_project(project_path)
print(project)

###############################################################################
# Once the data is loaded as a :class:`pyvista.MultiBlock` dataset from
# ``geoh5vista``, then that object can be directly used for interactive 3D
# visualization from ``pyvista``:
print(type(project))
project.plot()

###############################################################################
# Or an interactive scene can be created and manipulated to create a compelling
# figure directly in a Jupyter notebook. First, grab the elements from the
# project:

# Grab a few elements of interest and plot em up!
vol = project["Block Model"]
assay = project["wolfpass_WP_assay"]
topo = project["Topography"]
dacite = project["Dacite"]
diorite = project["Early Diorite"]

###############################################################################

assay.set_active_scalars("DENSITY")

# Then apply a filtering tool from ``pyvista`` to the volumetric data:
# Threshold the volumetric data
thresh_vol = vol.threshold([1.09, 4.20])
print(thresh_vol)

###############################################################################
# Then you can put it all in one environment!

# Create a plotting window
p = pv.Plotter()
# Add the bounds axis
# p.show_bounds()
# p.add_bounding_box()

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

#p.add_mesh(
#    thresh_vol,
#    cmap="coolwarm",
#    )

p.add_mesh_threshold(
    thresh_vol,
    cmap="coolwarm", pointa=(0.05, 0.9), pointb=(0.4, 0.9),
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
#p.enable_parallel_projection()
#p.export_html("geoh5vista_example.html")
p.show()
