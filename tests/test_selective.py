"""Structural read boundaries for the experimental selective reader."""

import hashlib
from uuid import uuid4

import h5py
import numpy as np
import pytest
import pyvista
from geoh5py.groups import ContainerGroup, DrillholeGroup
from geoh5py.io import H5Reader
from geoh5py.objects import (
    BlockModel,
    Curve,
    Drillhole,
    Grid2D,
    Label,
    Octree,
    Points,
    Slicer,
    Surface,
)
from geoh5py.workspace import Workspace

from geoh5vista import read_geoh5_entities
from geoh5vista.wrapper import geoh5wrap


def guard_reads(monkeypatch, forbidden):
    reads = []
    getitem = h5py.Dataset.__getitem__
    read_direct = h5py.Dataset.read_direct

    def check(dataset):
        assert not any(str(uid) in dataset.name for uid in forbidden), dataset.name
        reads.append(dataset.name)

    def guarded_getitem(dataset, selection):
        check(dataset)
        return getitem(dataset, selection)

    def guarded_direct(dataset, dest, source_sel=None, dest_sel=None):
        check(dataset)
        return read_direct(dataset, dest, source_sel, dest_sel)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", guarded_getitem)
    monkeypatch.setattr(h5py.Dataset, "read_direct", guarded_direct)
    return reads


@pytest.mark.parametrize("kind", [Points, Curve, Surface])
def test_selected_object_data_metadata_and_detachment(tmp_path, monkeypatch, kind):
    path = tmp_path / "objects.geoh5"
    vertices = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
    with Workspace.create(path) as ws:
        folder = ContainerGroup.create(ws, name="Folder")
        obj = kind.create(ws, parent=folder, vertices=vertices, name="A")
        obj.add_default_visual_parameters().colour = [10, 20, 30]
        obj.visible = False
        obj.add_data({"grade": {"values": np.array([3., 4., 5.]), "association": "VERTEX"}})
        obj.add_data({
            "rock": {
                "values": np.array([1, 2, 1]), "association": "VERTEX",
                "type": "referenced", "value_map": {0: "Unknown", 1: "A", 2: "B"},
            }
        })
        obj.create_property_group(
            name="Properties", properties=[obj.get_data("grade")[0].uid]
        )
        other = Points.create(ws, name="B", vertices=vertices)
        uid, other_uid, parent_uid = obj.uid, other.uid, folder.uid
    with h5py.File(path, "r+") as file:
        file[f"GEOSCIENCE/Objects/{{{uid}}}"].create_dataset(
            "Visible", data=np.ones(2, dtype=np.int32)
        )
    before = hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns
    reads = guard_reads(monkeypatch, [other_uid])
    source_open = Workspace.__init__
    owned_handles = []

    def no_source_workspace(workspace, h5file=None, **kwargs):
        assert h5file is None, "Source must not be opened as a Workspace"
        source_open(workspace, h5file, **kwargs)
        owned_handles.append(workspace.geoh5)

    monkeypatch.setattr(Workspace, "__init__", no_source_workspace)
    result = read_geoh5_entities(path, str(uid))
    assert owned_handles and all(not handle.id.valid for handle in owned_handles)
    assert len(result) == 1
    mesh = result[0]
    np.testing.assert_array_equal(mesh.points, vertices)
    np.testing.assert_array_equal(mesh["grade"], [3., 4., 5.])
    np.testing.assert_array_equal(mesh["rock_names"], ["A", "B", "A"])
    metadata = mesh.user_dict["geoh5"]
    assert metadata["source"]["uid"] == str(uid)
    assert metadata["source"]["parent_uid"] == str(parent_uid)
    assert metadata["display"] == {
        "name": "A", "colour": [10, 20, 30], "visible": False,
    }
    assert any(str(uid) in name and name.endswith("/Vertices") for name in reads)
    assert (hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns) == before
    path.unlink()
    np.testing.assert_array_equal(mesh.copy(deep=True)["grade"], [3., 4., 5.])


