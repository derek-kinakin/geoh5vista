geoh5vista: a Geoh5 <> PyVista (VTK) interface
===========================================

A PyVista (and VTK) interface for the `Geoh5 package` (``geoh5``)
providing Python 3D visualization and useable mesh data structures for
processing datasets in the geoh5 specification.

The structure and interfaces of this project are heavily inspired by (and borrowed from) the 'omfvista' package, which provides a similar interface for the 'omf' format.

omfvista package: https://github.com/OpenGeoVis/omfvista

Geoh5 Format package: https://mirageoscience-geoh5py.readthedocs-hosted.com/en/stable/index.html

Documentation is hosted at https://github.com/derek-kinakin/geoh5vista


Installation
------------
```python
pip install git+https://github.com/derek-kinakin/geoh5vista.git
```

Current Status
-------------------

| Geoh5 Entity | PyVista Object | Read from Geoh5 | Write to Geoh5 | Notes |
| -------------|----------------|-----------------|----------------|-------|
| Points       | PointSet       | Yes             | No             |       |
| Curve        | PolyData       | Yes             | No             |       |
| Surface      | PolyData       | Yes             | No             |       |
| Block model  | StructuredGrid | Yes             | No             |       |
| Drillholes   | TBD            | No              | No             |       |
| 2D Grid      | ImageData      | Yes             | No             |       |
| GeoImage     | TBD            | No              | No             |       |
| Octree Grid  | TBD            | No              | No             |       |

Example Use
-----------

```python
import pyvista as pv
import geoh5vista

project = geoh5vista.load_project('test_file.geoh5')
project
```

Once the data is loaded as a ``pyvista.MultiBlock`` dataset from ``geoh5vista``, then
that object can be directly used for interactive 3D visualization from PyVista_:

An interactive scene can be created and manipulated to create a compelling
figure. First, grab the elements from the project:

```python
# Grab a few elements of interest and plot em up!
vol = project['Block Model']
assay = project['wolfpass_WP_assay']
topo = project['Topography']
dacite = project['Dacite']
```

Then create a 3D scene with these spatial data and apply a filtering tool from
PyVista_ to the volumetric data:

```python
# Create a plotting window
p = pv.Plotter(notebook=False)
# Add our datasets
p.add_mesh(topo, cmap='gist_earth', opacity=0.5)
p.add_mesh(assay, color='blue', line_width=3)
p.add_mesh(dacite, color=dacite.user_dict["colour"], opacity=0.6)
# Add the volumetric dataset with a thresholding tool
p.add_mesh_threshold(vol)
# Add the bounds axis
p.show_bounds()
# Render the scene in a pop out window
p.show()
```
