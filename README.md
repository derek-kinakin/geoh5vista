geoh5vista: a Geoh5 <> PyVista (VTK) interface
===========================================

A PyVista (and VTK) interface for the `Geoh5` file format providing Python 3D visualization and useable data structures for processing datasets in the geoh5 specification. This library allows geologists to access the powerful tools available in the PyVista ecosystem for their data stored in the `Geoh5` format.

The structure and interfaces of this project are heavily inspired by the 'omfvista' package, which provides a similar interface for the 'omf' format.

omfvista package: <https://github.com/OpenGeoVis/omfvista>

Geoh5 Python interface package: <https://mirageoscience-geoh5py.readthedocs-hosted.com/en/stable/index.html>

Documentation is hosted at <https://github.com/derek-kinakin/geoh5vista>

Installation
------------

From PyPI

```python
pip install geoh5vista
```

From Github

```python
pip install git+https://github.com/derek-kinakin/geoh5vista.git
```

Current Status of Supported Geoh5 Entities
-------------------

This table provides the list of supported entities. Read from and write
to Geoh5 support is the goal for each entity.

| Geoh5 Entity | PyVista Object             | Read from Geoh5 | Write to Geoh5 | Notes                                                         |
| -------------|----------------------------|-----------------|----------------|---------------------------------------------------------------|
| Workspace    | MultiBlock                 | Yes             | Yes            | A multiblock containing several object can be written to Geoh5|
| Points       | PointSet                   | Yes             | Yes            |                                                               |
| Curve        | PolyData                   | Yes             | Yes            |                                                               |
| Surface      | PolyData                   | Yes             | Yes            |                                                               |
| 2D Grid      | ImageData                  | Yes             | Yes            | 2D grid with dimensions nU x nV x 1                           |
| Block model  | ImageData                  | Yes             | Yes            | Uniform spacing within each axis; 3D grid with dimensions nU x nV x nZ |
| Drillholes   | PolyData                   | Yes             | No             | Drillholes can be round-tripped back to geoh5 as curves       |
| Slicer       | PolyData                   | Yes             | No             | Geometry available as object metadata                         |

Block models may use different spacing for U, V, and Z, but spacing must be
uniform within each axis. Variable-spacing block models and StructuredGrid
exports are unsupported and raise explicit errors. The earlier StructuredGrid
block-model implementation has been removed, including
`blockmodel_grid_geom_to_structured_vtk`; use `blockmodel_to_vtk` or
`blockmodel_grid_geom_to_image_vtk` for supported models.

Block-model imports preserve rotation, nonzero delimiter offsets, and
descending-axis cell-data alignment. ImageData uses the transformed first
delimiter corner as its origin, positive spacing, and signed axis directions.
The geometry helper applies no rotation when `rotation_matrix=None`;
`blockmodel_to_vtk` applies the model's rotation automatically.

Block-model exports preserve horizontal rotation, signed axis directions, and
cell-data alignment. Tilted, sheared, or scaled direction matrices are rejected.
Export normalizes delimiters to start at zero and moves their offset into the
model origin. A reversed U axis is represented by an equivalent rotation and
signed V spacing, so geometry and data are preserved, but the original origin,
delimiter offsets, and rotation representation may differ after a round trip.

Geoh5 Entity Metadata Support
-------------------

The following metadata are read from the geoh5 entities and attached to the PyVista objects in the "user_dict":

* Entity name (ob.user_dict["gh5_name"]) as a string
* Entity colour (ob.user_dict["gh5_colour"]) as a list [R,G,B]
* Entity type (ob.user_dict["gh5_entity_type"]) as "Points", "Curve", "Surface", "Grid2D", "Grid3D", or "Drillhole"
* Entity visibility (ob.user_dict["gh5_visible"]) as True/False. Integer/NumPy visibility values from geoh5py are normalized (0 = hidden); unrecognized values are treated as visible with a warning.

Example Use
-----------

```python
import pyvista as pv
import geoh5vista

project = geoh5vista.read_geoh5('test_file.geoh5')
project
```

Once the data is loaded as a ``pyvista.MultiBlock`` dataset from ``geoh5vista``,
that object can be directly used for interactive 3D visualization from PyVista:

An interactive scene can be created and manipulated to create a figure.
First, grab the elements from the project:

```python
# Grab a few elements of interest and plot em up!
vol = project["Block Model"]
topo = project["Topography"]
dacite = project["Dacite"]
```

Then create a 3D scene with these spatial data and apply a filtering tool from
PyVista to the volumetric data:

```python
# Create a plotting window
p = pv.Plotter(notebook=False)
# Add our datasets
p.add_mesh(topo, cmap="gist_earth", opacity=0.5)
p.add_mesh(dacite, color=dacite.user_dict["gh5_colour"], opacity=0.6)
# Add the volumetric dataset with a thresholding tool
p.add_mesh_threshold(vol)
# Add the bounds axis
p.show_bounds()
# Render the scene in a pop out window
p.show()
```

Writing PyVista objects to a Geoh5 file can be as simple as:

```python

# Write a single object to geoh5
geoh5vista.write_geoh5(topo, "new_gh5_topo_file.geoh5")

# Write a multiblock to geoh5
new_project = pv.MultiBlock()
new_project["Topo"] = topo
new_project["Dacite"] = dacite

geoh5vista.write_geoh5(new_project, "new_project.geoh5")
```
