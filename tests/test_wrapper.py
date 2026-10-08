"""Tests for the wrapper module."""

from pathlib import Path

import numpy as np
import pytest
import pyvista
from geoh5py.objects.block_model import BlockModel
from geoh5py.objects.points import Points
from geoh5py.workspace import Workspace

from geoh5vista.wrapper import read_geoh5, write_geoh5

VERTICES = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=float)


@pytest.fixture
def mixed_visibility_workspace(tmp_path: Path) -> Path:
    path = tmp_path / "mixed.geoh5"
    with Workspace.create(path) as ws:
        Points.create(workspace=ws, name="shown", vertices=VERTICES)
        hidden = Points.create(workspace=ws, name="hidden", vertices=VERTICES)
        hidden.visible = False
    return path


def _names(blocks) -> set[str]:
    return {blocks[i].user_dict["gh5_name"] for i in range(blocks.n_blocks)}


def test_read_geoh5_loads_all_by_default(mixed_visibility_workspace: Path):
    blocks = read_geoh5(mixed_visibility_workspace)
    assert _names(blocks) == {"shown", "hidden"}


def test_read_geoh5_load_only_visible(mixed_visibility_workspace: Path):
    blocks = read_geoh5(mixed_visibility_workspace, load_only_visible=True)
    assert _names(blocks) == {"shown"}
    assert blocks[0].user_dict["gh5_visible"] is True


def test_read_geoh5_variable_spacing_returns_structured_grid(tmp_path: Path):
    path = tmp_path / "variable.geoh5"
    with Workspace.create(path) as ws:
        BlockModel.create(
            ws, name="variable",
            u_cell_delimiters=np.array([0.0, 1.0, 3.0]),
            v_cell_delimiters=np.array([0.0, 1.0, 2.0]),
            z_cell_delimiters=np.array([0.0, 1.0, 2.0]),
        )
    assert isinstance(read_geoh5(path)["variable"], pyvista.StructuredGrid)


def test_write_geoh5_structured_grid(tmp_path: Path):
    grid = pyvista.RectilinearGrid(
        np.array([0.0, 1.0, 3.0]),
        np.array([0.0, 2.0, 5.0, 9.0]),
        np.array([0.0, 1.0, 4.0]),
    ).cast_to_structured_grid().rotate_z(30, inplace=False)
    grid.cell_data["grade"] = np.arange(grid.n_cells, dtype=float)
    path = tmp_path / "structured.geoh5"
    write_geoh5(grid, path, entity_name="structured")
    restored = read_geoh5(path)["structured"]
    assert isinstance(restored, pyvista.StructuredGrid)
    np.testing.assert_allclose(restored.points, grid.points, rtol=0, atol=1e-8)
    np.testing.assert_array_equal(restored["grade"], grid["grade"])


@pytest.mark.parametrize("rotation", [0.0, 30.0, -90.0])
def test_rotated_descending_blockmodel_write_read(tmp_path: Path, rotation: float):
    from geoh5vista.blockmodel import blockmodel_to_vtk

    with Workspace.create(tmp_path / "source.geoh5") as ws:
        bm = BlockModel.create(
            ws, name="model", rotation=rotation,
            origin=(650000.123456, 5500000.234567, 1200.345678),
            u_cell_delimiters=np.array([100., 110., 120.]),
            v_cell_delimiters=np.array([-40., -20., 0., 20.]),
            z_cell_delimiters=np.array([-50., -55., -60., -65., -70.]),
        )
        bm.add_data({
            "density": {
                "association": "CELL", "values": np.arange(bm.n_cells, dtype=float),
            },
        })
        mesh = blockmodel_to_vtk(bm)
    destination = tmp_path / "roundtrip.geoh5"
    write_geoh5(mesh, destination)
    restored = read_geoh5(destination)["model"]
    np.testing.assert_allclose(
        restored.cell_centers().points, mesh.cell_centers().points,
        rtol=0, atol=1e-8,
    )
    np.testing.assert_array_equal(restored["density"], mesh["density"])
