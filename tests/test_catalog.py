"""Metadata-only discovery and its storage-access boundary."""

import hashlib
import json
import os
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

import h5py
import numpy as np
import pytest
from geoh5py.groups import ContainerGroup, DrillholeGroup, IntegratorDrillholeGroup
from geoh5py.objects import (
    BlockModel,
    Curve,
    Grid2D,
    Label,
    Octree,
    Points,
    Slicer,
    Surface,
)
from geoh5py.objects import Drillhole
from geoh5py.workspace import Workspace

from geoh5vista import EntityMetadata, catalog_geoh5


def _key(uid) -> str:
    return "{" + str(uid) + "}"


@pytest.fixture
def mixed_catalog(tmp_path):
    path = tmp_path / "catalog.geoh5"
    with Workspace.create(path) as ws:
        root_uid = str(ws.root.uid)
        first = Points.create(
            ws,
            uid=UUID(int=10),
            name="same",
            vertices=[[0.0, 0.0, 0.0]],
        )
        first.add_default_visual_parameters().colour = [10, 20, 30]
        first.add_data({"grade": {"values": np.array([3.0]), "association": "VERTEX"}})
        folder = ContainerGroup.create(ws, uid=UUID(int=20), name="Folder")
        folder.visible = False
        nested = Points.create(
            ws,
            uid=UUID(int=1),
            parent=folder,
            name="same",
            vertices=[[1.0, 1.0, 1.0]],
        )
        hidden = Points.create(
            ws,
            uid=UUID(int=30),
            name="hidden",
            vertices=[[2.0, 2.0, 2.0]],
        )
        hidden.visible = False
        unsupported = Octree.create(ws, uid=UUID(int=40), name="octree")
        slicer = Slicer.create(ws, uid=UUID(int=50), name="slicer")
        label = Label.create(ws, uid=UUID(int=60), name="Label \u00e9")
    return (
        path,
        root_uid,
        folder.uid,
        [
            first.uid,
            nested.uid,
            hidden.uid,
            unsupported.uid,
            slicer.uid,
            label.uid,
        ],
    )


def test_catalog_contract_and_hierarchy(mixed_catalog):
    path, root_uid, folder_uid, uids = mixed_catalog
    records = catalog_geoh5(path)
    assert [entry.uid for entry in records] == list(map(str, uids))
    assert [entry.name for entry in records] == [
        "same",
        "same",
        "hidden",
        "octree",
        "slicer",
        "Label \u00e9",
    ]
    assert records[0].parent_uid == root_uid
    assert records[1].parent_uid == str(folder_uid)
    assert str(folder_uid) not in {entry.uid for entry in records}
    assert records[0].colour == (10, 20, 30)
    assert records[1].colour is None
    assert records[1].visible is True  # No inherited visibility.
    assert records[2].visible is False
    assert records[3].entity_type == "Octree"
    assert records[3].conversion_supported is False
    assert "Octree" in records[3].unsupported_reason
    assert records[4].entity_type == "Slicer"
    assert records[5].entity_type == "Label"
    assert set(asdict(records[0])) == {
        "uid",
        "name",
        "entity_type",
        "parent_uid",
        "visible",
        "colour",
        "conversion_supported",
        "unsupported_reason",
    }
    for entry in records:
        assert isinstance(entry, EntityMetadata)
        assert type(entry.visible) is bool
        assert type(entry.conversion_supported) is bool
        assert str(UUID(entry.uid)) == entry.uid
        if entry.entity_type != "Octree":
            assert entry.conversion_supported is True
            assert entry.unsupported_reason is None
    assert catalog_geoh5(str(path)) == records


def test_records_are_immutable_detached_values(mixed_catalog):
    path = mixed_catalog[0]
    records = catalog_geoh5(path)
    with pytest.raises(FrozenInstanceError):
        records[0].name = "changed"
    for entry in records:
        assert all(
            value is None or type(value) in (str, bool, tuple)
            for value in asdict(entry).values()
        )
    serialized = json.dumps([asdict(entry) for entry in records])
    path.unlink()
    assert json.loads(serialized)[0]["colour"] == [10, 20, 30]
    assert records[0].name == "same"