def test_group_expansion_overlaps_and_sibling_exclusion(tmp_path, monkeypatch):
    path = tmp_path / "groups.geoh5"
    with Workspace.create(path) as ws:
        folder = ContainerGroup.create(ws, name="Folder")
        first = Points.create(ws, parent=folder, name="same", vertices=[[0., 0., 0.]])
        nested = ContainerGroup.create(ws, parent=folder)
        second = Points.create(ws, parent=nested, name="same", vertices=[[1., 0., 0.]])
        other = Points.create(ws, vertices=[[2., 0., 0.]])
        folder_uid, first_uid, second_uid, other_uid = (
            folder.uid, first.uid, second.uid, other.uid
        )
    guard_reads(monkeypatch, [other_uid])
    blocks = read_geoh5_entities(path, [folder_uid, first_uid, folder_uid])
    assert len(blocks) == 2
    assert {block.user_dict["geoh5"]["source"]["uid"] for block in blocks} == {
        str(first_uid), str(second_uid),
    }
    assert len(set(blocks.keys())) == 2


@pytest.mark.parametrize("kind", [Grid2D, BlockModel, Label, Slicer])
def test_other_ordinary_types_match_existing_conversion(tmp_path, monkeypatch, kind):
    path = tmp_path / "ordinary.geoh5"
    with Workspace.create(path) as ws:
        if kind is Grid2D:
            obj = kind.create(ws, u_count=3, v_count=4, rotation=30.)
        elif kind is BlockModel:
            obj = kind.create(
                ws, rotation=30.,
                u_cell_delimiters=np.array([0., 1., 3.]),
                v_cell_delimiters=np.array([0., 1.]),
                z_cell_delimiters=np.array([0., 2.]),
            )
            obj.add_data({
                "grade": {"values": np.array([3., 4.]), "association": "CELL"},
            })
        elif kind is Label:
            obj = kind.create(ws)
            setattr(obj, "Label position", np.array([1., 2., 3.]))
            setattr(obj, "Target position", np.array([4., 5., 6.]))
        else:
            obj = kind.create(ws)
            obj.add_default_visual_parameters().values = (
                "<IParameterList><Position>{1,2,3}</Position>"
                "<Orientation>{0,0,1}</Orientation></IParameterList>"
            )
        uid = obj.uid
        if kind is not Slicer:
            obj.add_default_visual_parameters().colour = [10, 20, 30]
        other_uid = Points.create(ws, vertices=[[0., 0., 0.]]).uid
    if kind is Label:
        with h5py.File(path, "r+") as file:
            group = file[f"GEOSCIENCE/Objects/{{{uid}}}"]
            group.attrs["Label position"] = [1., 2., 3.]
            group.attrs["Target position"] = [4., 5., 6.]
    with Workspace(path, mode="r") as ws:
        expected = geoh5wrap(ws.get_entity(uid)[0])
    guard_reads(monkeypatch, [other_uid])
    actual = read_geoh5_entities(path, uid)[0]
    assert type(actual) is type(expected)
    np.testing.assert_allclose(actual.points, expected.points)
    assert actual.n_cells == expected.n_cells
    assert actual.user_dict == expected.user_dict
    for association in ("point_data", "cell_data"):
        expected_arrays = getattr(expected, association)
        actual_arrays = getattr(actual, association)
        assert actual_arrays.keys() == expected_arrays.keys()
        for name in expected_arrays:
            np.testing.assert_array_equal(actual_arrays[name], expected_arrays[name])


def test_unsupported_explicit_object_and_unsupported_group_descendant(tmp_path, monkeypatch):
    path = tmp_path / "unsupported.geoh5"
    with Workspace.create(path) as ws:
        folder = ContainerGroup.create(ws)
        octree = Octree.create(ws, parent=folder)
        point = Points.create(ws, parent=folder, vertices=[[0., 0., 0.]])
        folder_uid, octree_uid, point_uid = folder.uid, octree.uid, point.uid
    guard_reads(monkeypatch, [octree_uid])
    with pytest.raises(ValueError, match="No converter"):
        read_geoh5_entities(path, octree_uid)
    assert read_geoh5_entities(path, folder_uid)[0].user_dict["geoh5"]["source"]["uid"] == str(point_uid)


