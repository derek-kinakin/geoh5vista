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
| Label        | PolyData                   | Yes             | No             | Line from label position to target position; label text in `user_dict["geoh5"]["label"]` |

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

Multi-component arrays
-------------------

geoh5 data stores one value per vertex or cell, so multi-component VTK point
and cell arrays are split on export. Three-component arrays such as `Normals`
become `<name>_x`, `<name>_y` and `<name>_z`; other widths use `<name>_0`,
`<name>_1`, and so on. Unsigned 8-bit RGB/RGBA arrays are written as native
geoh5 colour data on entities that support it (Points, Curve, Grid2D,
BlockModel); on Surfaces they are split into components like other arrays.
Split components are not recombined on import.

Geoh5 Entity Metadata Support
-------------------

`add_entity_metadata` stores metadata in `ob.user_dict["geoh5"]` using
schema version 1. The `source` dictionary contains the original UID, entity
class (`entity_type`), and parent UID. The `display` dictionary contains
`name`, `colour` (RGB integers), and `visible` (a boolean).
Visibility is the entity's own stored `Visible` attribute (the object-tree
checkbox), not effective rendered visibility. It is authoritative even when
every record in a per-view `Visible` dataset disagrees. Parent visibility is
not combined with the child's state. A missing attribute defaults to `True`,
with or without view records, matching the geoh5 format/geoh5py entity default.
Scalar Boolean/integer values are normalized (0 = hidden, nonzero = visible);
malformed stored values raise a contextual `ValueError`, not the missing-value
default. Concatenated entities use their entity-level attribute records.

The same policy applies to cataloging, direct conversion, selected entities
converted from an open workspace, and `load_only_visible` filtering. Existing
drillhole nesting is preserved: excluding a hidden drillhole group still
excludes that group from filtered file reading, even if a child's own state
is visible. Visibility resolution never rewrites source attributes or view
records. The general-purpose `normalize_visibility` utility retains its legacy
behavior, but does not define entity-level visibility.

`geoh5vista.data.restore_entity_metadata(entity, mesh, name=None)` restores
the display fields onto an already-created geoh5 entity. An explicit `name`
overrides the stored name. Missing metadata or display fields leave the
entity unchanged for those fields; invalid recognized values or unsupported
schema versions raise `ValueError` before display changes are applied.
Colour restoration creates Visual Parameters if needed and otherwise
updates the existing child's colour without replacing its other settings.
Source identity, parent relationships, and entity class are not restored.
This helper is not yet called automatically by the exporters.

Lightweight Entity Catalog
-------------------

`catalog_geoh5(path)` is a metadata-only alternative to `read_geoh5()`.
It opens an existing file read-only, closes it before returning, and returns
a `list[EntityMetadata]` of frozen, slotted dataclass records. It does not
construct geoh5py entities or import PyVista/VTK. Existing conversion functions
remain available through the same public imports.

```python
from geoh5vista import catalog_geoh5

catalog = catalog_geoh5("project.geoh5")
for entry in catalog:
    print(entry.uid, entry.name, entry.entity_type, entry.conversion_supported)
```

| Field | Meaning |
|-------|---------|
| `uid` | Canonical UUID string, consistent with converted source metadata |
| `name` | Native display name; duplicate names are preserved |
| `entity_type` | geoh5py class label for known types, including concatenated variants; stored type name for unknown types |
| `parent_uid` | Immediate native parent's UUID string, even when that parent is not cataloged |
| `visible` | Own stored entity checkbox; missing defaults to `True`, independent of views and parents |
| `colour` | Immutable RGB integer tuple, or `None` when unavailable |
| `conversion_supported` | Whether the native type is recognized and has a registered converter |
| `unsupported_reason` | Explanation for unsupported conversion, otherwise `None` |

Discovery follows the file's native `Root` hierarchy. It includes all reachable
object entities (including unsupported types and hidden objects) and
converter-supported groups such as drillhole groups. Each individual drillhole
is also listed once, with its group's UID as its parent. Ordinary organizational
groups, the workspace root, data channels, Visual Parameters children, property
groups, disconnected objects, and generated drillhole components are not entries.
Roots and organizational parents can therefore be absent from the returned list.
Ordering is deterministic depth-first traversal, with siblings sorted by canonical
UID, independent of names and converted MultiBlock ordering.

The reader accesses only hierarchy links, entity/type/display attributes,
concatenated object IDs and attribute JSON, and Visual Parameters XML (plus its
own index when concatenated). Both legacy and modern concatenated drillhole
metadata layouts are supported. Geometry, connectivity, surveys, observation
values, value maps, and computed bounds are not read. Point/cell counts are
intentionally omitted. Metadata size, especially concatenated attribute JSON
and display XML, still contributes to discovery time and memory.