@pytest.mark.parametrize("version", [1.0, 2.0, 2.1])
def test_drillhole_groups_and_children(tmp_path, version):
    path = tmp_path / "holes.geoh5"
    with Workspace(path, version=version) as ws:
        group = DrillholeGroup.create(ws, name="Holes")
        holes = []
        for value in (2, 1):
            hole = Drillhole.create(
                ws,
                parent=group,
                uid=UUID(int=value),
                name="A/B",
                collar=[0.0, 0.0, 100.0],
                end_of_hole=10.0,
                surveys=np.array([[0.0, 0.0, -90.0], [10.0, 0.0, -90.0]]),
            )
            hole.visible = value == 1
            hole.add_data(
                {
                    "grade": {
                        "from-to": np.array([[0.0, 10.0]]),
                        "values": np.array([3.0]),
                    },
                }
            )
            holes.append(hole.uid)
        group_uid = str(group.uid)
    records = catalog_geoh5(path)
    assert [item.uid for item in records] == [group_uid, *sorted(map(str, holes))]
    assert all(item.conversion_supported for item in records)
    assert records[0].entity_type == (
        "DrillholeGroup" if version == 1 else "ConcatenatorDrillholeGroup"
    )
    for item in records[1:]:
        assert item.parent_uid == group_uid
        assert item.name == "A/B"
        assert item.entity_type == (
            "Drillhole" if version == 1 else "ConcatenatedDrillhole"
        )
        assert item.visible is (item.uid == str(UUID(int=1)))