@pytest.mark.parametrize("select_group", [False, True])
def test_legacy_drillholes(tmp_path, monkeypatch, select_group):
    path = tmp_path / "legacy.geoh5"
    with Workspace(path, version=1.0) as ws:
        group = DrillholeGroup.create(ws, name="Holes")
        holes = []
        for index in range(2):
            hole = Drillhole.create(
                ws, parent=group, name=f"DH-{index}", collar=[float(index), 0., 100.],
                end_of_hole=10., surveys=np.array([[0., 0., -90.], [10., 0., -90.]]),
            )
            hole.add_data({
                "grade": {"from-to": np.array([[0., 10.]]), "values": np.array([3.])},
            })
            holes.append(hole.uid)
        group_uid = group.uid
    guard_reads(monkeypatch, [] if select_group else [holes[1]])
    blocks = read_geoh5_entities(path, group_uid if select_group else holes[0])
    assert len(blocks) == 1
    hole = blocks[0][0] if select_group else blocks[0]
    assert hole["trace"].n_points > 0
    np.testing.assert_array_equal(hole["intervals"][0]["grade"], [3.])
    assert hole.user_dict["geoh5"]["source"]["parent_uid"] == str(group_uid)
    if select_group:
        assert len(blocks[0]) == 2


def assert_converted_equal(actual, expected):
    assert type(actual) is type(expected)
    assert actual.user_dict == expected.user_dict
    if isinstance(expected, pyvista.MultiBlock):
        assert set(actual.keys()) == set(expected.keys())
        for key in expected.keys():  # noqa: SIM118 - MultiBlock iterates blocks, not keys
            assert_converted_equal(actual[key], expected[key])
    else:
        np.testing.assert_allclose(actual.points, expected.points)
        assert actual.n_cells == expected.n_cells
        for association in ("point_data", "cell_data", "field_data"):
            expected_arrays = getattr(expected, association)
            actual_arrays = getattr(actual, association)
            assert actual_arrays.keys() == expected_arrays.keys()
            for name in expected_arrays:
                np.testing.assert_array_equal(actual_arrays[name], expected_arrays[name])


