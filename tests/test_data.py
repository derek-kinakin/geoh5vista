"""Tests for the data module."""

from pathlib import Path

import numpy as np
import pytest
import pyvista
from geoh5py.objects.points import Points
from geoh5py.workspace import Workspace

from geoh5vista.data import add_entity_metadata, restore_entity_metadata

VERTICES = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=float)


@pytest.mark.parametrize("visible", [True, False])
def test_add_entity_metadata_visibility_from_file(tmp_path: Path, visible: bool):
    """Visibility read back from file (np.int8) is recorded as a Python bool."""
    path = tmp_path / "vis.geoh5"
    with Workspace.create(path) as ws:
        pts = Points.create(workspace=ws, name="pts", vertices=VERTICES)
        pts.visible = visible

    with Workspace(path) as ws:
        pts = ws.get_entity("pts")[0]
        result = add_entity_metadata(pyvista.PointSet(VERTICES), pts)

    assert result.user_dict["geoh5"]["display"]["visible"] is visible


@pytest.mark.parametrize("visible", [True, False])
@pytest.mark.parametrize("existing_visual_parameters", [True, False])
def test_restore_entity_metadata_round_trip(
    tmp_path: Path, visible: bool, existing_visual_parameters: bool
):
    source_path = tmp_path / "source.geoh5"
    with Workspace.create(source_path) as ws:
        source = Points.create(workspace=ws, name="source", vertices=VERTICES)
        source.visible = visible
        source.add_default_visual_parameters().colour = [12, 134, 250]
        source_uid = source.uid

    with Workspace(source_path) as ws:
        mesh = add_entity_metadata(pyvista.PointSet(VERTICES), ws.get_entity(source_uid)[0])

    output_path = tmp_path / "output.geoh5"
    with Workspace.create(output_path) as ws:
        target = Points.create(workspace=ws, name="target", vertices=VERTICES)
        target.visible = not visible
        if existing_visual_parameters:
            target.add_default_visual_parameters().colour = [255, 0, 0]
            target.visual_parameters.set_tags(custom="keep")
        target_uid = target.uid
        target_parent = target.parent
        result = restore_entity_metadata(target, mesh)
        assert result is target
        assert target.uid == target_uid
        assert target.uid != source_uid
        assert target.parent is target_parent
        assert len(target.get_data("Visual Parameters")) == 1

    with Workspace(output_path) as ws:
        target = ws.get_entity(target_uid)[0]
        assert target.name == "source"
        assert bool(target.visible) is visible
        assert target.visual_parameters.colour == [12, 134, 250]
        if existing_visual_parameters:
            assert target.visual_parameters.get_tag("Custom").text == "keep"
        np.testing.assert_array_equal(target.vertices, VERTICES)


def test_restore_entity_metadata_explicit_name(tmp_path: Path):
    mesh = pyvista.PointSet(VERTICES)
    mesh.user_dict["geoh5"] = {
        "schema_version": 1,
        "display": {"name": "stored"},
    }
    with Workspace.create(tmp_path / "name.geoh5") as ws:
        target = Points.create(workspace=ws, name="target", vertices=VERTICES)
        restore_entity_metadata(target, mesh, name="explicit")
        assert target.name == "explicit"


@pytest.mark.parametrize(
    ("metadata", "expected_visible"),
    [
        (None, True),
        ({"schema_version": 1}, True),
        ({"schema_version": 1, "display": {}}, True),
        ({"schema_version": 1, "display": {"visible": False}}, False),
    ],
)
def test_restore_entity_metadata_missing_fields(
    tmp_path: Path, metadata, expected_visible: bool
):
    mesh = pyvista.PointSet(VERTICES)
    if metadata is not None:
        mesh.user_dict["geoh5"] = metadata
    with Workspace.create(tmp_path / "partial.geoh5") as ws:
        target = Points.create(workspace=ws, name="target", vertices=VERTICES)
        target.visible = True
        result = restore_entity_metadata(target, mesh)
        assert result is target
        assert target.name == "target"
        assert target.visible is expected_visible
        assert target.visual_parameters is None


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (None, "dictionary"),
        ({}, "schema_version"),
        ({"schema_version": 2}, "schema_version"),
        ({"schema_version": True}, "schema_version"),
        ({"schema_version": 1.0}, "schema_version"),
        ({"schema_version": 1, "display": None}, "display"),
        ({"schema_version": 1, "display": {"name": None}}, "name"),
        ({"schema_version": 1, "display": {"visible": 0}}, "visible"),
        ({"schema_version": 1, "display": {"colour": "black"}}, "colour"),
        ({"schema_version": 1, "display": {"colour": [0, 1]}}, "colour"),
        ({"schema_version": 1, "display": {"colour": [0, -1, 255]}}, "colour"),
        ({"schema_version": 1, "display": {"colour": [0, 1, 256]}}, "colour"),
        ({"schema_version": 1, "display": {"colour": [0, 1, 2.0]}}, "colour"),
        ({"schema_version": 1, "display": {"colour": [0, True, 255]}}, "colour"),
        (
            {"schema_version": 1, "display": {"name": "changed", "visible": False, "colour": []}},
            "colour",
        ),
    ],
)
def test_restore_entity_metadata_invalid_values(tmp_path: Path, metadata, message: str):
    mesh = pyvista.PointSet(VERTICES)
    mesh.user_dict["geoh5"] = metadata
    with Workspace.create(tmp_path / "invalid.geoh5") as ws:
        target = Points.create(workspace=ws, name="target", vertices=VERTICES)
        target.visible = True
        with pytest.raises(ValueError, match=message):
            restore_entity_metadata(target, mesh)
        assert target.name == "target"
        assert target.visible is True
        assert target.visual_parameters is None
