"""Faithful drillhole geometry and sampling-table representations."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, overload

import numpy as np
import pyvista
from geoh5py.data import BooleanData, Data, ReferencedData
from geoh5py.groups.drillhole import DrillholeGroup
from geoh5py.objects.drillhole import Drillhole
from geoh5py.shared.concatenation.drillhole import ConcatenatedDrillhole

from geoh5vista.data import add_entity_metadata
from geoh5vista.visibility import entity_visibility

__all__ = (
    "FUNCTION_DISPLAY_NAMES",
    "MODULE_DISPLAY_NAME",
    "drillhole_to_vtk",
    "drillholes_to_vtk",
    "read_drillholes",
    "save_drillholes",
)

MODULE_DISPLAY_NAME: Final[str] = "Drillholes"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "drillhole_to_vtk": "Drillhole to VTK",
    "drillholes_to_vtk": "Drillholes to VTK",
    "save_drillholes": "Save Drillholes",
    "read_drillholes": "Read Drillholes",
}


@dataclass
class _Field:
    source: Data
    values: np.ndarray | None


@dataclass
class _Table:
    name: str
    uid: str | None
    kind: Literal["points", "intervals"]
    locations: np.ndarray
    data: list[_Field]
    source_rows: np.ndarray


def _normalize_table(
    hole: Drillhole,
    name: str,
    uid: str | None,
    kind: Literal["points", "intervals"],
    locations: np.ndarray,
    fields: list[Data],
) -> _Table:
    locations = np.asarray(locations, dtype=float)
    if kind == "points":
        if locations.ndim != 1:
            raise ValueError(f"Depth table {name!r} must have one-dimensional depths.")
        valid = np.isfinite(locations)
    else:
        if locations.ndim != 2 or locations.shape[1] != 2:
            raise ValueError(f"Interval table {name!r} must have shape (n, 2).")
        valid = np.isfinite(locations).all(axis=1)
    legacy = not isinstance(hole, ConcatenatedDrillhole)
    # Legacy depth arrays include padding for vertices that belong to intervals.
    if not valid.all() and (not legacy or kind == "intervals" or np.isinf(locations).any()):
        raise ValueError(f"Non-finite depths in sampling table {name!r}.")
    rows = np.flatnonzero(valid)
    normalized = []
    for data in fields:
        values = data.values
        if values is not None:
            values = np.asarray(values)
            if values.ndim != 1 or len(values) > len(locations):
                raise ValueError(f"Data {data.name!r} does not match table {name!r}.")
            if legacy:
                values = np.asarray(data.validate_values(values))
            if len(values) != len(locations):
                raise ValueError(f"Data {data.name!r} does not match table {name!r}.")
            values = values[rows]
        normalized.append(_Field(data, values))
    return _Table(name, uid, kind, locations[rows], normalized, rows)


def _tables(hole: Drillhole) -> list[_Table]:
    tables = []
    if isinstance(hole, ConcatenatedDrillhole):
        sampled_uids = set()
        for group in hole.property_groups or []:
            if group.property_group_type not in ("Depth table", "Interval table"):
                continue
            sampled_uids.update(group.properties or [])
            locations = group.locations
            if locations is None:
                raise ValueError(f"Sampling table {group.name!r} has no depth coordinates.")
            coordinates = [group.depth_, group.from_, group.to_]
            coordinate_uids = {d.uid for d in coordinates if d is not None}
            fields = [
                hole.get_data(uid)[0]
                for uid in group.properties or []
                if uid not in coordinate_uids
            ]
            tables.append(
                _normalize_table(
                    hole,
                    group.name,
                    str(group.uid),
                    "points" if group.property_group_type == "Depth table" else "intervals",
                    np.asarray(locations),
                    fields,
                )
            )
        for child in hole.children:
            if (
                isinstance(child, Data)
                and child.association.name != "OBJECT"
                and child.uid not in sampled_uids
            ):
                raise ValueError(f"Data {child.name!r} has no depth or interval sampling table.")
    else:
        fields = [child for child in hole.children if isinstance(child, Data)]
        if hole.from_ is not None and hole.to_ is not None:
            tables.append(
                _normalize_table(
                    hole,
                    "intervals",
                    None,
                    "intervals",
                    np.c_[hole.from_.values, hole.to_.values],
                    [
                        d
                        for d in fields
                        if d.association.name == "CELL"
                        and d.uid not in (hole.from_.uid, hole.to_.uid)
                    ],
                )
            )
        if hole.depths is not None:
            tables.append(
                _normalize_table(
                    hole,
                    "depths",
                    None,
                    "points",
                    np.asarray(hole.depths.validate_values(hole.depths.values)),
                    [
                        d
                        for d in fields
                        if d.association.name == "VERTEX" and d.uid != hole.depths.uid
                    ],
                )
            )
    return tables


def _key(container, name: str, uid: str | None) -> str:
    if name not in container:
        return name
    base = f"{name} [{uid or 'source'}]"
    candidate = base
    index = 2
    while candidate in container:
        candidate = f"{base} {index}"
        index += 1
    return candidate


def _sample_depths(
    hole: Drillhole,
    start: float,
    end: float,
    tolerance: float,
    extra=(),
) -> np.ndarray:
    if start == end:
        return np.array([start])
    intervals = hole.intervals
    breaks = np.unique(np.r_[start, end, intervals["depths"], extra])
    breaks = breaks[(breaks >= start) & (breaks <= end)]
    samples = []
    for left, right in zip(breaks[:-1], breaks[1:]):
        index = np.searchsorted(intervals["depths"], left, side="right") - 1
        radius = abs(intervals["rad"][index])
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError(f"Invalid desurvey radius for drillhole {hole.name!r}.")
        # Circular-arc sagitta is bounded by arc_length**2 / (8 * radius).
        step = min(5.0, np.sqrt(8.0 * radius * tolerance))
        count = int(np.ceil((right - left) / step))
        samples.append(np.linspace(left, right, count + 1)[:-1])
    return np.r_[np.concatenate(samples), end]


def _geometry(hole: Drillhole, depths: np.ndarray) -> np.ndarray:
    points = hole.desurvey(depths)
    if not np.isfinite(points).all():
        raise ValueError(f"Non-finite desurvey coordinates for drillhole {hole.name!r}.")
    return points


def _component(mesh, hole: Drillhole, role: str):
    add_entity_metadata(mesh, hole)
    metadata = mesh.user_dict["geoh5"]
    metadata["drillhole"] = {"role": role, "hole_uid": str(hole.uid)}
    mesh.user_dict["geoh5"] = metadata
    return mesh


def _text_values(values: np.ndarray, name: str) -> np.ndarray:
    if not all(isinstance(value, (str, bytes)) for value in values.flat):
        raise TypeError(f"Non-text object values in drillhole data {name!r}.")
    result = np.asarray(
        [value.decode("utf-8") if isinstance(value, bytes) else value for value in values.flat],
        dtype=str,
    ).reshape(values.shape)
    if not all(value.isascii() for value in result.flat):
        raise ValueError(
            f"Non-ASCII text in drillhole data {name!r} is not supported by PyVista/VTK."
        )
    return result


def _add_arrays(mesh, fields: list[_Field], rows: np.ndarray, association: str):
    arrays = (
        mesh.point_data
        if association == "point"
        else mesh.cell_data
        if association == "cell"
        else mesh.field_data
    )
    metadata = mesh.user_dict["geoh5"]
    provenance = metadata.get("arrays", {})
    for field in fields:
        data, values = field.source, field.values
        if values is None:
            warnings.warn(f"Data {data.name!r} has no values; omitted.", stacklevel=3)
            continue
        if values.dtype.kind not in "biufUSO":
            raise TypeError(f"Unsupported drillhole data type for {data.name!r}: {values.dtype}.")
        if values.dtype.kind in "OUS":
            values = _text_values(values, data.name)
        name = _key(arrays, data.name, str(data.uid))
        arrays[name] = values[rows]
        valid = np.ones(len(rows), dtype=bool)
        no_data = data.nan_value
        if not isinstance(data, BooleanData):
            if values.dtype.kind == "f":
                valid = np.isfinite(values[rows])
            elif no_data is not None:
                valid = values[rows] != no_data
        validity_name = _key(arrays, f"{name}__valid", str(data.uid))
        arrays[validity_name] = valid
        entry = {
            "uid": str(data.uid),
            "name": data.name,
            "association": data.association.name,
            "vtk_association": association,
            "primitive_type": data.entity_type.primitive_type.name,
            "validity_array": validity_name,
        }
        if not isinstance(data, BooleanData):
            entry["no_data_value"] = (
                None
                if isinstance(no_data, float) and not np.isfinite(no_data)
                else no_data.item()
                if isinstance(no_data, np.generic)
                else no_data
            )
        if isinstance(data, ReferencedData) and data.value_map is not None:
            labels = _key(arrays, f"{name}_names", str(data.uid))
            arrays[labels] = _text_values(data.value_map.map_values(values[rows]), data.name)
            entry["labels_array"] = labels
            entry["value_map"] = {
                str(int(code)): label.decode("utf-8") if isinstance(label, bytes) else str(label)
                for code, label in zip(
                    data.value_map.map["Key"],
                    data.value_map.map_values(data.value_map.map["Key"]),
                )
            }
        provenance[name] = entry
    metadata["arrays"] = provenance
    mesh.user_dict["geoh5"] = metadata


def _table_mesh(hole: Drillhole, table: _Table, tolerance: float, end: float):
    locations = table.locations
    rows = np.arange(len(locations))
    if (locations < 0).any() or (locations > end).any():
        raise ValueError(f"Sampling table {table.name!r} extends outside the drillhole.")
    omitted_intervals = []
    if table.kind == "intervals":
        malformed = locations[:, 1] <= locations[:, 0]
        omitted_intervals = [
            {"source_row": int(row), "from": float(start), "to": float(stop)}
            for row, (start, stop) in zip(table.source_rows[malformed], locations[malformed])
        ]
        if omitted_intervals:
            warnings.warn(
                f"Drillhole {hole.name!r}, interval table {table.name!r}: "
                f"omitting {len(omitted_intervals)} rows with from >= to "
                f"(zero-based source rows {table.source_rows[malformed].tolist()}). "
                "Original bounds are recorded in drillhole.omitted_intervals metadata.",
                UserWarning,
                stacklevel=3,
            )
            rows = rows[~malformed]
            locations = locations[~malformed]
    if table.kind == "points":
        mesh = pyvista.PolyData(_geometry(hole, locations))
        mesh.point_data["depth"] = locations
        mesh.point_data["source_row"] = table.source_rows[rows]
        association = "point"
    else:
        points, cells, depths = [], [], []
        offset = 0
        for start, stop in locations:
            sample = _sample_depths(hole, start, stop, tolerance)
            points.append(_geometry(hole, sample))
            depths.append(sample)
            cells.extend([len(sample), *range(offset, offset + len(sample))])
            offset += len(sample)
        mesh = pyvista.PolyData(
            np.concatenate(points) if points else np.empty((0, 3)),
            lines=np.asarray(cells, dtype=np.int64),
        )
        mesh.point_data["depth"] = np.concatenate(depths) if depths else np.array([])
        mesh.cell_data["from"] = locations[:, 0]
        mesh.cell_data["to"] = locations[:, 1]
        mesh.cell_data["source_row"] = table.source_rows[rows]
        association = "cell"
    _component(mesh, hole, table.kind)
    metadata = mesh.user_dict["geoh5"]
    metadata["drillhole"].update(table_name=table.name, table_uid=table.uid)
    if omitted_intervals:
        metadata["drillhole"]["omitted_intervals"] = omitted_intervals
    mesh.user_dict["geoh5"] = metadata
    _add_arrays(mesh, table.data, rows, association)
    return mesh


@overload
def drillhole_to_vtk(
    hole: Drillhole,
    *,
    curve_tolerance: float = 0.01,
    representation: Literal["composite"] = "composite",
) -> pyvista.MultiBlock: ...


@overload
def drillhole_to_vtk(
    hole: Drillhole,
    *,
    curve_tolerance: float = 0.01,
    representation: Literal["merged"],
) -> pyvista.PolyData: ...


@overload
def drillhole_to_vtk(
    hole: Drillhole,
    *,
    curve_tolerance: float = 0.01,
    representation: Literal["composite", "merged"],
) -> pyvista.MultiBlock | pyvista.PolyData: ...


def drillhole_to_vtk(
    hole: Drillhole,
    *,
    curve_tolerance: float = 0.01,
    representation: Literal["composite", "merged"] = "composite",
) -> pyvista.MultiBlock | pyvista.PolyData:
    """Convert one modern or legacy hole, preserving independent sampling tables.

    ``curve_tolerance`` bounds circular-arc chord error in workspace distance
    units. Measured-depth steps are also limited to 5 units. Missing surveys
    use geoh5py's vertical default with a warning and explicit provenance.
    Without a known extent, a collar-only hole is retained without inventing
    a path. Sampling beyond an explicit end of hole is rejected.
    Reversed and zero-length intervals are omitted with a warning, retaining
    original row IDs and recording omitted bounds in the table metadata.
    ``representation="merged"`` requests a common-line visualization instead
    of the default composite and rejects overlapping valid observations.
    """
    if not isinstance(hole, Drillhole):
        raise TypeError("Expected a geoh5py Drillhole.")
    if representation not in ("composite", "merged"):
        raise ValueError("representation must be 'composite' or 'merged'.")
    if not np.isfinite(curve_tolerance) or curve_tolerance <= 0:
        raise ValueError("curve_tolerance must be finite and positive.")
    collar = np.asarray(hole.collar.tolist(), dtype=float).reshape((-1, 3))
    if collar.shape != (1, 3) or not np.isfinite(collar).all():
        raise ValueError(f"Invalid collar for drillhole {hole.name!r}.")
    tables = _tables(hole)
    surveys = hole.surveys
    # The public surveys getter synthesizes a vertical survey when storage is absent.
    inferred_survey = hole._surveys is None
    if (
        surveys.ndim != 2
        or surveys.shape[1] != 3
        or not np.isfinite(surveys).all()
        or (surveys[:, 0] < 0).any()
        or (np.diff(surveys[:, 0]) <= 0).any()
    ):
        raise ValueError(f"Invalid surveys for drillhole {hole.name!r}.")
    finite_depths = [surveys[:, 0]]
    for table in tables:
        values = np.asarray(table.locations, dtype=float).ravel()
        finite_depths.append(values[np.isfinite(values)])
    end = hole.end_of_hole
    # geoh5py may normalize an unspecified extent to zero during creation.
    if end is None or end == 0:
        end = float(np.concatenate(finite_depths).max(initial=0))
        extent_source = "sampling_and_surveys"
    else:
        end = float(end)
        extent_source = "end_of_hole"
    if not np.isfinite(end) or end < 0:
        raise ValueError(f"Invalid end of hole for drillhole {hole.name!r}.")
    result = pyvista.MultiBlock()
    add_entity_metadata(result, hole)
    metadata = result.user_dict["geoh5"]
    metadata["drillhole"] = {
        "role": "hole",
        "collar": collar[0].tolist(),
        "surveys": surveys.tolist(),
        "survey_source": "inferred_vertical" if inferred_survey else "stored",
        "end_of_hole": hole.end_of_hole,
        "extent": end,
        "extent_source": extent_source,
        "curve_tolerance": curve_tolerance,
        "planning": hole.planning,
        "cost": hole.cost,
        "distance_unit": hole.workspace.distance_unit,
    }
    result.user_dict["geoh5"] = metadata
    result["collar"] = _component(pyvista.PolyData(collar), hole, "collar")
    object_data = [
        d
        for d in hole.children
        if isinstance(d, Data)
        and d.association.name == "OBJECT"
        and d.name not in ("Visual Parameters", "UserComments")
    ]
    for data in object_data:
        values = None if data.values is None else np.asarray(data.values)
        size = len(values) if values is not None else 0
        _add_arrays(
            result["collar"], [_Field(data, values)], np.arange(size),
            "point" if size == 1 else "field",
        )
    if end > 0 and inferred_survey:
        warnings.warn(
            f"Drillhole {hole.name!r} has no stored surveys; using a vertical path.",
            UserWarning,
            stacklevel=2,
        )
    if end > 0:
        depth = _sample_depths(hole, 0, end, curve_tolerance)
        trace = pyvista.lines_from_points(_geometry(hole, depth))
        trace.point_data["depth"] = depth
        trace.cell_data["from"] = depth[:-1]
        trace.cell_data["to"] = depth[1:]
        result["trace"] = _component(trace, hole, "trace")
    else:
        result["trace"] = _component(pyvista.PolyData(), hole, "trace")
    result["intervals"] = pyvista.MultiBlock()
    result["points"] = pyvista.MultiBlock()
    for table in tables:
        container = result[table.kind]
        container[_key(container.keys(), table.name, table.uid)] = _table_mesh(
            hole,
            table,
            curve_tolerance,
            end,
        )
    return result if representation == "composite" else _merged_hole(hole, result)


def _merged_rows(
    table: pyvista.PolyData,
    depth: np.ndarray,
    kind: Literal["intervals", "points"],
) -> tuple[np.ndarray, np.ndarray]:
    if kind == "intervals":
        midpoint = (depth[:-1] + depth[1:]) / 2
        starts = np.searchsorted(midpoint, table.cell_data["from"], side="left")
        stops = np.searchsorted(midpoint, table.cell_data["to"], side="left")
    else:
        starts = np.searchsorted(depth, table.point_data["depth"], side="left")
        stops = np.searchsorted(depth, table.point_data["depth"], side="right")
    # Retain overlapping rows; conflicts depend on each field's validity mask.
    source_rows = np.repeat(np.arange(len(starts)), stops - starts)
    target_rows = (
        np.concatenate([np.arange(start, stop) for start, stop in zip(starts, stops)])
        if len(starts)
        else np.empty(0, dtype=np.int64)
    )
    return source_rows, target_rows


def _merged_hole(
    hole: Drillhole,
    composite: pyvista.MultiBlock,
    output: pyvista.PolyData | None = None,
) -> pyvista.PolyData:
    """Derive common line cells without interpolating point observations."""
    end = composite.user_dict["geoh5"]["drillhole"]["extent"]
    if end == 0 and output is None:
        return _component(pyvista.PolyData(), hole, "merged")
    extras = [
        mesh.point_data["depth"] for kind in ("intervals", "points") for mesh in composite[kind]
    ]
    if output is None:
        depth = _sample_depths(
            hole,
            0,
            end,
            composite.user_dict["geoh5"]["drillhole"]["curve_tolerance"],
            np.concatenate(extras) if extras else (),
        )
        output = pyvista.lines_from_points(_geometry(hole, depth))
    else:
        if "depth" not in output.point_data:
            raise ValueError("The line object must have a 'depth' point data array.")
        depth = np.asarray(output.point_data["depth"])
        if (
            depth.ndim != 1
            or len(depth) < 2
            or not np.isfinite(depth).all()
            or (np.diff(depth) <= 0).any()
            or depth[0] < 0
            or depth[-1] > end
        ):
            raise ValueError("Line depths must increase within the drillhole extent.")
        expected = np.c_[
            np.full(len(depth) - 1, 2), np.arange(len(depth) - 1), np.arange(1, len(depth))
        ].ravel()
        if output.n_cells != len(depth) - 1 or not np.array_equal(output.lines, expected):
            raise ValueError("Expected sequential two-point line cells.")
        for table in composite["intervals"]:
            boundaries = np.r_[table.cell_data["from"], table.cell_data["to"]]
            boundaries = boundaries[(boundaries > depth[0]) & (boundaries < depth[-1])]
            if not np.isin(boundaries, depth).all():
                raise ValueError(
                    "Line cells cross sampling boundaries; split at all interval depths."
                )
        for table in composite["points"]:
            if not np.isin(table.point_data["depth"], depth).all():
                warnings.warn(
                    "Point observations not on the supplied line depths are omitted.",
                    UserWarning,
                    stacklevel=3,
                )
    mesh = _component(output, hole, "merged")
    mesh.point_data["depth"] = depth
    mesh.point_data["dh_name"] = np.repeat(hole.name, mesh.n_points)
    mesh.point_data["dh_uid"] = np.repeat(str(hole.uid), mesh.n_points)
    mesh.cell_data["dh_uid"] = np.repeat(str(hole.uid), mesh.n_cells)
    mesh.cell_data["from"] = depth[:-1]
    mesh.cell_data["to"] = depth[1:]
    metadata = mesh.user_dict["geoh5"]
    metadata["arrays"] = {}
    kinds: tuple[Literal["intervals", "points"], ...] = ("intervals", "points")
    for kind in kinds:
        target = mesh.cell_data if kind == "intervals" else mesh.point_data
        size = mesh.n_cells if kind == "intervals" else mesh.n_points
        for table in composite[kind]:
            source_arrays = table.cell_data if kind == "intervals" else table.point_data
            source_rows, target_rows = _merged_rows(table, depth, kind)
            provenance = table.user_dict["geoh5"]["arrays"]
            for name, entry in provenance.items():
                source = source_arrays[name]
                fill = (
                    np.nan if source.dtype.kind == "f" else "" if source.dtype.kind in "US" else 0
                )
                values = np.full(size, fill, dtype=source.dtype)
                valid = np.zeros(size, dtype=bool)
                selected = source_arrays[entry["validity_array"]][source_rows]
                source_indices, target_indices = source_rows[selected], target_rows[selected]
                if len(np.unique(target_indices)) != len(target_indices):
                    raise ValueError(
                        f"Overlapping observations in {name!r} cannot be merged losslessly; "
                        "use the composite representation."
                    )
                values[target_indices] = source[source_indices]
                valid[target_indices] = True
                key = _key(target, name, entry["uid"])
                target[key] = values
                validity_name = _key(target, f"{key}__valid", entry["uid"])
                target[validity_name] = valid
                exported = dict(entry, validity_array=validity_name)
                if "labels_array" in entry:
                    label_source = source_arrays[entry["labels_array"]]
                    labels = np.full(size, "", dtype=label_source.dtype)
                    labels[target_indices] = label_source[source_indices]
                    label_key = _key(target, f"{key}_names", entry["uid"])
                    target[label_key] = labels
                    exported["labels_array"] = label_key
                metadata["arrays"][key] = exported
    mesh.user_dict["geoh5"] = metadata
    return mesh


def drillholes_to_vtk(
    group: DrillholeGroup,
    *,
    representation: Literal["composite", "merged"] = "composite",
    curve_tolerance: float = 0.01,
    load_only_visible: bool = False,
) -> pyvista.MultiBlock | pyvista.PolyData:
    """Convert a group to independent holes, or an explicit merged-line view.

    Merged output is a visualization derivative. Overlapping observations
    in one array cannot be represented there and raise ``ValueError``.
    Visible-only filtering uses each hole's own stored checkbox, not view flags
    or the group's state. A missing visibility attribute defaults to True.
    """
    if not isinstance(group, DrillholeGroup):
        raise TypeError("Expected a geoh5py DrillholeGroup.")
    if representation not in ("composite", "merged"):
        raise ValueError("representation must be 'composite' or 'merged'.")
    if not np.isfinite(curve_tolerance) or curve_tolerance <= 0:
        raise ValueError("curve_tolerance must be finite and positive.")
    result = pyvista.MultiBlock()
    add_entity_metadata(result, group)
    for hole in group.children:
        if not isinstance(hole, Drillhole):
            continue
        if load_only_visible and not entity_visibility(hole):
            continue
        composite = drillhole_to_vtk(hole, curve_tolerance=curve_tolerance)
        result[_key(result.keys(), hole.name, str(hole.uid))] = (
            composite if representation == "composite" else _merged_hole(hole, composite)
        )
    if representation == "composite":
        return result
    merged = pyvista.PolyData()
    # VTK append drops arrays absent from any input: reject heterogeneous schemas.
    signatures = [
        set(
            (association, name, values.dtype.kind)
            for association, arrays in (("point", mesh.point_data), ("cell", mesh.cell_data))
            for name, values in arrays.items()
        )
        for mesh in result
    ]
    if signatures and any(signature != signatures[0] for signature in signatures):
        raise ValueError(
            "Holes have different arrays; use the composite representation "
            "or merge individual homogeneous subsets."
        )
    semantics = [
        {
            name: {key: entry.get(key) for key in ("name", "primitive_type", "value_map")}
            for name, entry in mesh.user_dict["geoh5"]["arrays"].items()
        }
        for mesh in result
    ]
    if semantics and any(item != semantics[0] for item in semantics):
        raise ValueError("Holes have different data definitions; use the composite representation.")
    for mesh in result:
        if merged.n_points == 0:
            merged = mesh.copy(deep=True)
        else:
            merged.merge(mesh, merge_points=False, inplace=True)
    if result.n_blocks:
        for target, original in (
            (merged.point_data, result[0].point_data),
            (merged.cell_data, result[0].cell_data),
        ):
            for name, values in original.items():
                if values.dtype.kind == "b":
                    target[name] = np.asarray(target[name]).astype(bool)
    add_entity_metadata(merged, group)
    metadata = merged.user_dict["geoh5"]
    metadata["drillhole"] = {
        "role": "merged_group",
        "holes": {str(i): dict(mesh.user_dict["geoh5"]) for i, mesh in enumerate(result)},
    }
    merged.user_dict["geoh5"] = metadata
    return merged


def save_drillholes(data: pyvista.MultiBlock, filename: str | Path) -> None:
    """Save a composite as VTM, preserving nested container metadata."""
    if not isinstance(data, pyvista.MultiBlock):
        raise TypeError("Expected a MultiBlock drillhole composite.")
    if Path(filename).suffix.lower() != ".vtm":
        raise ValueError("Drillhole composites must be saved as .vtm.")
    packed = data.copy(deep=True)
    if "geoh5vista_nested_metadata" in packed.user_dict:
        raise ValueError("Reserved nested-metadata registry key is already present.")
    registry = {}
    for index, _, block in packed.recursive_iterator("all", node_type="parent"):
        if any(name != "_PYVISTA_USER_DICT" for name in block.field_data):
            raise ValueError("Unexpected nested field data in drillhole composite.")
        if block.user_dict:
            registry["/".join(map(str, index))] = dict(block.user_dict)
        block.clear_field_data()
    for index, _, block in data.recursive_iterator("all", node_type="child"):
        if block is None:
            continue
        if "geoh5vista_boolean_arrays" in block.user_dict:
            raise ValueError("Reserved Boolean-array registry key is already present.")
        boolean_arrays = {
            association: [
                name
                for name, array in getattr(block, association).items()
                if name != "_PYVISTA_USER_DICT" and array.dtype.kind == "b"
            ]
            for association in ("point_data", "cell_data", "field_data")
        }
        if any(boolean_arrays.values()):
            target = packed
            for part in index:
                target = target[part]
            target.user_dict["geoh5vista_boolean_arrays"] = boolean_arrays
    packed.user_dict["geoh5vista_nested_metadata"] = registry
    packed.save(filename)


def _retain_wrappers(data: pyvista.MultiBlock) -> None:
    # Keep Python wrappers alive so Boolean dtype tracking survives nested lookups.
    for index in range(len(data)):
        block = data[index]
        if isinstance(block, pyvista.MultiBlock):
            _retain_wrappers(block)
        name = data.get_block_name(index)
        data[index] = block
        data.set_block_name(index, name)


def read_drillholes(filename: str | Path) -> pyvista.MultiBlock:
    """Read a VTM saved by :func:`save_drillholes` and restore container metadata."""
    data = pyvista.read(filename)
    if not isinstance(data, pyvista.MultiBlock):
        raise TypeError("Expected a MultiBlock drillhole file.")
    _retain_wrappers(data)
    if "geoh5vista_nested_metadata" not in data.user_dict:
        raise ValueError("Missing nested metadata registry; save composites with save_drillholes.")
    registry = data.user_dict.pop("geoh5vista_nested_metadata")
    if not isinstance(registry, dict):
        raise ValueError("Invalid nested drillhole metadata registry.")
    for path, metadata in registry.items():
        if (
            not isinstance(path, str)
            or not all(part.isdecimal() for part in path.split("/"))
            or not isinstance(metadata, dict)
        ):
            raise ValueError("Invalid nested drillhole metadata entry.")
        block = data
        for index in path.split("/"):
            if not isinstance(block, pyvista.MultiBlock) or int(index) >= len(block):
                raise ValueError("Nested drillhole metadata path does not match the file.")
            block = block[int(index)]
        if not isinstance(block, pyvista.MultiBlock):
            raise ValueError("Nested drillhole metadata must refer to a MultiBlock.")
        block.user_dict.update(metadata)
    # VTK XML persists bool arrays as uint8 and does not retain PyVista's bool tracking.
    for block in data.recursive_iterator(node_type="child"):
        if block is None or "geoh5vista_boolean_arrays" not in block.user_dict:
            continue
        boolean_arrays = block.user_dict.pop("geoh5vista_boolean_arrays")
        if not isinstance(boolean_arrays, dict):
            raise ValueError("Invalid Boolean-array registry.")
        for association, names in boolean_arrays.items():
            if association not in ("point_data", "cell_data", "field_data") or not isinstance(
                names, list
            ):
                raise ValueError("Invalid Boolean-array association.")
            arrays = getattr(block, association)
            for name in names:
                if not isinstance(name, str) or name not in arrays:
                    raise ValueError("Boolean-array registry does not match the file.")
                if not np.isin(arrays[name], [0, 1]).all():
                    raise ValueError(f"Invalid Boolean values in {name!r}.")
                arrays[name] = np.asarray(arrays[name]).astype(bool)
    return data
