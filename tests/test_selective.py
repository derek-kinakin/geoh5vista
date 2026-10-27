"""Structural read boundaries for the experimental selective reader."""

import hashlib
from uuid import uuid4

import h5py
import numpy as np
import pytest
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


@pytest.mark.parametrize("version", [2.0, 2.1])
def test_concatenated_selection_rejected_before_payload(tmp_path, monkeypatch, version):
    path = tmp_path / "modern.geoh5"
    with Workspace(path, version=version) as ws:
        group = DrillholeGroup.create(ws)
        hole = Drillhole.create(
            ws, parent=group, collar=[0., 0., 100.],
            surveys=np.array([[0., 0., -90.]]), end_of_hole=10.,
        )
        point = Points.create(ws, vertices=[[1., 2., 3.]])
        hole_uid, group_uid, point_uid = hole.uid, group.uid, point.uid
    original = h5py.Dataset.__getitem__

    def guarded(dataset, selection):
        assert dataset.name.endswith("/Concatenated object IDs"), dataset.name
        return original(dataset, selection)

    with monkeypatch.context() as context:
        context.setattr(h5py.Dataset, "__getitem__", guarded)
        for uid in (hole_uid, group_uid):
            with pytest.raises(NotImplementedError, match="concatenated"):
                read_geoh5_entities(path, uid)
    guard_reads(monkeypatch, [hole_uid])
    assert read_geoh5_entities(path, point_uid)[0].n_points == 1


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
