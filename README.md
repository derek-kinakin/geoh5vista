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
| Block model  | ImageData / StructuredGrid | Yes             | Yes            | ImageData for uniform spacing within each axis; StructuredGrid for variable spacing |
| Drillholes   | Nested MultiBlock          | Yes             | No             | Independent collars, traces, and sampling tables; optional merged PolyData view |
| Slicer       | PolyData                   | Yes             | No             | Geometry available as object metadata                         |

Block models with uniform spacing within each axis are read as `ImageData`;
U, V, and Z spacing may differ from each other. Models with variable spacing
within any axis are read as `StructuredGrid` with explicit, rotated point
coordinates. Use `blockmodel_to_vtk` to select the representation
automatically, or `blockmodel_grid_geom_to_image_vtk` /
`blockmodel_grid_geom_to_structured_vtk` for geometry only.

StructuredGrid block models support common dataset attributes and filters such
as `cell_data`, `user_dict`, `bounds`, slicing, clipping, thresholding,
contouring, cell centres, and structured subsets. ImageData-only attributes and
filters, such as `spacing`, `origin`, `direction_matrix`, image smoothing,
FFT, and morphology, are not available. For positive cell volumes, descending
delimiter axes are reversed in StructuredGrid index order; cell data are
reordered to remain spatially aligned.

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

StructuredGrid exports infer rotation and delimiters from the current point
coordinates. Points must form an orthogonal rectilinear lattice with horizontal
U/V axes and a vertical Z axis; tilted, sheared, warped, or degenerate grids are
rejected. The first grid node becomes the model origin.

Geoh5 Entity Metadata Support
-------------------

`add_entity_metadata` stores metadata in `ob.user_dict["geoh5"]` using
schema version 1. The `source` dictionary contains the original UID, entity
class (`entity_type`), and parent UID. The `display` dictionary contains
`name`, `colour` (RGB integers), and `visible` (a boolean).
Integer/NumPy visibility values from geoh5py are normalized (0 = hidden);
unrecognized values are treated as visible with a warning.

`geoh5vista.data.restore_entity_metadata(entity, mesh, name=None)` restores
the display fields onto an already-created geoh5 entity. An explicit `name`
overrides the stored name. Missing metadata or display fields leave the
entity unchanged for those fields; invalid recognized values or unsupported
schema versions raise `ValueError` before display changes are applied.
Colour restoration creates Visual Parameters if needed and otherwise
updates the existing child's colour without replacing its other settings.
Source identity, parent relationships, and entity class are not restored.
This helper is not yet called automatically by the exporters.

Drillhole Representation
-------------------

Drillhole imports now return nested `MultiBlock` objects instead of a single
merged `PolyData`. `geoh5wrap(hole)` or
`geoh5vista.drillholes.drillhole_to_vtk(hole)` converts one hole;
`drillholes_to_vtk(group)` converts a group. Modern concatenated drillholes and
legacy drillholes are supported. Workspace loading includes each hole once,
inside its drillhole group, and applies `load_only_visible` to both groups and
individual holes.

Each hole has four named components:

| Component | Representation | Arrays |
|-----------|----------------|--------|
| `collar` | One-vertex PolyData | Scalar object-associated observations as point arrays; longer object arrays in field data |
| `trace` | Connected two-point line cells | Measured `depth` on points; segment `from` and `to` on cells |
| `intervals` | MultiBlock of sampling tables | One polyline cell per source interval, with observations, `from`, `to`, and `source_row` on cells |
| `points` | MultiBlock of sampling tables | Vertex cells at observation depths, with observations, `depth`, and `source_row` on points |

Arrays sharing a modern property group share a dataset; different sampling
tables remain independent. Legacy arrays retain their shared cell/depth
alignment. Gaps are not bridged in interval tables, overlapping intervals
remain separate cells, and repeated point depths remain separate observations.
Point observations are never interpolated onto the trace automatically.

