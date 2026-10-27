"""Stored entity visibility must not be replaced by per-view visibility."""

import hashlib
import json
from uuid import UUID, uuid4

import h5py
import numpy as np
import pytest
import pyvista
from geoh5py.groups import ContainerGroup, DrillholeGroup
from geoh5py.objects import (
    BlockModel,
    Curve,
    Drillhole,
    Grid2D,
    Label,
    Points,
    Slicer,
    Surface,
)
from geoh5py.workspace import Workspace

from geoh5vista import catalog_geoh5, geoh5wrap, read_geoh5
from geoh5vista.data import add_entity_metadata
from geoh5vista.visibility import entity_visibility, project_group, stored_visibility
from geoh5vista.wrapper import GEOH5WRAPPERS, entities_to_vtk


def _key(uid):
    return "{" + str(uid) + "}"


def _create_entity(ws, kind):
    vertices = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    if kind == "Points":
        return Points.create(ws, name="entity", vertices=vertices)
    if kind == "Curve":
        return Curve.create(ws, name="entity", vertices=vertices)
    if kind == "Surface":
        return Surface.create(
            ws,
            name="entity",
            vertices=vertices,
            cells=np.array([[0, 1, 2]], dtype="uint32"),
        )
    if kind == "Grid2D":
        return Grid2D.create(ws, name="entity", u_count=2, v_count=2)
    if kind == "BlockModel":
        return BlockModel.create(
            ws,
            name="entity",
            u_cell_delimiters=np.array([0.0, 1.0, 2.0]),
            v_cell_delimiters=np.array([0.0, 1.0]),
            z_cell_delimiters=np.array([0.0, 1.0]),
        )
    if kind == "Label":
        return Label.create(ws, name="entity")
    if kind == "Slicer":
        entity = Slicer.create(ws, name="entity")
        entity.add_default_visual_parameters().values = (
            "<IParameterList><Position>{0,0,0}</Position>"
            "<Orientation>{0,0,1}</Orientation></IParameterList>"
        )
        return entity
    group = DrillholeGroup.create(ws, name="group")
    hole = Drillhole.create(
        ws,
        parent=group,
        name="hole",
        collar=[0.0, 0.0, 10.0],
        end_of_hole=10.0,
        surveys=np.array([[0.0, 0.0, -90.0], [10.0, 0.0, -90.0]]),
    )
    return group if kind == "DrillholeGroup" else hole


def _set_visibility(project, uid, attribute, views, *, family="Objects"):
    entity = project[family][_key(uid)]
    if "Visible" in entity.attrs:
        del entity.attrs["Visible"]
    if attribute is not None:
        entity.attrs["Visible"] = attribute
    if views is not None:
        entity.create_dataset(
            "Visible",
            data=np.array(
                [(_key(uuid4()).encode(), int(value)) for value in views],
                dtype=[("ViewID", "S38"), ("Visible", "i1")],
            ),
        )


def _snapshot(path):
    return hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns


def _metadata_for(data, uid):
    metadata = data.user_dict.get("geoh5")
    if metadata is not None and metadata["source"]["uid"] == str(uid):
        yield metadata
    if isinstance(data, pyvista.MultiBlock):
        for child in data:
            yield from _metadata_for(child, uid)


def _assert_visibility(data, uid, expected):
    matches = list(_metadata_for(data, uid))
    assert matches
    assert all(meta["display"]["visible"] is expected for meta in matches)


def _assert_entry_points(path, uid, expected):
    before = _snapshot(path)
    entry = next(item for item in catalog_geoh5(path) if item.uid == str(uid))
    assert entry.visible is expected
    _assert_visibility(read_geoh5(path, mode="r"), uid, expected)
    filtered = read_geoh5(path, mode="r", load_only_visible=True)
    assert bool(list(_metadata_for(filtered, uid))) is expected
    with Workspace(path, mode="r") as ws:
        entity = ws.get_entity(uid)[0]
        _assert_visibility(geoh5wrap(entity), uid, expected)
        _assert_visibility(GEOH5WRAPPERS[type(entity).__name__](entity), uid, expected)
        selected = entities_to_vtk([entity])
        _assert_visibility(selected, uid, expected)
        selected = entities_to_vtk([entity], load_only_visible=True)
        assert bool(list(_metadata_for(selected, uid))) is expected
        assert ws.geoh5.id.valid
    assert _snapshot(path) == before


