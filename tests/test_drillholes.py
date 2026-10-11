"""Drillhole geometry, independent sampling and composite persistence."""

import numpy as np
import pytest
import pyvista as pv
from geoh5py.groups import DrillholeGroup
from geoh5py.objects import Drillhole
from geoh5py.workspace import Workspace

from geoh5vista.drillholes import (
    drillhole_to_vtk,
    drillholes_to_vtk,
    read_drillholes,
    save_drillholes,
)
from geoh5vista.wrapper import geoh5wrap, read_geoh5, write_geoh5
from geoh5vista.data import add_drillhole_interval_data_to_vtk
from geoh5vista import drillholes


def make_hole(ws, group, name="DH-01", **kwargs):
    attributes = dict(
        collar=[10.0, 20.0, 100.0],
        end_of_hole=100.0,
        surveys=np.array([[0.0, 45.0, -45.0], [100.0, 90.0, -60.0]]),
    )
    attributes.update(kwargs)
    return Drillhole.create(ws, parent=group, name=name, **attributes)


def add_tables(hole):
    hole.add_data(
        {
            "Au": {
                "from-to": np.array([[0.0, 10.0], [10.0, 30.0]]),
                "values": np.array([1.0, np.nan]),
            }
        }
    )
    hole.add_data(
        {
            "rock": {
                "from-to": np.array([[0.0, 20.0], [20.0, 50.0], [60.0, 100.0]]),
                "values": np.array([1, 2, 3]),
                "type": "referenced",
                "value_map": {0: "Unknown", 1: "A", 2: "B", 3: "C"},
            }
        }
    )
    hole.add_data(
        {
            "log": {
                "depth": np.array([5.0, 15.0, 45.0]),
                "values": np.array([10.0, 20.0, 30.0]),
            }
        }
    )


def test_modern_independent_tables_without_stored_trace(tmp_path):
    path = tmp_path / "modern.geoh5"
    with Workspace.create(path) as ws:
        group = DrillholeGroup.create(ws, name="Holes")
        hole = make_hole(ws, group)
        add_tables(hole)
        uid = str(hole.uid)
        assert hole.trace is None
    with Workspace(path) as ws:
        hole = ws.get_entity("DH-01")[0]
        composite = geoh5wrap(hole)
        assert isinstance(composite, pv.MultiBlock)
        assert composite.keys() == ["collar", "trace", "intervals", "points"]
        np.testing.assert_allclose(composite["collar"].points, [hole.collar.tolist()])
        trace = composite["trace"]
        np.testing.assert_allclose(trace.points, hole.desurvey(trace["depth"]))
        assert trace.n_lines == trace.n_points - 1
        assert trace["depth"][0] == 0
        assert trace["depth"][-1] == 100
        intervals = composite["intervals"]
        assert len(intervals) == 2
        assays, geology = intervals
        assert assays.n_cells == 2
        assert geology.n_cells == 3
        np.testing.assert_array_equal(assays.cell_data["from"], [0.0, 10.0])
        np.testing.assert_array_equal(geology.cell_data["from"], [0.0, 20.0, 60.0])
        np.testing.assert_array_equal(geology.cell_data["rock"], [1, 2, 3])
        np.testing.assert_array_equal(geology.cell_data["rock_names"], ["A", "B", "C"])
        assert np.isnan(assays.cell_data["Au"][1])
        assert assays.get_cell(0).n_points > 2
        log = composite["points"][0]
        assert log.n_verts == 3
        np.testing.assert_array_equal(log.point_data["depth"], [5.0, 15.0, 45.0])
        np.testing.assert_array_equal(log.point_data["log"], [10.0, 20.0, 30.0])
        assert "log" not in trace.point_data
        assert composite.user_dict["geoh5"]["source"]["uid"] == uid
        assert geology.user_dict["geoh5"]["arrays"]["rock"]["value_map"]["2"] == "B"
        selected = geology.threshold([2, 2], scalars="rock", preference="cell")
        assert selected.n_cells == 1
        np.testing.assert_array_equal(selected.cell_data["source_row"], [1])
        tubes = geology.tube(radius=0.1)
        assert tubes.n_points > geology.n_points
        assert set(tubes.cell_data["rock"]) == {1, 2, 3}