Geometry is generated from collar and surveys through geoh5py desurveying;
a stored trace is not required and elevation differences are not used as
measured depth. Curved interval cells include intermediate vertices. The
default `curve_tolerance=0.01` bounds circular-arc chord error in workspace
distance units, with depth steps also limited to 5 units. This is an
approximation tolerance relative to geoh5py's desurveyed path, not a measure of
survey accuracy. Survey/desurvey boundaries are always included.

A missing or zero end-of-hole depth is treated as unspecified (geoh5py may
normalize missing depths to zero); the extent is then inferred from sampling
and survey depths. Without a positive extent the result is collar-only, with
an empty trace. Missing surveys use geoh5py's default vertical direction with
a warning when a path is generated. Negative/non-finite depths and sampling
beyond an explicit positive end of hole are rejected. Reversed and zero-length
intervals (`from >= to`) are omitted with a warning identifying the hole,
table, and zero-based source rows. Remaining arrays keep their original
`source_row` IDs; omitted row IDs and bounds are retained in the table's
`user_dict["geoh5"]["drillhole"]["omitted_intervals"]`. No bounds are guessed
or repaired, and the source workspace is unchanged.

The existing `user_dict["geoh5"]` source/display metadata is preserved per
hole and per leaf dataset. Additional `drillhole` metadata records component
roles, sampling-table identity, original surveys, survey/extent provenance,
hole attributes, workspace distance units, and the geometry tolerance.
The `arrays` dictionary records source array UIDs, names, types, associations,
and referenced-value maps. Numeric, Boolean, referenced, and text arrays are
preserved, with companion validity arrays named `<array>__valid` and referenced
labels named `<array>_names`. Boolean `False` is valid; native numeric/text
no-data values are distinguished using validity arrays. Duplicate names and
collisions with geometry-array names are disambiguated; metadata retains the
original names and UIDs.
Modern data without a resolvable sampling table are rejected rather than
silently omitted. Cached legacy arrays that are shorter than their extended
shared geometry are padded using geoh5py's native no-data conventions.
PyVista/VTK rejects non-ASCII string arrays; non-ASCII text values and
referenced labels therefore raise an explicit error rather than being
transliterated or discarded. JSON source/display metadata can retain Unicode.

```python
import pyvista as pv
import geoh5vista
from geoh5vista.drillholes import save_drillholes, read_drillholes

project = geoh5vista.read_geoh5("project.geoh5")
hole = project["Drillholes"]["DH-001"]
assays = hole["intervals"][0]

plotter = pv.Plotter()
plotter.add_mesh(hole["trace"], color="black")
plotter.add_mesh(assays, scalars="Au", preference="cell", line_width=5)
plotter.add_mesh(hole["collar"], color="red", point_size=10)
plotter.show()

save_drillholes(project["Drillholes"], "drillholes.vtm")
restored = read_drillholes("drillholes.vtm")
```

Use `save_drillholes` / `read_drillholes` for VTM persistence: ordinary
`MultiBlock.save` loses nested container metadata. These helpers pack metadata
into a root registry without modifying the input and restore it on loading.
They also support a containing workspace MultiBlock. Extra nested container
field arrays are rejected rather than silently discarded; leaf field arrays
are preserved, including Boolean dtypes that VTK otherwise stores as integers.

For a common-line visualization, use
`drillhole_to_vtk(hole, representation="merged")`,
`drillholes_to_vtk(group, representation="merged")`, or
`read_geoh5(path, drillhole_representation="merged")`. This view splits at all
sampling boundaries, maps interval values to line cells, and places point
values only at exact observation depths. Validity arrays distinguish gaps
from valid zero/False values, and point/cell `dh_uid` arrays retain hole
identity, even for coincident holes. Overlapping valid observations in one
array or incompatible array definitions across holes raise an error: use
the composite representation instead.
Fields sharing a sampling table reuse the same row mapping. Missing observations
do not overwrite valid overlapping observations; referenced labels follow the
same validity mask as their codes and remain empty where no valid value is mapped.

Composite export to geoh5 drillholes is not implemented and is explicitly
rejected. An explicit merged view may be exported as ordinary curves, not as
a faithful drillhole round trip.

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