@pytest.mark.parametrize("attribute", [True, False, None])
@pytest.mark.parametrize(
    "views",
    [
        None,
        [True],
        [False],
        [True, True],
        [False, False],
        [True, False],
        [False, True],
        [],
    ],
)
def test_points_visibility_parity(tmp_path, attribute, views):
    path = tmp_path / "visibility.geoh5"
    with Workspace.create(path) as ws:
        uid = _create_entity(ws, "Points").uid
    with h5py.File(path, "r+") as file:
        _set_visibility(file["GEOSCIENCE"], uid, attribute, views)
    _assert_entry_points(path, uid, True if attribute is None else attribute)


@pytest.mark.parametrize(
    "kind",
    ["Curve", "Surface", "Grid2D", "BlockModel", "Label", "Slicer", "DrillholeGroup"],
)
@pytest.mark.parametrize(
    "attribute, view",
    [
        (True, False),
        (False, True),
        (True, True),
        (False, False),
        (None, False),
        (None, True),
    ],
)
def test_non_points_and_group_visibility(tmp_path, kind, attribute, view):
    path = tmp_path / "types.geoh5"
    with Workspace.create(path) as ws:
        uid = _create_entity(ws, kind).uid
    with h5py.File(path, "r+") as file:
        project = file["GEOSCIENCE"]
        _set_visibility(
            project,
            uid,
            attribute,
            [view],
            family="Groups" if kind == "DrillholeGroup" else "Objects",
        )
        if kind == "Label":
            xyz = np.dtype([("x", "f8"), ("y", "f8"), ("z", "f8")])
            entity = project["Objects"][_key(uid)]
            entity.attrs["Label position"] = np.array((0.0, 0.0, 0.0), dtype=xyz)
            entity.attrs["Target position"] = np.array((1.0, 1.0, 1.0), dtype=xyz)
    _assert_entry_points(path, uid, True if attribute is None else attribute)


def _edit_concatenated_visibility(project, group_uid, uid, attribute):
    storage = project["Groups"][_key(group_uid)]["Concatenated Data"]
    modern = "Attributes Jsons" in storage
    label = "Attributes Jsons" if modern else "Attributes"
    dataset = storage[label]
    if modern:
        records = [json.loads(value) for value in dataset[()]]
    else:
        raw = dataset[()]
        if isinstance(raw, np.ndarray):
            raw = raw.item()
        records = json.loads(raw)["Attributes"]
    record = next(item for item in records if UUID(item["ID"]) == uid)
    record.pop("Visible", None)
    if attribute is not None:
        record["Visible"] = attribute
    if modern:
        dataset[:] = [json.dumps(item) for item in records]
    else:
        dataset[()] = json.dumps({"Attributes": records})


@pytest.mark.parametrize("version", [1.0, 2.0, 2.1])
@pytest.mark.parametrize("attribute", [True, False, None])
def test_drillhole_visibility_and_child_filtering(tmp_path, version, attribute):
    path = tmp_path / "holes.geoh5"
    with Workspace(path, version=version) as ws:
        hole = _create_entity(ws, "Drillhole")
        uid, group_uid = hole.uid, hole.parent.uid
    with h5py.File(path, "r+") as file:
        project = file["GEOSCIENCE"]
        if version == 1:
            _set_visibility(project, uid, attribute, [False, True])
        else:
            _edit_concatenated_visibility(project, group_uid, uid, attribute)
    _assert_entry_points(path, uid, True if attribute is None else attribute)


def test_hidden_parent_does_not_change_child_state(tmp_path):
    path = tmp_path / "parent.geoh5"
    with Workspace.create(path) as ws:
        parent = ContainerGroup.create(ws, visible=False)
        child = Points.create(
            ws, name="child", parent=parent, vertices=[[0.0, 0.0, 0.0]]
        )
        uid = child.uid
    with h5py.File(path, "r+") as file:
        _set_visibility(file["GEOSCIENCE"], uid, True, [False])
    _assert_entry_points(path, uid, True)