def test_chord_error_and_measured_depth(tmp_path):
    with Workspace.create(tmp_path / "curve.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        tolerance = 0.001
        trace = drillhole_to_vtk(hole, curve_tolerance=tolerance)["trace"]
        depths = trace.point_data["depth"]
        midpoint = hole.desurvey((depths[:-1] + depths[1:]) / 2)
        chord_midpoint = (trace.points[:-1] + trace.points[1:]) / 2
        assert np.max(np.linalg.norm(midpoint - chord_midpoint, axis=1)) <= tolerance
        assert not np.isclose(depths[-1], trace.points[0, 2] - trace.points[-1, 2])
        assert np.max(np.diff(depths)) <= 5.0


@pytest.mark.parametrize("version", [1.0, 2.1])
def test_group_and_workspace_identity_visibility(tmp_path, version):
    path = tmp_path / "group.geoh5"
    with Workspace(path, version=version) as ws:
        group = DrillholeGroup.create(ws, name="Holes")
        first = make_hole(ws, group, "same")
        second = make_hole(ws, group, "same", collar=[40.0, 20.0, 100.0])
        second.visible = False
        result = drillholes_to_vtk(group)
        assert len(result) == 2
        assert len(set(result.keys())) == 2
        assert result[0].user_dict["geoh5"]["source"]["uid"] == str(first.uid)
        assert result[1].user_dict["geoh5"]["display"]["visible"] is False
        assert len(drillholes_to_vtk(group, load_only_visible=True)) == 1
    project = read_geoh5(path)
    assert project.keys() == ["Holes"]
    assert len(project["Holes"]) == 2
    assert len(read_geoh5(path, load_only_visible=True)["Holes"]) == 1
    with Workspace(path) as ws:
        ws.get_entity("Holes")[0].visible = False
    assert len(read_geoh5(path, load_only_visible=True)) == 0


def test_legacy_cell_and_padded_vertex_data(tmp_path):
    with Workspace(tmp_path / "legacy.geoh5", version=1.0) as ws:
        group = DrillholeGroup.create(ws)
        hole = make_hole(ws, group)
        hole.add_data(
            {
                "assay": {
                    "from-to": np.array([[0.0, 10.0], [20.0, 30.0]]),
                    "values": np.array([1.0, 2.0]),
                }
            }
        )
        hole.add_data(
            {
                "log": {
                    "depth": np.array([5.0, 15.0]),
                    "values": np.array([10.0, 20.0]),
                }
            }
        )
        result = drillhole_to_vtk(hole)
        intervals = result["intervals"][0]
        log = result["points"][0]
        np.testing.assert_array_equal(intervals.cell_data["assay"], [1.0, 2.0])
        np.testing.assert_array_equal(log.point_data["depth"], [5.0, 15.0])
        np.testing.assert_array_equal(log.point_data["log"], [10.0, 20.0])
        np.testing.assert_array_equal(
            log.point_data["source_row"],
            np.flatnonzero(np.isfinite(hole.depths.values)),
        )


def test_legacy_different_intervals_preserve_shared_alignment(tmp_path):
    with Workspace(tmp_path / "legacy-tables.geoh5", version=1.0) as ws:
        group = DrillholeGroup.create(ws)
        hole = make_hole(ws, group)
        add_tables(hole)
        composite = drillhole_to_vtk(hole)
        assert len(composite["intervals"]) == 1
        intervals = composite["intervals"][0]
        np.testing.assert_array_equal(intervals.cell_data["from"], hole.from_.values)
        for name in ("Au", "rock"):
            source = hole.get_data(name)[0]
            np.testing.assert_array_equal(
                intervals.cell_data[name], source.validate_values(source.values)
            )
        merged = drillholes_to_vtk(group, representation="merged")
        assert set(merged.cell_data["rock"][merged.cell_data["rock__valid"]]) == {1, 2, 3}
        assert merged.point_data["log__valid"].sum() == 3


@pytest.mark.parametrize("version", [1.0, 2.1])
def test_normalized_tables_are_row_aligned_without_mutating_source(tmp_path, version):
    with Workspace(tmp_path / "normalized.geoh5", version=version) as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        add_tables(hole)
        source_values = {
            child.uid: child.values.copy()
            for child in hole.children
            if hasattr(child, "values") and isinstance(child.values, np.ndarray)
        }
        tables = drillholes._tables(hole)
        for table in tables:
            assert np.isfinite(table.locations).all()
            assert len(table.source_rows) == len(table.locations)
            for field in table.data:
                source = field.source
                expected = source.values
                if version == 1.0:
                    expected = source.validate_values(expected)
                np.testing.assert_array_equal(field.values, expected[table.source_rows])
                assert len(field.values) == len(table.locations)
        points = next(table for table in tables if table.kind == "points")
        np.testing.assert_array_equal(points.locations, [5.0, 15.0, 45.0])
        for child in hole.children:
            if child.uid in source_values:
                np.testing.assert_array_equal(child.values, source_values[child.uid])


@pytest.mark.parametrize("values", [np.array([1.0]), np.array([1.0, 2.0, 3.0])])
def test_modern_normalization_rejects_misaligned_cached_values(tmp_path, monkeypatch, values):
    with Workspace.create(tmp_path / "misaligned.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        data = hole.add_data(
            {"grade": {"depth": np.array([10.0, 20.0]), "values": np.array([1.0, 2.0])}}
        )
        monkeypatch.setattr(data, "_values", values)
        with pytest.raises(ValueError, match="does not match table"):
            drillhole_to_vtk(hole)


def test_unlocated_data_is_not_silently_dropped(tmp_path):
    with Workspace.create(tmp_path / "unlocated.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        hole.add_data({"unlocated": {"association": "DEPTH", "values": np.array([1.0, 2.0])}})
        with pytest.raises(ValueError, match="no depth or interval sampling table"):
            drillhole_to_vtk(hole)


def test_overlap_gaps_and_duplicate_depths_preserved(tmp_path):
    with Workspace.create(tmp_path / "overlap.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        hole = make_hole(ws, group)
        hole.add_data(
            {
                "grade": {
                    "from-to": np.array([[0.0, 20.0], [10.0, 30.0], [50.0, 60.0]]),
                    "values": np.array([1.0, 2.0, 3.0]),
                }
            }
        )
        hole.add_data(
            {
                "sample": {
                    "depth": np.array([15.0, 15.0]),
                    "values": np.array([4.0, 5.0]),
                }
            }
        )
        composite = drillhole_to_vtk(hole)
        intervals = composite["intervals"][0]
        assert intervals.n_cells == 3
        np.testing.assert_array_equal(intervals.cell_data["to"], [20.0, 30.0, 60.0])
        samples = composite["points"][0]
        assert samples.n_points == 2
        np.testing.assert_array_equal(samples.points[0], samples.points[1])
        with pytest.raises(ValueError, match="Overlapping observations"):
            drillholes_to_vtk(group, representation="merged")


def test_multiple_point_tables_and_shared_arrays(tmp_path):
    with Workspace.create(tmp_path / "points.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        hole.add_data({"first": {"depth": np.array([10.0, 20.0]), "values": np.array([1.0, 2.0])}})
        hole.add_data({"second": {"depth": np.array([10.0, 20.0]), "values": np.array([3.0, 4.0])}})
        hole.add_data(
            {"third": {"depth": np.array([5.0, 25.0, 35.0]), "values": np.array([5.0, 6.0, 7.0])}}
        )
        tables = drillhole_to_vtk(hole)["points"]
        assert len(tables) == 2
        assert {"first", "second"} <= set(tables[0].point_data)
        assert tables[1].n_points == 3


def test_boolean_text_and_reserved_names(tmp_path):
    with Workspace.create(tmp_path / "types.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        hole.add_data({"depth": {"depth": np.array([10.0, 20.0]), "values": np.array([1.0, 2.0])}})
        hole.add_data(
            {
                "flag": {
                    "depth": np.array([10.0, 20.0]),
                    "values": np.array([True, False]),
                    "type": "boolean",
                }
            }
        )
        hole.add_data(
            {
                "description": {
                    "depth": np.array([10.0, 20.0]),
                    "values": np.array(["one", "two"]),
                    "type": "text",
                }
            }
        )
        mesh = drillhole_to_vtk(hole)["points"][0]
        metadata = mesh.user_dict["geoh5"]["arrays"]
        depth_key = next(key for key, value in metadata.items() if value["name"] == "depth")
        assert depth_key != "depth"
        np.testing.assert_array_equal(mesh["depth"], [10.0, 20.0])
        np.testing.assert_array_equal(mesh[depth_key], [1.0, 2.0])
        np.testing.assert_array_equal(mesh["flag"], [True, False])
        np.testing.assert_array_equal(mesh["description"], ["one", "two"])


def test_non_ascii_text_is_rejected_without_mangling(tmp_path):
    path = tmp_path / "text.geoh5"
    labels = ["caf\u00e9", "\u00e9chantillon"]
    with Workspace.create(path) as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        hole.add_data(
            {"text": {"depth": np.array([10.0, 20.0]), "values": np.array(labels), "type": "text"}}
        )
        hole.add_data(
            {
                "rock": {
                    "depth": np.array([10.0, 20.0]),
                    "values": np.array([1, 2]),
                    "type": "referenced",
                    "value_map": {0: "Unknown", 1: labels[0], 2: labels[1]},
                }
            }
        )
    with Workspace(path) as ws:
        with pytest.raises(ValueError, match="Non-ASCII text.*not supported"):
            drillhole_to_vtk(ws.get_entity("DH-01")[0])


def test_missing_surveys_and_collar_only(tmp_path):
    with Workspace.create(tmp_path / "collars.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        collar_only = make_hole(ws, group, end_of_hole=None, surveys=None)
        result = drillhole_to_vtk(collar_only)
        assert result["collar"].n_points == 1
        assert result["trace"].n_points == 0
        known_extent = make_hole(ws, group, "vertical", surveys=None)
        with pytest.warns(UserWarning, match="vertical path"):
            result = drillhole_to_vtk(known_extent)
        assert result.user_dict["geoh5"]["drillhole"]["survey_source"] == "inferred_vertical"
        np.testing.assert_allclose(result["trace"].points[-1], [10.0, 20.0, 0.0], atol=2e-5)


def test_sampling_infers_extent(tmp_path):
    with Workspace.create(tmp_path / "extent.geoh5") as ws:
        hole = make_hole(
            ws, DrillholeGroup.create(ws), end_of_hole=None, surveys=np.array([[0.0, 0.0, -90.0]])
        )
        hole.add_data({"grade": {"from-to": np.array([[10.0, 35.0]]), "values": np.array([1.0])}})
        result = drillhole_to_vtk(hole)
        assert result["trace"]["depth"][-1] == 35.0
        assert result.user_dict["geoh5"]["drillhole"]["extent_source"] == "sampling_and_surveys"


@pytest.mark.parametrize("bounds", [[[-1.0, 10.0]], [[0.0, 101.0]]])
def test_invalid_intervals_rejected(tmp_path, bounds):
    with Workspace.create(tmp_path / "invalid.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        hole.add_data({"grade": {"from-to": np.array(bounds), "values": np.array([1.0])}})
        with pytest.raises(ValueError, match="outside"):
            drillhole_to_vtk(hole)


@pytest.mark.parametrize("version", [1.0, 2.1])
def test_malformed_intervals_warn_and_preserve_source_rows(tmp_path, version):
    with Workspace(tmp_path / "malformed.geoh5", version=version) as ws:
        group = DrillholeGroup.create(ws)
        hole = make_hole(ws, group)
        bounds = np.array([[0., 10.], [20., 15.], [25., 25.], [30., 40.]])
        hole.add_data({"grade": {"from-to": bounds, "values": np.array([1., 2., 3., 4.])}})
        hole.add_data({"rock": {"from-to": bounds, "values": np.array([1, 2, 2, 3]),
                               "type": "referenced",
                               "value_map": {0: "Unknown", 1: "A", 2: "B", 3: "C"}}})
        with pytest.warns(UserWarning, match=r"DH-01.*omitting 2 rows.*\[1, 2\]"):
            composite = drillhole_to_vtk(hole)
        table = composite["intervals"][0]
        assert table.n_cells == 2
        assert table.n_verts == 0
        np.testing.assert_array_equal(table.cell_data["source_row"], [0, 3])
        np.testing.assert_array_equal(table.cell_data["grade"], [1., 4.])
        np.testing.assert_array_equal(table.cell_data["rock_names"], ["A", "C"])
        np.testing.assert_array_equal(table.cell_data["from"], [0., 30.])
        omitted = table.user_dict["geoh5"]["drillhole"]["omitted_intervals"]
        assert omitted == [
            {"source_row": 1, "from": 20., "to": 15.},
            {"source_row": 2, "from": 25., "to": 25.},
        ]
        source = hole.from_ if version == 1.0 else hole.from_[0]
        np.testing.assert_array_equal(source.values, bounds[:, 0])
        with pytest.warns(UserWarning, match="omitting 2 rows"):
            merged = drillholes_to_vtk(group, representation="merged")
        midpoint = (merged.cell_data["from"] + merged.cell_data["to"]) / 2
        assert not merged.cell_data["grade__valid"][(midpoint >= 10) & (midpoint < 30)].any()
    save_drillholes(composite, tmp_path / "malformed.vtm")
    restored = read_drillholes(tmp_path / "malformed.vtm")["intervals"][0]
    assert restored.user_dict["geoh5"]["drillhole"]["omitted_intervals"] == omitted
    np.testing.assert_array_equal(restored.cell_data["source_row"], [0, 3])


@pytest.mark.parametrize("bounds", [[[20., 10.]], [[10., 10.]]])
def test_all_malformed_intervals_produce_empty_table(tmp_path, bounds):
    with Workspace.create(tmp_path / "empty-intervals.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        hole.add_data({"grade": {"from-to": np.array(bounds), "values": np.array([1.])}})
        with pytest.warns(UserWarning, match="omitting 1 rows"):
            composite = drillhole_to_vtk(hole)
        table = composite["intervals"][0]
        assert table.n_points == table.n_cells == 0
        assert len(table.cell_data["grade"]) == 0
        assert len(table.cell_data["source_row"]) == 0
        assert composite["trace"].n_cells > 0


@pytest.mark.parametrize("tolerance", [0.0, -1.0, np.nan, np.inf])
def test_invalid_tolerance(tmp_path, tolerance):
    with Workspace.create(tmp_path / "tolerance.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        hole = make_hole(ws, group)
        with pytest.raises(ValueError, match="curve_tolerance"):
            drillhole_to_vtk(hole, curve_tolerance=tolerance)
        with pytest.raises(ValueError, match="curve_tolerance"):
            drillholes_to_vtk(group, curve_tolerance=tolerance)


def test_composite_persistence_without_mutation(tmp_path):
    with Workspace.create(tmp_path / "source.geoh5") as ws:
        group = DrillholeGroup.create(ws, name="Holes")
        add_tables(make_hole(ws, group))
        composite = drillholes_to_vtk(group)
    original = dict(composite[0].user_dict)
    filename = tmp_path / "holes.vtm"
    save_drillholes(composite, filename)
    assert dict(composite[0].user_dict) == original
    restored = read_drillholes(filename)
    assert restored.keys() == composite.keys()
    assert dict(restored.user_dict) == dict(composite.user_dict)
    assert dict(restored[0].user_dict) == original
    for kind in ("intervals", "points"):
        for expected, actual in zip(composite[0][kind], restored[0][kind]):
            assert dict(actual.user_dict) == dict(expected.user_dict)
            np.testing.assert_allclose(actual.points, expected.points)
            np.testing.assert_array_equal(actual.point_data["depth"], expected.point_data["depth"])
            for association in ("point_data", "cell_data"):
                original_arrays, read_arrays = (
                    getattr(expected, association),
                    getattr(actual, association),
                )
                for name in original_arrays:
                    np.testing.assert_array_equal(read_arrays[name], original_arrays[name])
                    assert read_arrays[name].dtype.kind == original_arrays[name].dtype.kind
    project = pv.MultiBlock({"Drillholes": composite})
    save_drillholes(project, tmp_path / "project.vtm")
    assert dict(read_drillholes(tmp_path / "project.vtm")[0][0].user_dict) == original


def test_merged_view_exact_points_and_interval_gaps(tmp_path):
    with Workspace.create(tmp_path / "merged.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        hole = make_hole(ws, group)
        add_tables(hole)
        mesh = drillholes_to_vtk(group, representation="merged")
        assert isinstance(mesh, pv.PolyData)
        midpoint = (mesh.cell_data["from"] + mesh.cell_data["to"]) / 2
        np.testing.assert_array_equal(mesh.cell_data["rock"][(midpoint >= 20) & (midpoint < 50)], 2)
        assert not mesh.cell_data["rock__valid"][(midpoint >= 50) & (midpoint < 60)].any()
        assert mesh.point_data["log__valid"].sum() == 3
        assert set(mesh.point_data["depth"][mesh.point_data["log__valid"]]) == {5.0, 15.0, 45.0}
        assert set(mesh.point_data["dh_uid"]) == {str(hole.uid)}


@pytest.mark.parametrize("kind", ["points", "intervals"])
def test_merged_fields_share_mapping_with_field_specific_validity(tmp_path, monkeypatch, kind):
    with Workspace.create(tmp_path / "shared-mapping.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        sampling = (
            {"depth": np.array([20.0, 20.0, 70.0])}
            if kind == "points"
            else {"from-to": np.array([[10.0, 30.0], [20.0, 40.0], [70.0, 80.0]])}
        )
        hole.add_data(
            {
                name: {
                    **sampling,
                    "values": np.array(values),
                    "type": "referenced",
                    "value_map": {0: "Unknown", 1: "A", 2: "B"},
                }
                for name, values in (("first", [1, 0, 0]), ("second", [0, 2, 0]))
            }
            | {"grade": {**sampling, "values": np.array([np.nan, 5.0, np.nan])}}
        )
        calls = []
        original = drillholes._merged_rows

        def record_mapping(table, depth, table_kind):
            calls.append(table_kind)
            return original(table, depth, table_kind)

        monkeypatch.setattr(drillholes, "_merged_rows", record_mapping)
        merged = drillhole_to_vtk(hole, representation="merged")
        assert calls == [kind]
        arrays = merged.point_data if kind == "points" else merged.cell_data
        locations = (
            arrays["depth"]
            if kind == "points"
            else (arrays["from"] + arrays["to"]) / 2
        )
        for name, code, label, start, stop in (
            ("first", 1, "A", 10.0, 30.0),
            ("second", 2, "B", 20.0, 40.0),
        ):
            expected = locations == 20.0 if kind == "points" else (
                (locations >= start) & (locations < stop)
            )
            np.testing.assert_array_equal(arrays[f"{name}__valid"], expected)
            np.testing.assert_array_equal(arrays[name][expected], code)
            np.testing.assert_array_equal(arrays[f"{name}_names"][expected], label)
            np.testing.assert_array_equal(arrays[f"{name}_names"][~expected], "")
        np.testing.assert_array_equal(arrays["grade__valid"], arrays["second__valid"])
        np.testing.assert_array_equal(arrays["grade"][arrays["grade__valid"]], 5.0)


@pytest.mark.parametrize("kind", ["points", "intervals"])
def test_shared_mapping_rejects_overlapping_valid_rows(tmp_path, kind):
    with Workspace.create(tmp_path / "conflicting-rows.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        sampling = (
            {"depth": np.array([20.0, 20.0])}
            if kind == "points"
            else {"from-to": np.array([[10.0, 30.0], [20.0, 40.0]])}
        )
        hole.add_data({"grade": {**sampling, "values": np.array([1.0, 2.0])}})
        with pytest.raises(ValueError, match="Overlapping observations"):
            drillhole_to_vtk(hole, representation="merged")


def test_shared_mapping_on_supplied_partial_line(tmp_path):
    with Workspace.create(tmp_path / "partial-line.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        add_tables(hole)
        depth = np.array([10.0, 15.0, 20.0, 30.0])
        mesh = pv.lines_from_points(hole.desurvey(depth))
        mesh.point_data["depth"] = depth
        with pytest.warns(UserWarning, match="not on the supplied line depths"):
            add_drillhole_interval_data_to_vtk(mesh, hole)
        np.testing.assert_array_equal(mesh.cell_data["rock"], [1, 1, 2])
        np.testing.assert_array_equal(mesh.cell_data["rock_names"], ["A", "A", "B"])
        assert not mesh.cell_data["Au__valid"].any()
        np.testing.assert_array_equal(mesh.point_data["log__valid"], [False, True, False, False])
        assert mesh.point_data["log"][1] == 20.0


def test_merged_heterogeneous_arrays_rejected(tmp_path):
    with Workspace.create(tmp_path / "heterogeneous.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        first = make_hole(ws, group)
        make_hole(ws, group, "DH-02")
        add_tables(first)
        with pytest.raises(ValueError, match="different arrays"):
            drillholes_to_vtk(group, representation="merged")


def test_merged_coincident_holes_keep_separate_identity(tmp_path):
    with Workspace.create(tmp_path / "coincident.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        first = make_hole(ws, group)
        second = make_hole(ws, group, "DH-02")
        expected_points = sum(drillhole_to_vtk(h)["trace"].n_points for h in (first, second))
        mesh = drillholes_to_vtk(group, representation="merged")
        assert mesh.n_points == expected_points
        assert set(mesh.point_data["dh_uid"]) == {str(first.uid), str(second.uid)}
        assert set(mesh.cell_data["dh_uid"]) == {str(first.uid), str(second.uid)}


def test_merged_homogeneous_tables_keep_validity_and_identity(tmp_path):
    with Workspace.create(tmp_path / "homogeneous.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        for name in ("DH-01", "DH-02"):
            add_tables(make_hole(ws, group, name))
        merged = drillholes_to_vtk(group, representation="merged")
        assert merged.point_data["log__valid"].dtype.kind == "b"
        assert merged.point_data["log__valid"].sum() == 6
        assert merged.cell_data["rock__valid"].dtype.kind == "b"


def test_standalone_hole_workspace_representation(tmp_path):
    path = tmp_path / "standalone.geoh5"
    with Workspace(path, version=1.0) as ws:
        hole = Drillhole.create(
            ws,
            name="standalone",
            collar=[0.0, 0.0, 0.0],
            end_of_hole=10.0,
            surveys=np.array([[0.0, 0.0, -90.0]]),
        )
        assert isinstance(drillhole_to_vtk(hole, representation="merged"), pv.PolyData)
    assert isinstance(read_geoh5(path)["standalone"], pv.MultiBlock)
    assert isinstance(
        read_geoh5(path, drillhole_representation="merged")["standalone"], pv.PolyData
    )


def test_line_helper_uses_all_sampling_tables(tmp_path):
    with Workspace.create(tmp_path / "helper.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        add_tables(hole)
        depth = np.array([0.0, 5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 50.0, 60.0, 100.0])
        mesh = pv.lines_from_points(hole.desurvey(depth))
        mesh.point_data["depth"] = depth
        assert add_drillhole_interval_data_to_vtk(mesh, hole) is mesh
        np.testing.assert_array_equal(mesh.cell_data["rock"], [1, 1, 1, 1, 2, 2, 2, 0, 3])
        assert mesh.point_data["log__valid"].sum() == 3
        incomplete = pv.lines_from_points(hole.desurvey(np.array([0.0, 100.0])))
        incomplete.point_data["depth"] = [0.0, 100.0]
        with pytest.raises(ValueError, match="cross sampling boundaries"):
            add_drillhole_interval_data_to_vtk(incomplete, hole)
        assert "rock" not in incomplete.cell_data


def test_missing_integer_and_false_boolean_remain_distinct(tmp_path):
    with Workspace.create(tmp_path / "missing.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        hole = make_hole(ws, group)
        hole.add_data(
            {
                "integer": {
                    "depth": np.array([10.0, 20.0, 30.0]),
                    "values": np.array([0.0, np.nan, 2.0]),
                    "type": "integer",
                }
            }
        )
        hole.add_data(
            {
                "flag": {
                    "depth": np.array([10.0, 20.0, 30.0]),
                    "values": np.array([False, True, False]),
                    "type": "boolean",
                }
            }
        )
        native = drillhole_to_vtk(hole)["points"][0]
        np.testing.assert_array_equal(native["integer__valid"], [True, False, True])
        np.testing.assert_array_equal(native["flag__valid"], [True, True, True])
        merged = drillholes_to_vtk(group, representation="merged")
        assert merged.point_data["integer__valid"].sum() == 2
        assert merged.point_data["flag__valid"].sum() == 3


def test_empty_group_and_point_table(tmp_path):
    with Workspace.create(tmp_path / "empty.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        assert len(drillholes_to_vtk(group)) == 0
        assert drillholes_to_vtk(group, representation="merged").n_cells == 0
        hole = make_hole(ws, group)
        hole.add_data(
            {"empty": {"depth": np.array([], dtype=float), "values": np.array([], dtype=float)}}
        )
        result = drillhole_to_vtk(hole)
        assert result["points"][0].n_points == 0


def test_nested_field_data_rejected_without_mutation(tmp_path):
    composite = pv.MultiBlock({"nested": pv.MultiBlock()})
    composite[0].user_dict["keep"] = "metadata"
    composite[0].field_data["extra"] = [1.0, 2.0]
    with pytest.raises(ValueError, match="Unexpected nested field data"):
        save_drillholes(composite, tmp_path / "field.vtm")
    assert composite[0].user_dict["keep"] == "metadata"
    assert "extra" in composite[0].field_data


def test_object_arrays_preserved_without_truncation(tmp_path):
    with Workspace.create(tmp_path / "object.geoh5") as ws:
        hole = make_hole(ws, DrillholeGroup.create(ws))
        hole.add_data({"scalar": {"association": "OBJECT", "values": np.array([42.0])}})
        hole.add_data({"vector": {"association": "OBJECT", "values": np.array([1.0, 2.0, 3.0])}})
        composite = drillhole_to_vtk(hole)
        collar = composite["collar"]
        np.testing.assert_array_equal(collar.point_data["scalar"], [42.0])
        np.testing.assert_array_equal(collar.field_data["vector"], [1.0, 2.0, 3.0])
        assert collar.user_dict["geoh5"]["arrays"]["vector"]["vtk_association"] == "field"
    save_drillholes(composite, tmp_path / "object.vtm")
    np.testing.assert_array_equal(
        read_drillholes(tmp_path / "object.vtm")["collar"].field_data["vector"], [1.0, 2.0, 3.0]
    )


def test_composite_export_rejected_before_creating_workspace(tmp_path):
    with Workspace.create(tmp_path / "source.geoh5") as ws:
        composite = drillholes_to_vtk(DrillholeGroup.create(ws))
        composite["DH"] = drillhole_to_vtk(make_hole(ws, ws.get_entity("Drillholes")[0]))
    destination = tmp_path / "unsupported.geoh5"
    with pytest.raises(ValueError, match="composite export"):
        write_geoh5(composite, destination)
    assert not destination.exists()


@pytest.mark.parametrize("explicit_name", [None, "curves"])
def test_merged_curve_export_preserves_line_geometry(tmp_path, explicit_name):
    with Workspace.create(tmp_path / "source.geoh5") as ws:
        group = DrillholeGroup.create(ws)
        add_tables(make_hole(ws, group))
        merged = drillholes_to_vtk(group, representation="merged")
    destination = tmp_path / "curves.geoh5"
    write_geoh5(merged, destination, entity_name=explicit_name)
    with Workspace(destination) as ws:
        curve = ws.get_entity(explicit_name or "Drillholes")[0]
        assert type(curve).__name__ == "Curve"
        assert len(curve.cells) == merged.n_cells
        np.testing.assert_allclose(
            curve.vertices[curve.cells], merged.points[merged.lines.reshape(-1, 3)[:, 1:]]
        )
