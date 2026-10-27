"""Root-alias reconciliation must be shared, read-only, and payload-selective."""

import hashlib
from uuid import UUID, uuid4

import h5py
import numpy as np
import pytest
from geoh5py.groups import ContainerGroup, DrillholeGroup
from geoh5py.objects import Drillhole, Points
from geoh5py.workspace import Workspace

from geoh5vista import catalog_geoh5, read_geoh5_entities, selective


def key(uid):
    return "{" + str(uid) + "}"


def split_root(project):
    """Split only the synthetic fixture, preserving the indexed group's links."""
    indexed = project["Root"]
    del project["Root"]
    root = project.create_group("Root")
    for label, value in indexed.attrs.items():
        root.attrs[label] = value
    root["Type"] = indexed["Type"]
    for family in ("Groups", "Objects", "Data"):
        root.create_group(family)
    return root, indexed


@pytest.fixture
def root_fixture(tmp_path):
    path = tmp_path / "roots.geoh5"
    with Workspace.create(path) as workspace:
        root_uid = workspace.root.uid
        first = Points.create(
            workspace, uid=UUID(int=10), name="catalog_only", vertices=[[0., 0., 0.]],
        )
        first.add_default_visual_parameters().colour = [10, 20, 30]
        first.visible = False
        grade = first.add_data({
            "grade": {"values": np.array([3.]), "association": "VERTEX"},
        })
        grade_uid = grade.uid
        second = Points.create(
            workspace, uid=UUID(int=20), name="reader_only", vertices=[[1., 1., 1.]],
        )
        orphan = Points.create(
            workspace, uid=UUID(int=30), name="orphan", vertices=[[2., 2., 2.]],
        )
        first_uid, second_uid, orphan_uid = first.uid, second.uid, orphan.uid
    with h5py.File(path, "r+") as file:
        del file["GEOSCIENCE/Root/Objects"][key(orphan_uid)]
    return path, root_uid, first_uid, second_uid, orphan_uid, grade_uid


def instrument(monkeypatch, path):
    reads, handles, modes = [], [], []
    getitem = h5py.Dataset.__getitem__
    read_direct = h5py.Dataset.read_direct
    open_file = h5py.File.__init__
    open_workspace = Workspace.__init__
    allowed = set()

    def check(dataset):
        display = dataset.parent.attrs.get("Name") == "Visual Parameters"
        if not display:
            assert any(key(uid) in dataset.name for uid in allowed), dataset.name
        reads.append(dataset.name)

    def guarded_getitem(dataset, selection):
        check(dataset)
        return getitem(dataset, selection)

    def guarded_direct(dataset, dest, source_sel=None, dest_sel=None):
        check(dataset)
        return read_direct(dataset, dest, source_sel, dest_sel)

    def tracked(file, *args, **kwargs):
        open_file(file, *args, **kwargs)
        handles.append(file)
        if file.filename == str(path):
            modes.append(file.mode)
            assert file.mode == "r"

    def no_source(workspace, h5file=None, **kwargs):
        assert h5file is None, "Source must not be opened as an eager workspace"
        open_workspace(workspace, h5file, **kwargs)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", guarded_getitem)
    monkeypatch.setattr(h5py.Dataset, "read_direct", guarded_direct)
    monkeypatch.setattr(h5py.File, "__init__", tracked)
    monkeypatch.setattr(Workspace, "__init__", no_source)
    return allowed, reads, handles, modes