@pytest.mark.parametrize("version", [1.0, 2.0, 2.1])
def test_hidden_drillhole_group_retains_nesting_but_child_metadata_is_visible(
    tmp_path, version
):
    path = tmp_path / "hidden-group.geoh5"
    with Workspace(path, version=version) as ws:
        hole = _create_entity(ws, "Drillhole")
        uid, group_uid = hole.uid, hole.parent.uid
        hole.parent.visible = False
    before = _snapshot(path)
    entries = {item.uid: item for item in catalog_geoh5(path)}
    assert entries[str(uid)].visible is True
    assert entries[str(group_uid)].visible is False
    _assert_visibility(read_geoh5(path, mode="r"), uid, True)
    assert read_geoh5(path, mode="r", load_only_visible=True).n_blocks == 0
    with Workspace(path, mode="r") as ws:
        group = ws.get_entity(group_uid)[0]
        _assert_visibility(
            GEOH5WRAPPERS[type(group).__name__](group, load_only_visible=True),
            uid,
            True,
        )
    assert _snapshot(path) == before


@pytest.mark.parametrize(
    "value", ["false", 1.0, np.array([0, 1]), np.array([], dtype="i1")]
)
def test_malformed_attribute_is_not_missing(tmp_path, value):
    path = tmp_path / "malformed.geoh5"
    with Workspace.create(path) as ws:
        uid = _create_entity(ws, "Points").uid
    with h5py.File(path, "r+") as file:
        _set_visibility(file["GEOSCIENCE"], uid, value, [True])
    before = _snapshot(path)
    with pytest.raises(ValueError, match=f"Entity {uid}.*malformed entity Visible"):
        catalog_geoh5(path)
    for visible_only in (False, True):
        with pytest.raises(ValueError, match=f"Entity {uid}.*malformed entity Visible"):
            read_geoh5(path, mode="r", load_only_visible=visible_only)
    with (
        Workspace(path, mode="r") as ws,
        pytest.raises(ValueError, match=f"Entity {uid}.*malformed entity Visible"),
    ):
        geoh5wrap(ws.get_entity(uid)[0])
    assert _snapshot(path) == before


@pytest.mark.parametrize("version", [2.0, 2.1])
def test_malformed_concatenated_visibility(tmp_path, version):
    path = tmp_path / "malformed-hole.geoh5"
    with Workspace(path, version=version) as ws:
        hole = _create_entity(ws, "Drillhole")
        uid, group_uid = hole.uid, hole.parent.uid
    with h5py.File(path, "r+") as file:
        _edit_concatenated_visibility(file["GEOSCIENCE"], group_uid, uid, [False, True])
    before = _snapshot(path)
    with pytest.raises(ValueError, match="malformed entity Visible"):
        catalog_geoh5(path)
    with pytest.raises(ValueError, match="malformed entity Visible"):
        read_geoh5(path, mode="r")
    assert _snapshot(path) == before


def test_project_name_and_duplicate_entity_names_do_not_determine_identity(tmp_path):
    path = tmp_path / "renamed.geoh5"
    with Workspace.create(path) as ws:
        first = Points.create(ws, name="Renamed", vertices=[[0.0, 0.0, 0.0]])
        second = Points.create(ws, name="Renamed", vertices=[[1.0, 0.0, 0.0]])
        uids = first.uid, second.uid
    with h5py.File(path, "r+") as file:
        file.move("GEOSCIENCE", "Renamed")
        for uid, visible in zip(uids, (False, True), strict=True):
            _set_visibility(file["Renamed"], uid, visible, [not visible])
    _assert_entry_points(path, uids[0], False)
    _assert_entry_points(path, uids[1], True)


def test_project_resolution_rejects_ambiguous_roots(tmp_path):
    path = tmp_path / "ambiguous.geoh5"
    with Workspace.create(path) as ws:
        entity = _create_entity(ws, "Points")
        ws.geoh5.create_group("AAA unrelated")
        with pytest.raises(ValueError, match="Expected one geoh5 project group"):
            entity_visibility(entity)
    with pytest.raises(ValueError, match="Expected one geoh5 project group"):
        catalog_geoh5(path)


def test_missing_entity_group_is_not_missing_attribute(tmp_path):
    with Workspace.create(tmp_path / "missing.geoh5") as ws:
        entity = _create_entity(ws, "Points")
        del ws.geoh5["GEOSCIENCE/Objects"][_key(entity.uid)]
        with pytest.raises(ValueError, match="missing entity group"):
            entity_visibility(entity)


