# Release notes

## 0.11.0 - 2026-11-02

- Support workspaces without a stored `/Root` link by resolving an indexed
  `RootGroup` when available or discovering a hierarchy forest from flat
  `Groups` and `Objects` indexes. Cataloging, selective reading, and full
  workspace conversion now share hierarchy membership and preserve source
  parent metadata for rootless entities.
- Default `read_geoh5()` to read-only mode.

## 0.10.0 - 2026-11-02

- Fixed Grid2D import of geoh5py's structured origin and corrected its geometry
  to native cell boundaries: ImageData point dimensions are now
  `(u_count + 1, v_count + 1, 1)`, and native values are cell data rather than
  point samples. Rotation, dip, vertical orientation, signed cell sizes, and
  native cell-center/value alignment are preserved.
- Corrected Grid2D export cell counts, dip recovery, and nonzero image extent
  offsets. Unsupported geometry and point arrays are explicitly rejected
  before creating a native grid. Added geometry, round-trip, public-reader,
  and invalid-input regression coverage. Consumers of the old point-sampled
  representation must migrate explicitly; see the README.
- Raised minimum dependencies to geoh5py 0.13.1, NumPy 2.4, and PyVista
  0.49.2. The PyVista minimum includes fixes for rotated ImageData
  point/cell conversion and combining empty nested MultiBlocks.
- Declared h5py 3.15 or newer as a direct dependency, reflecting its use in
  cataloging, hierarchy discovery, visibility, and selective reading.

## 0.9.4 - 2026-10-30

- Fixed coordinate precision loss when writing PolyData surfaces, curves, and
  vertex meshes through `write_geoh5` or `vtkwrap`. Homogeneous datasets bypass
  cell extraction; mixed-cell datasets use precision-preserving selection while
  retaining the first-cell-type export policy. Float64 UTM and mine-grid
  coordinates are no longer rounded to float32. Previously rounded files require
  re-export from original full-precision geometry; casting stored vertices to
  float64 cannot restore lost precision.

## 0.9.3 - 2026-10-28

- Made the indexed workspace root authoritative for both cataloging and selective
  reading, including root attributes. `/Root` is used only when the indexed root
  is absent. This replaces the split-root union policy, which could resurrect
  deleted entities through stale `/Root` links and introduce conflicting parents.
- Allowed concatenated drillhole discovery and selective loading when the native
  Drillhole object-type record is absent from the project's type index. Exact
  registered type identities use native defaults with an explicit warning about
  unavailable stored metadata. Unknown missing type IDs remain discoverable but
  unsupported; missing data-type definitions are not inferred.

## 0.9.2 - 2026-10-27

- Fixed discovery and selective loading of reachable hierarchy-only entities
  missing from the flat Groups/Objects/Data indices. Linked handles are used
  for unindexed geometry, channels, property groups and concatenated storage,
  while conflicting definitions in existing indices still raise errors.
  Source access remains read-only and payload-selective.

## 0.9.1 - 2026-10-27

- Unified catalog and selective-reader native hierarchy discovery. Split
  `/Root` and indexed root groups now contribute a UID-deduplicated union of
  child links, with `/Root` supplying root attributes. This preserves entities
  reachable through either representation without including orphaned objects.
- Conflicting root IDs/types, distinct non-root definitions for one UID,
  conflicting parents, and cycles raise contextual errors before conversion.
  Root-only files without an indexed root group are supported. Discovery remains
  metadata-only and read-only, with deterministic ordering and shared native and
  concatenated type resolution.

## 0.9.0 - 2026-10-27

- Added experimental `read_geoh5_entities(path, uids)`, using H5Reader and an
  owned in-memory workspace to convert selected ordinary objects and legacy
  or concatenated drillholes without opening the source as an eager workspace.
  Group expansion, overlap deduplication, source identity/display metadata,
  channel types and property groups are preserved. Concatenated drillhole payloads use selected
  index slices and compact public caches, supporting geoh5 2.0/2.1 metadata
  layouts without reading sibling payloads. Workspace distance units are
  retained. Existing full-file reading is unchanged.

## 0.8.1 - 2026-10-27

- Corrected visibility metadata and visible-only filtering to use each entity's
  stored `Visible` checkbox, including groups and concatenated drillholes.
  Per-view `Visible` datasets no longer override this value. Cataloging, full-file
  reading, and direct/selected entity conversion now use the same policy.
- A missing entity-level visibility attribute defaults to `True`, even when
  per-view records are hidden. This preserves the catalog default and follows
  the geoh5 format/geoh5py entity default, but changes conversion and filtering
  for files that previously fell back to hidden view records.
- Malformed entity-level visibility raises a contextual `ValueError` rather
  than being treated as missing or aggregated as view flags. Parent visibility
  is not folded into child metadata. Source attributes and view flags are not
  rewritten; existing drillhole group nesting/selection and metadata schema
  version 1 are unchanged.