@pytest.mark.parametrize("layout", ["hardlink", "equivalent", "disjoint", "overlap", "unindexed"])
def test_root_aliases_catalog_reader_parity(root_fixture, monkeypatch, layout):
    path, root_uid, first_uid, second_uid, orphan_uid, grade_uid = root_fixture
    with h5py.File(path, "r+") as file:
        project = file["GEOSCIENCE"]
        if layout not in ("hardlink", "unindexed"):
            root, indexed = split_root(project)
            root["Objects"][key(first_uid)] = project["Objects"][key(first_uid)]
            if layout == "disjoint":
                del indexed["Objects"][key(first_uid)]
            elif layout == "equivalent":
                root["Objects"][key(second_uid)] = project["Objects"][key(second_uid)]
            # /Root attributes win; the indexed root may be an older snapshot.
            root.attrs["Name"] = "Resolved root"
            root.attrs["Visible"] = False
            indexed.attrs["Name"] = "Indexed snapshot"
            indexed.attrs["Visible"] = True
        elif layout == "unindexed":
            del project["Groups"][key(root_uid)]
        else:
            assert project["Root"].id == project["Groups"][key(root_uid)].id
        expected_root = (
            root_uid, str(project["Root"].attrs["Name"]),
            bool(project["Root"].attrs.get("Visible", True)),
        )
    before = hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns
    allowed, reads, handles, modes = instrument(monkeypatch, path)
    roots = []
    convert = selective.entities_to_vtk

    def check_root(entities, **kwargs):
        root = entities[0].workspace.root
        roots.append((root.uid, root.name, root.visible))
        return convert(entities, **kwargs)

    monkeypatch.setattr(selective, "entities_to_vtk", check_root)
    entries = catalog_geoh5(path)
    assert [entry.uid for entry in entries] == [str(first_uid), str(second_uid)]
    assert all(entry.parent_uid == str(root_uid) for entry in entries)
    assert entries[0].visible is False
    assert entries[0].colour == (10, 20, 30)
    assert not any(name.endswith("/Vertices") for name in reads)
    assert str(orphan_uid) not in " ".join(reads)
    with pytest.raises(ValueError, match="not reachable"):
        read_geoh5_entities(path, orphan_uid)
    for entry, xyz in zip(entries, [[0., 0., 0.], [1., 1., 1.]], strict=True):
        allowed.clear()
        allowed.add(UUID(entry.uid))
        if entry.uid == str(first_uid):
            allowed.add(grade_uid)
        start = len(reads)
        block = read_geoh5_entities(path, entry.uid)[0]
        metadata = block.user_dict["geoh5"]
        assert metadata["source"]["uid"] == entry.uid
        assert metadata["source"]["parent_uid"] == entry.parent_uid
        assert metadata["source"]["entity_type"] == entry.entity_type
        assert metadata["display"]["visible"] == entry.visible
        np.testing.assert_array_equal(block.points, [xyz])
        assert any(name.endswith("/Vertices") for name in reads[start:])
        if entry.uid == str(first_uid):
            np.testing.assert_array_equal(block["grade"], [3.])
    allowed.update([first_uid, second_uid, grade_uid])
    result = read_geoh5_entities(path, root_uid)
    assert [block.user_dict["geoh5"]["source"]["uid"] for block in result] == [
        str(first_uid), str(second_uid),
    ]
    assert (hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns) == before
    assert handles and all(not file.id.valid for file in handles)
    assert modes and set(modes) == {"r"}
    assert roots and all(value == expected_root for value in roots)
    path.unlink()
    np.testing.assert_array_equal(result[0].copy(deep=True)["grade"], [3.])


@pytest.mark.parametrize(
    "damage", [
        "root-id", "root-type", "child-id", "child-definition", "parents", "cycle", "nested-cycle",
    ],
)
def test_conflicting_hierarchies_fail_before_payload(root_fixture, monkeypatch, damage):
    path, root_uid, first_uid, _, _, _ = root_fixture
    with h5py.File(path, "r+") as file:
        project = file["GEOSCIENCE"]
        root, indexed = split_root(project)
        root["Objects"][key(first_uid)] = project["Objects"][key(first_uid)]
        if damage == "root-id":
            indexed.attrs["ID"] = key(uuid4())
        elif damage == "root-type":
            del indexed["Type"]
            entity_type = indexed.create_group("Type")
            entity_type.attrs["ID"] = key(uuid4())
            entity_type.attrs["Name"] = "Other type"
        elif damage == "child-id":
            project["Objects"][key(first_uid)].attrs["ID"] = key(uuid4())
        elif damage == "child-definition":
            del root["Objects"][key(first_uid)]
            project.copy(project["Objects"][key(first_uid)], root["Objects"], name=key(first_uid))
        elif damage == "parents":
            # A second parent that is not merely the other root representation.
            folder_uid = uuid4()
            folder = project["Groups"].create_group(key(folder_uid))
            folder.attrs["ID"], folder.attrs["Name"] = key(folder_uid), "Folder"
            folder["Type"] = root["Type"]
            folder.create_group("Objects")[key(first_uid)] = project["Objects"][key(first_uid)]
            indexed["Groups"][key(folder_uid)] = folder
        elif damage == "cycle":
            indexed["Groups"][key(root_uid)] = root
        else:
            folder_uid = uuid4()
            folder = project["Groups"].create_group(key(folder_uid))
            folder.attrs["ID"], folder.attrs["Name"] = key(folder_uid), "Folder"
            folder["Type"] = root["Type"]
            folder.create_group("Groups")[key(folder_uid)] = folder
            indexed["Groups"][key(folder_uid)] = folder
    before = hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns
    _, reads, handles, modes = instrument(monkeypatch, path)
    for reader in (
        lambda: catalog_geoh5(path), lambda: read_geoh5_entities(path, first_uid),
    ):
        with pytest.raises(ValueError, match="hierarchy"):
            reader()
    assert not any(name.endswith("/Vertices") for name in reads)
    assert (hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns) == before
    assert handles and all(not file.id.valid for file in handles)
    assert modes and set(modes) == {"r"}
    path.unlink()


