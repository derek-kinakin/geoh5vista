"""Tests for the label module."""

from pathlib import Path

import h5py
import numpy as np
import pytest
import pyvista
from geoh5py.objects.label import Label
from geoh5py.workspace.workspace import Workspace

from geoh5vista.label import get_label_text, label_geom_to_vtk, label_to_vtk
from geoh5vista.wrapper import geoh5wrap, read_geoh5

LABEL_POSITION = (10.0, 20.0, 30.0)
TARGET_POSITION = (1.5, 2.5, 3.5)
TARGET_ID = "{e8b05ac6-b434-4347-9aab-7c078cc0c504}"
LABEL_TEXT = "my label text"
VISUAL_PARAMETERS_XML = (
    '<IParameterList Version="1.0">\n'
    " <SavePreferenceButton>[NO STRING REPRESENTATION]</SavePreferenceButton>\n"
    " <Colour>4294945407</Colour>\n"
    " <Transparency>0</Transparency>\n"
    f" <Text>{LABEL_TEXT}</Text>\n"
    ' <Font>{\n    "bold": "0",\n    "font_name": "Arial",\n'
    '    "italic": "0",\n    "size": "10"\n}\n</Font>\n'
    "</IParameterList>\n"
)
XYZ_DTYPE = np.dtype([("x", "<f8"), ("y", "<f8"), ("z", "<f8")])


def _write_label_file(path: Path, *, with_positions: bool = True) -> None:
    with Workspace.create(path) as ws:
        label = Label.create(workspace=ws, name="Label1")
        vp = label.add_default_visual_parameters()
        vp.values = VISUAL_PARAMETERS_XML
        uid = label.uid

    if with_positions:
        # geoh5py does not write label positions, so inject them as Geoscience ANALYST does.
        with h5py.File(path, "r+") as f:
            obj = f[f"GEOSCIENCE/Objects/{{{uid}}}"]
            obj.attrs["Label position"] = np.array(LABEL_POSITION, dtype=XYZ_DTYPE)
            obj.attrs["Target position"] = np.array(TARGET_POSITION, dtype=XYZ_DTYPE)
            obj.attrs["Target object id"] = TARGET_ID


@pytest.fixture
def label_path(tmp_path: Path) -> Path:
    path = tmp_path / "labels.geoh5"
    _write_label_file(path)
    return path


@pytest.fixture
def geoh5_label(label_path: Path):
    with Workspace(label_path, mode="r") as ws:
        yield ws.get_entity("Label1")[0]


def test_label_geom_to_vtk_points(geoh5_label: Label):
    result = label_geom_to_vtk(geoh5_label)
    assert isinstance(result, pyvista.PolyData)
    np.testing.assert_allclose(result.points, [LABEL_POSITION, TARGET_POSITION])


def test_label_geom_to_vtk_single_line(geoh5_label: Label):
    result = label_geom_to_vtk(geoh5_label)
    assert result.n_cells == 1
    np.testing.assert_array_equal(result.lines, [2, 0, 1])


def test_get_label_text(geoh5_label: Label):
    assert get_label_text(geoh5_label) == LABEL_TEXT


def test_label_to_vtk_metadata(geoh5_label: Label):
    result = label_to_vtk(geoh5_label)
    display = result.user_dict["geoh5"]["display"]
    assert display["name"] == "Label1"
    assert display["colour"] == [255, 170, 127]
    assert result.user_dict["geoh5"]["source"]["entity_type"] == "Label"
    assert result.user_dict["geoh5"]["label"] == LABEL_TEXT


def test_geoh5wrap_dispatches_label(geoh5_label: Label):
    result = geoh5wrap(geoh5_label)
    assert result.user_dict["geoh5"]["source"]["entity_type"] == "Label"


def test_read_geoh5_includes_labels(label_path: Path):
    result = read_geoh5(label_path, mode="r")
    assert "Label1" in result.keys()
    np.testing.assert_allclose(result["Label1"].points, [LABEL_POSITION, TARGET_POSITION])


def test_label_missing_positions_raises(tmp_path: Path):
    path = tmp_path / "no_positions.geoh5"
    _write_label_file(path, with_positions=False)
    with Workspace(path, mode="r") as ws:
        label = ws.get_entity("Label1")[0]
        with pytest.raises(ValueError, match="Label position"):
            label_to_vtk(label)