@pytest.mark.parametrize("version", [2.0, 2.1])
@pytest.mark.parametrize("selection_kind", ["hole", "multiple", "group"])
def test_concatenated_selection_reads_only_selected_slices(
    tmp_path, monkeypatch, version, selection_kind,
):
    path = tmp_path / "modern.geoh5"
    with Workspace(path, version=version, distance_unit="foot") as ws:
        group = DrillholeGroup.create(ws)
        holes = []
        for index in range(3):
            hole = Drillhole.create(
                ws, parent=group, name=f"DH-{index}", collar=[float(index), 0., 100.],
                surveys=np.array([[0., 0., -90.], [10., 0., -90.]]), end_of_hole=10.,
            )
            hole.add_data({
                "grade": {"from-to": np.array([[0., 10.]]), "values": np.array([3. + index])},
            })
            hole.add_data({
                "rock": {
                    "from-to": np.array([[0., 5.], [5., 10.]]),
                    "values": np.array([1, 2]), "type": "referenced",
                    "value_map": {0: "Unknown", 1: "A", 2: "B"},
                },
            })
            hole.add_data({
                "log/channel": {
                    "depth": np.array([2., 8.]), "values": np.array([10., np.nan]),
                },
            })
            hole.add_data({
                "note": {
                    "depth": np.array([2., 8.]), "values": np.array(["a", "b"]),
                    "type": "text",
                },
                "flag": {
                    "depth": np.array([2., 8.]), "values": np.array([True, False]),
                    "type": "boolean",
                },
            })
            hole.visible = index != 1
            hole.add_default_visual_parameters().values = np.array([
                "<IParameterList><Colour>4278850590</Colour></IParameterList>"
            ])
            holes.append(hole.uid)
        unrelated_group = DrillholeGroup.create(ws)
        Drillhole.create(
            ws, parent=unrelated_group, name="Unrelated", collar=[100., 0., 0.],
            surveys=np.array([[0., 45., -90.]]), end_of_hole=50.,
        )
        unrelated_group_uid = unrelated_group.uid
        point = Points.create(ws, vertices=[[1., 2., 3.]])
        hole_uid, group_uid, point_uid = holes[1], group.uid, point.uid
    selected_holes = set(holes if selection_kind == "group" else (
        holes[1:] if selection_kind == "multiple" else [hole_uid]
    ))
    selection = (
        [group_uid, hole_uid] if selection_kind == "group"
        else list(selected_holes) if selection_kind == "multiple" else hole_uid
    )
    if version > 2:
        with h5py.File(path, "r+") as file:
            storage = file[f"GEOSCIENCE/Groups/{{{group_uid}}}/Concatenated Data"]
            storage.move("Surveys", "Data/Surveys")
    with Workspace(path, mode="r") as ws:
        expected = {
            uid: geoh5wrap(ws.get_entity(uid)[0]) for uid in selected_holes
        }
        expected_group = geoh5wrap(ws.get_entity(group_uid)[0])
    ranges = {}
    with h5py.File(path, "r") as file:
        storage = file[f"GEOSCIENCE/Groups/{{{group_uid}}}/Concatenated Data"]
        for field in storage["Index"]:
            rows = storage["Index"][field][()]
            values = storage["Data"][field] if field in storage["Data"] else storage[field]
            ranges[values.name] = [
                (int(row["Start index"]), int(row["Size"]))
                for row in rows
                if row["Object ID"].decode().strip("{}") in set(map(str, selected_holes))
            ]
    before = hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns
    original = h5py.Dataset.__getitem__
    reads = []

    def guarded(dataset, selection):
        if dataset.name in ranges:
            assert isinstance(selection, slice), (dataset.name, selection)
            start, stop, step = selection.indices(len(dataset))
            assert step == 1
            assert any(start >= left and stop <= left + size for left, size in ranges[dataset.name]), (
                dataset.name, selection,
            )
            reads.append(dataset.name)
        assert str(point_uid) not in dataset.name
        assert str(unrelated_group_uid) not in dataset.name or dataset.name.endswith(
            ("/Concatenated object IDs", "/Attributes", "/Attributes Jsons")
        )
        return original(dataset, selection)

    with monkeypatch.context() as context:
        context.setattr(h5py.Dataset, "__getitem__", guarded)
        def no_direct(*args, **kwargs):
            pytest.fail("Unexpected unguarded read_direct")
        context.setattr(h5py.Dataset, "read_direct", no_direct)
        original_workspace = Workspace.__init__

        def no_source_workspace(workspace, h5file=None, **kwargs):
            assert h5file is None, "Source must not be opened as a Workspace"
            original_workspace(workspace, h5file, **kwargs)

        context.setattr(Workspace, "__init__", no_source_workspace)
        result = read_geoh5_entities(path, selection)
    assert reads
    if selection_kind == "group":
        assert len(result) == 1
        assert_converted_equal(result[0], expected_group)
        assert [
            block.user_dict["geoh5"]["source"]["uid"] for block in result[0]
        ] == sorted(map(str, selected_holes))
        converted = list(result[0])
    else:
        converted = list(result)
    assert len(converted) == len(selected_holes)
    by_uid = {block.user_dict["geoh5"]["source"]["uid"]: block for block in converted}
    for uid in selected_holes:
        assert_converted_equal(by_uid[str(uid)], expected[uid])
    actual = by_uid[str(hole_uid)]
    np.testing.assert_array_equal(actual["intervals"][0]["grade"], [4.])
    np.testing.assert_array_equal(actual["intervals"][1]["rock_names"], ["A", "B"])
    np.testing.assert_array_equal(actual["points"][0]["log/channel"], [10., np.nan])
    assert (hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns) == before
    assert read_geoh5_entities(path, point_uid)[0].n_points == 1
    path.unlink()
    assert actual["trace"].copy(deep=True).n_points > 0