Missing colours are `None`, rather than the black/white defaults used by existing
converters. Conversion support is derived from the same capability registry as
the reader; it does not validate geometry. Unknown type IDs remain discoverable
but unsupported, even if their stored type name matches a supported class.
Missing or unreadable files raise `OSError` (including `FileNotFoundError`);
malformed required hierarchy or metadata raises a contextual `ValueError`,
not an empty successful catalog. Owned handles close on success and failure.
There is no writable mode, persistent caching, or retained source handle.

This API only discovers metadata. It adds no selective conversion or loading
API and does not change `read_geoh5()` return shapes or nesting.
In particular, opening a geoh5py `Workspace` to resolve
catalog UIDs can itself read unrelated payload arrays; the catalog does not
promise payload-selective loading for subsequent operations.

Experimental Selective Reader
-------------------

`read_geoh5_entities(path, uids)` reads selected entities through geoh5py's
`H5Reader`, without opening the source as a geoh5py `Workspace`. This is a
prototype for ordinary objects, legacy drillholes, and concatenated drillholes
inside native `DrillholeGroup` containers.

```python
from geoh5vista import catalog_geoh5, read_geoh5_entities

catalog = catalog_geoh5("project.geoh5")
selected_uid = next(entry.uid for entry in catalog if entry.entity_type == "Points")
blocks = read_geoh5_entities("project.geoh5", selected_uid)
mesh = blocks[0]
```

`uids` accepts a UUID, a UUID string, or an iterable of either. The result is
always a detached PyVista `MultiBlock`, including for a single selection.
The source is opened read-only and closed before returning. Selected entities
are reconstructed with public creation APIs in an owned in-memory workspace,
then passed to the existing converters. No private-method overrides or new
global patches are used by this reader. Existing `read_geoh5()` is unchanged.

Object selection reads the object's mapped datasets and data channels, including
Visual Parameters and referenced-data type/value-map metadata. Required ancestor
identities and display attributes are reconstructed without reading ancestor or
sibling geometry. Property groups are reconstructed after their data channels.
The existing converters determine which channels appear in the output.

Selecting an organizational group includes supported descendant objects,
flattened into the result. Selecting a legacy or concatenated drillhole group
preserves its existing nested drillhole representation. Selecting an individual
hole does not read sibling holes. Root UID selection includes supported descendants.
Overlapping selections are deduplicated; output uses depth-first hierarchy
order with siblings sorted by UID, not request order. Hidden objects are included
and preserve their own stored visibility. Unsupported descendants are skipped,
but explicitly selecting an unsupported object raises `ValueError`.

For concatenated drillholes, H5Reader supplies attribute/type metadata. The
reader uses the shared indices to read only selected holes' payload slices,
compacts their offsets, and populates geoh5py's public concatenator caches.
It does not call `H5Reader.fetch_concatenated_values()`, which would read a whole
shared array. Both legacy `Attributes` JSON (geoh5 2.0) and `Attributes Jsons`
(geoh5 2.1) layouts are supported, including payloads directly under
`Concatenated Data` or in its `Data` subgroup.

Independent interval/depth tables, referenced value maps, string/Boolean
channels, Visual Parameters, source IDs, own visibility, and workspace distance
units are retained through the existing drillhole converters. Selecting a group
includes all its holes, while multiple hole UID selections read only those holes.
Missing indexed payloads produce warnings and are treated as absent, consistent
with the existing compatibility reader; missing surveys retain the converter's
vertical-default policy and provenance. Invalid slice bounds, duplicate indices,
overlap with unrelated holes, and missing required records raise errors.

Limitations:

- Concatenated storage is supported only for drillholes in `DrillholeGroup`,
  not other concatenated entity/group types.
- The reader scans reachable hierarchy metadata, including concatenated object
  ID lists. Selected concatenators' attribute JSON and index arrays are read in
  full, but only selected payload slices are requested. It is payload-selective,
  not constant-time UID lookup. HDF5 chunk decompression may touch adjacent rows
  physically; selectivity refers to logical dataset selections.
- Reconstruction and in-memory workspace finalization add allocation/copying
  overhead. No bounded peak-memory or performance guarantee is established.
- Existing converter limitations still apply; conversion errors are propagated.

Missing/unreachable UIDs, malformed UUIDs, and empty selections raise errors;
there is no fallback to eager source-workspace opening. Owned handles close on
success and failure. `drillhole_representation` and `curve_tolerance` have the
same meaning as in `read_geoh5()`.

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