@pytest.mark.parametrize("version", [1.0, 2.0, 2.1])
def test_payload_reads_and_entity_construction_are_forbidden(
    tmp_path, monkeypatch, version
):
    path = tmp_path / "payload.geoh5"
    with Workspace(path, version=version) as ws:
        points = Points.create(ws, vertices=[[0.0, 0.0, 0.0]])
        points.add_default_visual_parameters().colour = [123, 45, 67]
        points.add_data({"grade": {"values": np.array([3.0]), "association": "VERTEX"}})
        Curve.create(ws, vertices=[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        Surface.create(
            ws,
            vertices=[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 0.0, 0.0]],
            cells=np.array([[0, 1, 2]], dtype=np.uint32),
        )
        Grid2D.create(ws, u_count=3, v_count=4)
        BlockModel.create(
            ws,
            u_cell_delimiters=np.array([0.0, 1.0, 3.0]),
            v_cell_delimiters=np.array([0.0, 1.0]),
            z_cell_delimiters=np.array([0.0, 1.0]),
        )
        group = DrillholeGroup.create(ws)
        hole = Drillhole.create(
            ws,
            parent=group,
            collar=[0.0, 0.0, 100.0],
            end_of_hole=10.0,
            surveys=np.array([[0.0, 0.0, -90.0], [10.0, 0.0, -90.0]]),
        )
        hole.add_data(
            {
                "grade": {
                    "from-to": np.array([[0.0, 10.0]]),
                    "values": np.array([3.0]),
                },
            }
        )
        if version > 1:
            visual = hole.add_default_visual_parameters()
            visual.values = np.array(
                [
                    "<IParameterList><Colour>4278850590</Colour></IParameterList>",
                ]
            )
    with h5py.File(path, "r+") as file:
        obj = file["GEOSCIENCE/Objects"][_key(points.uid)]
        del obj["Vertices"]
        obj.create_dataset("Vertices", shape=(100_000_000, 3), dtype="f8", chunks=True)
    before = hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns
    reads = []
    original = h5py.Dataset.__getitem__

    def guarded(dataset, key):
        name = dataset.name
        metadata = (
            name.endswith("/Concatenated object IDs")
            or name.endswith("/Concatenated Data/Attributes")
            or name.endswith("/Concatenated Data/Attributes Jsons")
            or (
                name.endswith("/Data")
                and dataset.parent.attrs.get("Name") == "Visual Parameters"
            )
            or name.endswith("/Concatenated Data/Index/Visual Parameters")
            or name.endswith("/Concatenated Data/Data/Visual Parameters")
        )
        assert metadata, f"Payload read: {name}"
        reads.append(name)
        return original(dataset, key)

    def forbidden(*args, **kwargs):
        pytest.fail("Catalog attempted entity construction or an unguarded array read.")

    monkeypatch.setattr(Workspace, "__init__", forbidden)
    monkeypatch.setattr(h5py.Dataset, "__getitem__", guarded)
    monkeypatch.setattr(h5py.Dataset, "read_direct", forbidden)
    monkeypatch.setattr(h5py.Dataset, "__array__", forbidden)
    records = catalog_geoh5(path)
    assert len(records) == 7
    assert any(item.colour == (123, 45, 67) for item in records)
    assert reads
    assert (
        hashlib.sha256(path.read_bytes()).digest(),
        path.stat().st_mtime_ns,
    ) == before


def test_metadata_matches_converted_objects(tmp_path):
    from geoh5vista import read_geoh5

    path = tmp_path / "parity.geoh5"
    with Workspace.create(path) as ws:
        for value in range(2):
            points = Points.create(ws, name="same", vertices=[[value, 0.0, 0.0]])
            points.visible = bool(value)
            points.add_default_visual_parameters().colour = [value, 20, 30]
    catalog = {item.uid: item for item in catalog_geoh5(path)}
    for block in read_geoh5(path, mode="r"):
        metadata = block.user_dict["geoh5"]
        entry = catalog[metadata["source"]["uid"]]
        assert entry.entity_type == metadata["source"]["entity_type"]
        assert entry.parent_uid == metadata["source"]["parent_uid"]
        assert entry.name == metadata["display"]["name"]
        assert entry.visible == metadata["display"]["visible"]
        assert entry.colour == tuple(metadata["display"]["colour"])


def test_support_comes_from_converter_registry(mixed_catalog, monkeypatch):
    from geoh5vista.constants import CONVERTERS, SUPPORTED
    from geoh5vista.wrapper import GEOH5WRAPPERS

    assert set(SUPPORTED) == set(CONVERTERS) == set(GEOH5WRAPPERS)
    monkeypatch.delitem(CONVERTERS, "Points")
    records = catalog_geoh5(mixed_catalog[0])
    assert all(
        not item.conversion_supported
        for item in records
        if item.entity_type == "Points"
    )


def test_unknown_native_type_is_discoverable_even_with_supported_label(mixed_catalog):
    path, _, _, uids = mixed_catalog
    with h5py.File(path, "r+") as file:
        entity = file["GEOSCIENCE/Objects"][_key(uids[0])]
        unknown = file["GEOSCIENCE/Types/Object types"].create_group(_key(uuid4()))
        unknown.attrs["ID"] = unknown.name.rsplit("/", 1)[1]
        unknown.attrs["Name"] = "Points"
        del entity["Type"]
        entity["Type"] = unknown
    first = catalog_geoh5(path)[0]
    assert first.entity_type == "Points"
    assert first.conversion_supported is False
    assert "No converter" in first.unsupported_reason


def test_disconnected_objects_are_not_cataloged(mixed_catalog):
    path = mixed_catalog[0]
    with h5py.File(path, "r+") as file:
        orphan = file["GEOSCIENCE/Objects"].create_group(_key(uuid4()))
        orphan.attrs["Name"] = "orphan"
    assert len(catalog_geoh5(path)) == 6


def test_empty_valid_workspace(tmp_path):
    path = tmp_path / "empty.geoh5"
    with Workspace.create(path):
        pass
    assert catalog_geoh5(path) == []


@pytest.mark.parametrize("failure", [False, True])
def test_read_only_handle_closes_on_success_and_failure(
    mixed_catalog, monkeypatch, failure
):
    path = mixed_catalog[0]
    if failure:
        with h5py.File(path, "r+") as file:
            del file["GEOSCIENCE/Root"].attrs["ID"]
    opened = []
    original = h5py.File

    def tracked(filename, mode):
        assert Path(filename) == path
        assert mode == "r"
        handle = original(filename, mode)
        opened.append(handle)
        return handle

    monkeypatch.setattr(h5py, "File", tracked)
    if failure:
        with pytest.raises(ValueError, match="Cannot catalog geoh5"):
            catalog_geoh5(path)
    else:
        assert catalog_geoh5(path)
    assert len(opened) == 1
    assert not opened[0].id.valid


@pytest.mark.parametrize("kind", ["missing", "not-hdf5", "not-geoh5"])
def test_invalid_files_raise(tmp_path, kind):
    path = tmp_path / "bad.geoh5"
    if kind == "not-hdf5":
        path.write_text("not hdf5", encoding="ascii")
    elif kind == "not-geoh5":
        with h5py.File(path, "w"):
            pass
    expected = ValueError if kind == "not-geoh5" else OSError
    with pytest.raises(expected):
        catalog_geoh5(path)


@pytest.mark.parametrize(
    "damage", ["type", "name", "uid", "broken-link", "cycle", "xml"]
)
def test_malformed_metadata_raises_with_file_context(mixed_catalog, damage):
    path, _, _, uids = mixed_catalog
    with h5py.File(path, "r+") as file:
        project = file["GEOSCIENCE"]
        entity = project["Objects"][_key(uids[0])]
        if damage == "type":
            del entity["Type"]
        elif damage == "name":
            del entity.attrs["Name"]
        elif damage == "uid":
            entity.attrs["ID"] = "invalid"
        elif damage == "broken-link":
            project["Root/Objects"][_key(uuid4())] = h5py.SoftLink("/missing")
        elif damage == "cycle":
            project["Root/Groups"][_key(project["Root"].attrs["ID"].strip("{}"))] = (
                project["Root"]
            )
        else:
            visual = next(
                child
                for child in entity["Data"].values()
                if child.attrs["Name"] == "Visual Parameters"
            )
            visual["Data"][0] = "not xml"
    with pytest.raises(ValueError, match="Cannot catalog geoh5 file") as error:
        catalog_geoh5(path)
    assert str(path) in str(error.value)


@pytest.mark.parametrize(
    "xml, expected",
    [
        ("<IParameterList/>", None),
        ("<IParameterList><Colour>4278190080</Colour></IParameterList>", (0, 0, 0)),
        (
            "<IParameterList><Colour>4294967295</Colour></IParameterList>",
            (255, 255, 255),
        ),
    ],
)
def test_optional_colour_metadata(mixed_catalog, xml, expected):
    path, _, _, uids = mixed_catalog
    with h5py.File(path, "r+") as file:
        obj = file["GEOSCIENCE/Objects"][_key(uids[0])]
        visual = next(
            child
            for child in obj["Data"].values()
            if child.attrs["Name"] == "Visual Parameters"
        )
        visual["Data"][0] = xml
    assert catalog_geoh5(path)[0].colour == expected


@pytest.mark.parametrize("version", [2.0, 2.1])
@pytest.mark.parametrize("storage_layout", ["nested", "direct"])
def test_concatenated_colours_read_only_display_index_once(
    tmp_path,
    monkeypatch,
    version,
    storage_layout,
):
    path = tmp_path / "colours.geoh5"
    with Workspace(path, version=version) as ws:
        group = DrillholeGroup.create(ws)
        holes = []
        for value in (1, 2):
            hole = Drillhole.create(ws, parent=group, collar=[0.0, 0.0, 0.0])
            visual = hole.add_default_visual_parameters()
            visual.values = np.array(
                [
                    f"<IParameterList><Colour>{0xFF0A141E + value}</Colour></IParameterList>",
                ]
            )
            holes.append(hole.uid)
    if storage_layout == "direct":
        with h5py.File(path, "r+") as file:
            storage = file["GEOSCIENCE/Groups"][_key(group.uid)]["Concatenated Data"]
            storage.move("Data/Visual Parameters", "Visual Parameters")
    reads = []
    original = h5py.Dataset.__getitem__

    def guarded(dataset, key):
        assert dataset.name.endswith(
            (
                "/Concatenated object IDs",
                "/Attributes",
                "/Attributes Jsons",
                "/Visual Parameters",
            )
        ), f"Unexpected payload read: {dataset.name}"
        reads.append(dataset.name)
        return original(dataset, key)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", guarded)
    records = {entry.uid: entry for entry in catalog_geoh5(path)}
    for value, uid in enumerate(holes, 1):
        assert records[str(uid)].colour == (10, 20, 30 + value)
    assert sum(name.endswith("/Index/Visual Parameters") for name in reads) == 1


@pytest.mark.parametrize("version", [2.0, 2.1])
def test_missing_concatenated_colour_is_unavailable(tmp_path, version):
    path = tmp_path / "missing-colour.geoh5"
    with Workspace(path, version=version) as ws:
        group = DrillholeGroup.create(ws)
        hole = Drillhole.create(ws, parent=group, collar=[0.0, 0.0, 0.0])
        hole.add_default_visual_parameters()
    assert catalog_geoh5(path)[1].colour is None


@pytest.mark.parametrize(
    "damage",
    [
        "json",
        "missing-object",
        "duplicate-uid",
        "colour-slice",
        "index-schema",
    ],
)
@pytest.mark.parametrize("version", [2.0, 2.1])
def test_malformed_concatenated_metadata_raises(tmp_path, version, damage):
    path = tmp_path / "broken-concatenation.geoh5"
    with Workspace(path, version=version) as ws:
        group = DrillholeGroup.create(ws)
        hole = Drillhole.create(ws, parent=group, collar=[0.0, 0.0, 0.0])
        visual = hole.add_default_visual_parameters()
        visual.values = np.array(
            ["<IParameterList><Colour>0</Colour></IParameterList>"]
        )
    with h5py.File(path, "r+") as file:
        native_group = file["GEOSCIENCE/Groups"][_key(group.uid)]
        storage = native_group["Concatenated Data"]
        label = "Attributes" if version == 2 else "Attributes Jsons"
        if damage == "json":
            storage[label][0] = "not json"
        elif damage == "missing-object":
            native_group["Concatenated object IDs"][0] = _key(uuid4())
        elif damage == "duplicate-uid":
            if version == 2:
                attributes = json.loads(storage[label][0])
                attributes["Attributes"].append(attributes["Attributes"][0])
                storage[label][0] = json.dumps(attributes)
            else:
                storage[label][1] = storage[label][0]
        elif damage == "colour-slice":
            row = storage["Index/Visual Parameters"][0]
            row["Size"] = 20
            storage["Index/Visual Parameters"][0] = row
        else:
            del storage["Index/Visual Parameters"]
            storage["Index"].create_dataset("Visual Parameters", data=np.array([1.5]))
    with pytest.raises(ValueError, match="Cannot catalog geoh5 file"):
        catalog_geoh5(path)


def test_legacy_concatenated_attributes_scalar_json(tmp_path):
    path = tmp_path / "scalar-json.geoh5"
    with Workspace(path, version=2.0) as ws:
        group = DrillholeGroup.create(ws)
        hole = Drillhole.create(ws, parent=group, collar=[0.0, 0.0, 0.0])
    with h5py.File(path, "r+") as file:
        storage = file["GEOSCIENCE/Groups"][_key(group.uid)]["Concatenated Data"]
        raw = storage["Attributes"][0]
        del storage["Attributes"]
        storage.create_dataset("Attributes", data=raw)
    records = catalog_geoh5(path)
    assert records[1].uid == str(hole.uid)


def test_supported_hole_under_unsupported_integrator_group(tmp_path):
    path = tmp_path / "integrator.geoh5"
    with Workspace.create(path) as ws:
        group = IntegratorDrillholeGroup.create(ws)
        hole = Drillhole.create(ws, parent=group, collar=[0.0, 0.0, 0.0])
    records = catalog_geoh5(path)
    assert len(records) == 1
    assert records[0].uid == str(hole.uid)
    assert records[0].parent_uid == str(group.uid)
    assert records[0].entity_type == "ConcatenatedDrillhole"
    assert records[0].conversion_supported


def test_catalog_import_and_execution_do_not_import_vtk(mixed_catalog):
    code = """
import importlib.abc
import sys
class NoVTK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('pyvista', 'vtk', 'vtkmodules'):
            raise AssertionError('VTK import attempted: ' + fullname)
sys.meta_path.insert(0, NoVTK())
from geoh5vista import EntityMetadata, catalog_geoh5
assert len(catalog_geoh5(sys.argv[1])) == 6
assert 'geoh5vista.wrapper' not in sys.modules
assert 'geoh5vista.data' not in sys.modules
"""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1] / "src"))
    result = subprocess.run(
        [sys.executable, "-c", code, str(mixed_catalog[0])],
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def test_public_conversion_exports_remain_available():
    import geoh5vista
    from geoh5vista import geoh5wrap, read_geoh5, vtkwrap, write_geoh5
    from geoh5vista import wrapper

    for name in ("geoh5wrap", "read_geoh5", "vtkwrap", "write_geoh5"):
        assert getattr(geoh5vista, name) is getattr(wrapper, name)
        assert name in dir(geoh5vista)
    assert all(callable(func) for func in (geoh5wrap, read_geoh5, vtkwrap, write_geoh5))
    with pytest.raises(AttributeError):
        getattr(geoh5vista, "missing")