@pytest.mark.parametrize("corruption", ["bounds", "overlap", "duplicate", "missing-record"])
def test_concatenated_malformed_storage_closes_handles(tmp_path, monkeypatch, corruption):
    path = tmp_path / "malformed.geoh5"
    with Workspace.create(path) as ws:
        group = DrillholeGroup.create(ws)
        holes = [
            Drillhole.create(
                ws, parent=group, collar=[float(index), 0., 0.],
                surveys=np.array([[0., 0., -90.]]), end_of_hole=10.,
            ).uid for index in range(2)
        ]
        uid = group.uid
    with h5py.File(path, "r+") as file:
        storage = file[f"GEOSCIENCE/Groups/{{{uid}}}/Concatenated Data"]
        rows = storage["Index/Surveys"][()]
        if corruption == "bounds":
            rows[0]["Size"] = 100
        elif corruption == "overlap":
            rows[0]["Start index"] = rows[1]["Start index"]
        elif corruption == "duplicate":
            rows = np.concatenate([rows, rows[:1]])
        else:
            del storage["Attributes Jsons"]
            storage.create_dataset(
                "Attributes Jsons", data=np.array([], dtype=h5py.string_dtype())
            )
        del storage["Index/Surveys"]
        storage["Index"].create_dataset("Surveys", data=rows)
    handles = []
    original = h5py.File.__init__

    def track(file, *args, **kwargs):
        original(file, *args, **kwargs)
        handles.append(file)

    monkeypatch.setattr(h5py.File, "__init__", track)
    with pytest.raises(ValueError):
        read_geoh5_entities(path, holes[0])
    assert handles and all(not file.id.valid for file in handles)
    path.unlink()


@pytest.mark.parametrize("representation", ["composite", "merged"])
def test_concatenated_geometry_only_and_conversion_failure(tmp_path, monkeypatch, representation):
    path = tmp_path / "geometry.geoh5"
    with Workspace.create(path) as ws:
        group = DrillholeGroup.create(ws)
        hole = Drillhole.create(
            ws, parent=group, collar=[1., 2., 100.], end_of_hole=10.,
            surveys=np.array([[0., 0., -90.], [10., 45., -80.]]),
        )
        hole_uid = hole.uid
    with Workspace(path, mode="r") as ws:
        from geoh5vista.drillholes import drillhole_to_vtk

        expected = drillhole_to_vtk(
            ws.get_entity(hole_uid)[0], representation=representation, curve_tolerance=0.001,
        )
    actual = read_geoh5_entities(
        path, hole_uid, drillhole_representation=representation, curve_tolerance=0.001,
    )[0]
    assert_converted_equal(actual, expected)
    handles = []
    original = h5py.File.__init__

    def track(file, *args, **kwargs):
        original(file, *args, **kwargs)
        handles.append(file)

    def fail(*args, **kwargs):
        raise RuntimeError("Injected concatenated conversion failure")

    monkeypatch.setattr(h5py.File, "__init__", track)
    monkeypatch.setattr("geoh5vista.selective.entities_to_vtk", fail)
    with pytest.raises(RuntimeError, match="Injected concatenated"):
        read_geoh5_entities(path, hole_uid)
    assert handles and all(not file.id.valid for file in handles)


