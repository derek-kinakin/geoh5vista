"""
Load Project
------------

Load and visualize an GEOH5 project file
"""

import sys
import pyvista as pv
from pathlib import Path

path_root = Path(__file__).parents[1]
sys.path.append(str(path_root))

import geoh5vista

###############################################################################
# Load the project into an :class:`pyvista.MultiBlock` dataset

project = geoh5vista.load_project(f"{path_root}\\assets\\test_1_file.geoh5")
print(project)

###############################################################################
# Once the data is loaded as a :class:`pyvista.MultiBlock` dataset from
# ``geoh5vista``, then that object can be directly used for interactive 3D
# visualization from ``pyvista``:

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

###############################################################################

assay.set_active_scalars("DENSITY")

p = pv.Plotter()
p.add_mesh(assay.tube(radius=3))
p.add_mesh(topo, opacity=0.5)
p.show()

###############################################################################
# Then apply a filtering tool from ``pyvista`` to the volumetric data:

# Threshold the volumetric data
thresh_vol = vol.threshold([1.09, 4.20])
print(thresh_vol)

###############################################################################
# Then you can put it all in one environment!

# Create a plotting window
p = pv.Plotter()
# Add the bounds axis
p.show_bounds()
p.add_bounding_box()

# Add our datasets
p.add_mesh(topo, opacity=0.5)
p.add_mesh(
    dacite,
    color="orange",
    opacity=0.6,
)
p.add_mesh(thresh_vol, cmap="coolwarm", clim=vol.get_data_range())

# Add the assay logs: use a tube filter that varius the radius by an attribute
p.add_mesh(assay.tube(radius=3), cmap="viridis")

#p.export_html("geoh5vista.html")
p.show()
