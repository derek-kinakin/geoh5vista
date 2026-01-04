geoh5vista: a Geoh5 <> PyVista (VTK) interface
===========================================

A PyVista (and VTK) interface for the `Geoh5` file format providing Python 3D visualization and useable mesh data structures for processing datasets in the geoh5 specification.

The structure and interfaces of this project are heavily inspired by (and borrowed from) the 'omfvista' package, which provides a similar interface for the 'omf' format.

omfvista package: <https://github.com/OpenGeoVis/omfvista>

Geoh5 Python interface package: <https://mirageoscience-geoh5py.readthedocs-hosted.com/en/stable/index.html>

Documentation is hosted at <https://github.com/derek-kinakin/geoh5vista>

Installation
------------

```python
pip install git+https://github.com/derek-kinakin/geoh5vista.git
```

Current Status of Supported Geoh5 Entities
-------------------

| Geoh5 Entity | PyVista Object | Read from Geoh5 | Write to Geoh5 | Notes                                 |
| -------------|----------------|-----------------|----------------|---------------------------------------|
| Workspace    | MultiBlock     | Yes             | Yes            | A multiblock can be written to Geoh5  |
| Points       | PointSet       | Yes             | Yes            |                                       |
| Curve        | PolyData       | Yes             | Yes            |                                       |
| Surface      | PolyData       | Yes             | Yes            |                                       |
| 2D Grid      | ImageData      | Yes             | Yes            | 2D grid with dimensions nU x nV x 1   |
| Block model  | ImageData      | Yes             | No             | 3D grid with dimensions nU x nV x nZ  |
| Drillholes   | MultiBlock     | Yes             | No             |                                       |
| Slicer       | PolyData       | Yes             | No             | Geometry available as object metadata |

This table provides the list of supported entities. Read from and write
to Geoh5 support is the goal for each entity.

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
p.add_mesh(dacite, color=dacite["gh5_colour"], opacity=0.6)
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
new_project = pv.Multiblock()
new_project["Topo"] = topo
new_project["Dactite"] = dacite

geoh5vista.write_geoh5(new_project, "new_project.geoh5")
```