@pytest.mark.parametrize("version", [1.0, 2.0, 2.1])
@pytest.mark.parametrize("nested_side", ["root", "indexed"])
def test_split_roots_nested_groups_and_drillholes(tmp_path, monkeypatch, version, nested_side):
    path = tmp_path / "nested.geoh5"
    channel_owners = {}
    with Workspace(path, version=version) as workspace:
        folder = ContainerGroup.create(workspace, uid=UUID(int=1), name="Folder")
        nested = ContainerGroup.create(workspace, parent=folder, uid=UUID(int=2))
        group = DrillholeGroup.create(workspace, parent=nested, uid=UUID(int=3))
        holes = []
        for value in (5, 4):
            hole = Drillhole.create(
                workspace, parent=group, uid=UUID(int=value), name=f"DH-{value}",
                collar=[float(value), 0., 100.], end_of_hole=10.,
                surveys=np.array([[0., 0., -90.], [10., 45., -80.]]),
            )
            hole.add_data({
                "grade": {"from-to": np.array([[0., 10.]]), "values": np.array([float(value)])},
            })
            holes.append(hole.uid)
            for child in hole.children:
                channel_owners[str(child.uid)] = hole.uid
        point = Points.create(
            workspace, uid=UUID(int=10), name="Root-only", vertices=[[1., 2., 3.]],
        )
        point_uid, group_uid = point.uid, group.uid
    with h5py.File(path, "r+") as file:
        project = file["GEOSCIENCE"]
        root, indexed = split_root(project)
        if nested_side == "indexed":
            root["Objects"][key(point_uid)] = project["Objects"][key(point_uid)]
            del indexed["Objects"][key(point_uid)]
        else:
            root["Groups"][key(folder.uid)] = project["Groups"][key(folder.uid)]
            del indexed["Groups"][key(folder.uid)]
        ranges = {}
        if version > 1:
            storage = project["Groups"][key(group_uid)]["Concatenated Data"]
            for field in storage["Index"]:
                rows = storage["Index"][field][()]
                values = storage["Data"][field] if field in storage["Data"] else storage[field]
                ranges[values.name.rsplit("/", 1)[-1]] = [
                    (UUID(row["Object ID"].decode().strip("{}")),
                     int(row["Start index"]), int(row["Size"]))
                    for row in rows
                ]
    before = hashlib.sha256(path.read_bytes()).digest()
    getitem = h5py.Dataset.__getitem__
    reads = []
    selected = None

    def guard(dataset, selection):
        metadata = dataset.name.endswith((
            "/Concatenated object IDs", "/Attributes", "/Attributes Jsons",
        ))
        if selected is None:
            assert metadata, dataset.name
        elif not metadata:
            if selected == point_uid:
                assert key(point_uid) in dataset.name, dataset.name
            else:
                wanted = set(holes) if selected == group_uid else {selected}
                if version > 1 and "/Index/" not in dataset.name:
                    start, stop, step = selection.indices(len(dataset))
                    assert step == 1
                    assert any(
                        owner in wanted and start >= left and stop <= left + size
                        for owner, left, size in ranges[dataset.name.rsplit("/", 1)[-1]]
                    ), (dataset.name, selection)
                elif version == 1:
                    assert any(key(uid) in dataset.name for uid in wanted) or (
                        channel_owners.get(dataset.parent.attrs.get("ID", "").strip("{}"))
                        in wanted
                    ), dataset.name
        reads.append(dataset.name)
        return getitem(dataset, selection)

    def no_direct(*args, **kwargs):
        pytest.fail("Unexpected unguarded read_direct")

    monkeypatch.setattr(h5py.Dataset, "__getitem__", guard)
    monkeypatch.setattr(h5py.Dataset, "read_direct", no_direct)
    entries = catalog_geoh5(path)
    assert [entry.uid for entry in entries] == [
        str(group_uid), *sorted(map(str, holes)), str(point_uid),
    ]
    for entry in entries:
        selected = UUID(entry.uid)
        block = read_geoh5_entities(path, selected)[0]
        assert block.user_dict["geoh5"]["source"]["uid"] == entry.uid
        assert block.user_dict["geoh5"]["source"]["parent_uid"] == entry.parent_uid
        assert block.user_dict["geoh5"]["source"]["entity_type"] == entry.entity_type
    assert hashlib.sha256(path.read_bytes()).digest() == before
    path.unlink()
