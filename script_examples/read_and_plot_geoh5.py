"""Example script that reads a geoh5 workspace and visualizes its contents using geoh5vista and PyVista.

This example is based on the "GeoscienceANALYST_ProGeology_demo.geoh5" workspace that is provided when
downloading the Geoscience Analyst software.

"""

import pyvista as pv

import geoh5vista

GEOH5FILE = r"C:\Users\dkinakin\Downloads\GeoscienceANALYST\Geoscience_ANALYST_demo_workspace_and_data\GeoscienceANALYST_ProGeology_demo.geoh5"
print(geoh5vista.__version__)

project = geoh5vista.read_geoh5(GEOH5FILE)

geology = [
    "Mississippi",
    "Hidden",
    "Millrock",
    "F1",
    "Louis",
    "BlueLagoon",
    ]

data = [
    "observations",
    "surface samples",
    ]

drillholes = [
    "Drillholes",
    "Drillholes_descriptions"
    ]

topography = ["DEM"]
block_models = ["Geology model"]


p = pv.Plotter()
for item in topography:
    mesh = project[item]
    p.add_mesh(mesh, cmap="terrain")

for item in geology:
    mesh = project[item]
    p.add_mesh(mesh, color=mesh.user_dict["gh5_colour"], label=mesh.user_dict["gh5_name"], opacity=1)

for item in data:
    mesh = project[item]
    p.add_mesh(mesh, color=mesh.user_dict["gh5_colour"], label=mesh.user_dict["gh5_name"])

for item in drillholes:
    mesh = project[item]
    p.add_mesh(mesh, line_width=3, color="black")

blkmdl = project[block_models[0]]
ore_blocks = blkmdl.extract_cells(blkmdl.cell_data["geomodel"] == 14)
p.add_mesh(ore_blocks, color="red", opacity=1, label="ore_zone_refined")

p.add_legend()
p.show()