def test_concatenated_missing_indexed_payload_warns(tmp_path):
    path = tmp_path / "missing-surveys.geoh5"
    with Workspace.create(path) as ws:
        group = DrillholeGroup.create(ws)
        hole = Drillhole.create(
            ws, parent=group, collar=[1., 2., 100.], end_of_hole=10.,
            surveys=np.array([[0., 0., -90.]]),
        )
        hole.end_of_hole = 10.
        hole_uid, group_uid = hole.uid, group.uid
    with h5py.File(path, "r+") as file:
        del file[f"GEOSCIENCE/Groups/{{{group_uid}}}/Concatenated Data/Surveys"]
    with pytest.warns(UserWarning) as warnings:
        actual = read_geoh5_entities(path, hole_uid)[0]
    messages = [str(warning.message) for warning in warnings]
    assert any("no stored data" in message for message in messages)
    assert any("no stored surveys" in message for message in messages), messages
    assert actual.user_dict["geoh5"]["drillhole"]["survey_source"] == "inferred_vertical"


def test_empty_concatenated_group(tmp_path):
    path = tmp_path / "empty-group.geoh5"
    with Workspace.create(path) as ws:
        uid = DrillholeGroup.create(ws).uid
    blocks = read_geoh5_entities(path, uid)
    assert len(blocks) == 1 and len(blocks[0]) == 0


@pytest.mark.parametrize("failure_phase", ["conversion", "reconstruction"])
def test_input_errors_and_cleanup_on_failure(tmp_path, monkeypatch, failure_phase):
    path = tmp_path / "failure.geoh5"
    with Workspace.create(path) as ws:
        obj = Points.create(ws, vertices=[[1., 2., 3.]])
        uid = obj.uid
    with pytest.raises(ValueError, match="At least one"):
        read_geoh5_entities(path, [])
    with pytest.raises(ValueError, match="not reachable"):
        read_geoh5_entities(path, uuid4())
    with pytest.raises(ValueError):
        read_geoh5_entities(path, "not-a-uuid")
    handles = []
    source_modes = []
    original = h5py.File.__init__

    def track(file, *args, **kwargs):
        original(file, *args, **kwargs)
        handles.append(file)
        if file.filename == str(path):
            source_modes.append(file.mode)

    def fail(*args, **kwargs):
        raise RuntimeError("Injected failure")

    original_fetch = H5Reader.fetch_attributes

    def fail_source(file, *args, **kwargs):
        if file.filename == str(path):
            raise RuntimeError("Injected failure")
        return original_fetch(file, *args, **kwargs)

    monkeypatch.setattr(h5py.File, "__init__", track)
    target = (
        "geoh5vista.selective.entities_to_vtk" if failure_phase == "conversion"
        else "geoh5vista.selective.H5Reader.fetch_attributes"
    )
    monkeypatch.setattr(target, fail if failure_phase == "conversion" else fail_source)
    with pytest.raises(RuntimeError, match="Injected failure"):
        read_geoh5_entities(path, uid)
    assert handles and all(not file.id.valid for file in handles)
    assert source_modes and set(source_modes) == {"r"}
    path.unlink()


def test_root_selection_and_invalid_options(tmp_path):
    path = tmp_path / "root.geoh5"
    with Workspace.create(path) as ws:
        root_uid = ws.root.uid
        point_uid = Points.create(ws, vertices=[[1., 2., 3.]]).uid
    blocks = read_geoh5_entities(path, root_uid)
    assert blocks[0].user_dict["geoh5"]["source"]["uid"] == str(point_uid)
    assert blocks[0].user_dict["geoh5"]["source"]["parent_uid"] == str(root_uid)
    for tolerance in (0., -1., float("inf"), float("nan")):
        with pytest.raises(ValueError, match="curve_tolerance"):
            read_geoh5_entities(path, point_uid, curve_tolerance=tolerance)
    with pytest.raises(ValueError, match="drillhole_representation"):
        read_geoh5_entities(path, point_uid, drillhole_representation="invalid")
    with pytest.raises(FileNotFoundError):
        read_geoh5_entities(tmp_path / "missing.geoh5", point_uid)
