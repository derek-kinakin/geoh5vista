# Release notes

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