@pytest.mark.parametrize("visible", [True, False])
def test_unsaved_entity_uses_explicit_in_memory_state(visible):
    with Workspace() as ws:
        entity = ws.create_entity(
            Points,
            entity={"vertices": np.array([[0.0, 0.0, 0.0]]), "visible": visible},
            save_on_creation=False,
        )
        assert entity.on_file is False
        mesh = add_entity_metadata(pyvista.PolyData(), entity)
        assert mesh.user_dict["geoh5"]["display"]["visible"] is visible


@pytest.mark.parametrize(
    "value, expected",
    [
        (False, False),
        (True, True),
        (np.int8(0), False),
        (np.uint8(2), True),
        (np.array(0), False),
    ],
)
def test_scalar_visibility_normalization(value, expected):
    assert stored_visibility({"Visible": value}, context="test") is expected


def test_missing_and_explicit_null_are_distinct():
    assert stored_visibility({}, context="test") is True
    with pytest.raises(ValueError, match="malformed entity Visible"):
        stored_visibility({"Visible": None}, context="test")


def test_project_must_be_a_group(tmp_path):
    with h5py.File(tmp_path / "dataset-root.h5", "w") as file:
        file.create_dataset("not a project", data=[1])
        with pytest.raises(ValueError, match="expected an HDF5 group"):
            project_group(file)


@pytest.mark.parametrize("attribute", [True, False, None])
def test_default_writable_mode_preserves_attribute_and_view_records(
    tmp_path, attribute
):
    path = tmp_path / "default-mode.geoh5"
    with Workspace.create(path) as ws:
        uid = _create_entity(ws, "Points").uid
    with h5py.File(path, "r+") as file:
        _set_visibility(file["GEOSCIENCE"], uid, attribute, [False, True])
        entity = file["GEOSCIENCE/Objects"][_key(uid)]
        attributes = dict(entity.attrs)
        views = entity["Visible"][()]
    expected = True if attribute is None else attribute
    _assert_visibility(read_geoh5(path), uid, expected)
    assert (
        bool(list(_metadata_for(read_geoh5(path, load_only_visible=True), uid)))
        is expected
    )
    with h5py.File(path, "r") as file:
        entity = file["GEOSCIENCE/Objects"][_key(uid)]
        assert set(entity.attrs) == set(attributes)
        for key, value in attributes.items():
            np.testing.assert_array_equal(entity.attrs[key], value)
        np.testing.assert_array_equal(entity["Visible"][()], views)


@pytest.mark.parametrize("version", [1.0, 2.0, 2.1])
def test_merged_drillhole_metadata_and_filtering(tmp_path, version):
    path = tmp_path / "merged.geoh5"
    with Workspace(path, version=version) as ws:
        hole = _create_entity(ws, "Drillhole")
        hole_uid, group_uid = hole.uid, hole.parent.uid
    with h5py.File(path, "r+") as file:
        project = file["GEOSCIENCE"]
        _set_visibility(project, group_uid, True, [False], family="Groups")
        if version == 1:
            _set_visibility(project, hole_uid, False, [True])
        else:
            _edit_concatenated_visibility(project, group_uid, hole_uid, False)
    before = _snapshot(path)
    blocks = read_geoh5(path, mode="r", drillhole_representation="merged")
    _assert_visibility(blocks, group_uid, True)
    group = blocks[0].user_dict["geoh5"]
    assert group["drillhole"]["holes"]["0"]["display"]["visible"] is False
    filtered = read_geoh5(
        path, mode="r", drillhole_representation="merged", load_only_visible=True
    )
    _assert_visibility(filtered, group_uid, True)
    assert filtered[0].user_dict["geoh5"]["drillhole"]["holes"] == {}
    assert _snapshot(path) == before


def test_catalog_does_not_read_view_datasets_or_construct_entities(
    tmp_path, monkeypatch
):
    path = tmp_path / "no-view-reads.geoh5"
    with Workspace.create(path) as ws:
        uid = _create_entity(ws, "Points").uid
    with h5py.File(path, "r+") as file:
        _set_visibility(file["GEOSCIENCE"], uid, True, [False, False])
    before = _snapshot(path)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Catalog must not read datasets or construct a workspace for visibility."
        )

    monkeypatch.setattr(Workspace, "__init__", forbidden)
    monkeypatch.setattr(h5py.Dataset, "__getitem__", forbidden)
    monkeypatch.setattr(h5py.Dataset, "read_direct", forbidden)
    monkeypatch.setattr(h5py.Dataset, "__array__", forbidden)
    assert catalog_geoh5(path)[0].visible is True
    assert _snapshot(path) == before
