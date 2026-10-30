"""Tests for the wrapper module."""

from pathlib import Path

import numpy as np
import pytest
import pyvista
from geoh5py.objects.block_model import BlockModel
from geoh5py.objects.curve import Curve
from geoh5py.objects.points import Points
from geoh5py.objects.surface import Surface
from geoh5py.workspace import Workspace

from geoh5vista.wrapper import read_geoh5, vtkwrap, write_geoh5

VERTICES = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=float)

UTM_VERTICES = np.array([
    [650000.123456, 5500000.234567, 1200.345678],
    [650001.123456, 5500000.334567, 1200.445678],
    [650001.223456, 5500001.234567, 1200.545678],
    [650000.223456, 5500001.334567, 1200.645678],
    [650002.123456, 5500002.234567, 1200.745678],
], dtype=np.float64)


def _assert_mesh_unchanged(mesh, original):
    np.testing.assert_array_equal(mesh.points, original.points)
    assert mesh.points.dtype == original.points.dtype
    assert mesh.n_cells == original.n_cells
    for i in range(mesh.n_cells):
        assert mesh.get_cell(i).type == original.get_cell(i).type
        assert mesh.get_cell(i).point_ids == original.get_cell(i).point_ids
    for attribute in ("point_data", "cell_data", "field_data"):
        actual = getattr(mesh, attribute)
        expected = getattr(original, attribute)
        assert list(actual) == list(expected)
        for name in actual:
            np.testing.assert_array_equal(actual[name], expected[name])
    assert mesh.user_dict == original.user_dict
    assert mesh.active_scalars_info == original.active_scalars_info


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("kind", ["surface", "curve", "vertices", "pointset"])
def test_write_geoh5_preserves_utm_vertices(tmp_path: Path, dtype, kind):
    points = UTM_VERTICES[:4].astype(dtype)
    if kind == "surface":
        mesh = pyvista.PolyData(points, faces=[3, 0, 1, 2, 3, 0, 2, 3])
        entity_type = Surface
        cells = np.array([[0, 1, 2], [0, 2, 3]])
    elif kind == "curve":
        mesh = pyvista.PolyData(points, lines=[2, 0, 1, 2, 1, 2, 2, 2, 3])
        entity_type = Curve
        cells = np.array([[0, 1], [1, 2], [2, 3]])
    else:
        mesh = pyvista.PointSet(points) if kind == "pointset" else pyvista.PolyData(points)
        entity_type = Points
        cells = None
    mesh.point_data["sample"] = np.arange(mesh.n_points, dtype=float)
    if mesh.n_cells:
        mesh.cell_data["grade"] = np.arange(mesh.n_cells, dtype=float) + 10
    mesh.user_dict["geoh5"] = {
        "schema_version": 1,
        "display": {"name": "utm", "visible": False, "colour": [12, 34, 56]},
    }
    original = mesh.copy(deep=True)
    path = tmp_path / "utm.geoh5"

    write_geoh5(mesh, path)

    with Workspace(path, mode="r") as ws:
        entity = ws.get_entity("utm")[0]
        assert isinstance(entity, entity_type)
        np.testing.assert_array_equal(entity.vertices, points)
        if cells is not None:
            np.testing.assert_array_equal(entity.cells, cells)
        np.testing.assert_array_equal(entity.get_data("sample")[0].values, mesh["sample"])
        if mesh.n_cells:
            np.testing.assert_array_equal(entity.get_data("grade")[0].values, mesh["grade"])
        assert not entity.visible
        assert list(entity.visual_parameters.colour) == [12, 34, 56]
        assert set(entity.get_data_list()) == (
            {"sample", "grade", "Visual Parameters"}
            if mesh.n_cells else {"sample", "Visual Parameters"}
        )
    _assert_mesh_unchanged(mesh, original)
    assert mesh.points.dtype == dtype


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("kind", ["surface", "curve", "vertices"])
def test_write_geoh5_mixed_cells_preserve_precision_and_selection(tmp_path: Path, dtype, kind):
    points = UTM_VERTICES.astype(dtype)
    if kind == "surface":
        mesh = pyvista.PolyData(points, faces=[3, 1, 3, 4, 4, 0, 1, 2, 3])
        expected_indices = [1, 3, 4]
        expected_cells = [[0, 1, 2]]
        entity_type = Surface
    elif kind == "curve":
        mesh = pyvista.PolyData(points, lines=[2, 1, 4, 3, 0, 2, 3])
        expected_indices = [1, 4]
        expected_cells = [[0, 1]]
        entity_type = Curve
    else:
        mesh = pyvista.PolyData(points, verts=[1, 4], faces=[3, 0, 1, 2])
        expected_indices = [4]
        expected_cells = None
        entity_type = Points
    mesh.point_data["sample"] = np.arange(mesh.n_points, dtype=float)
    mesh.cell_data["grade"] = np.array([10., 20.])
    mesh.user_dict["geoh5"] = {
        "schema_version": 1,
        "display": {"name": "selected", "visible": False, "colour": [12, 34, 56]},
    }
    original = mesh.copy(deep=True)
    path = tmp_path / "mixed.geoh5"

    write_geoh5(mesh, path)

    with Workspace(path, mode="r") as ws:
        entity = ws.get_entity("selected")[0]
        assert isinstance(entity, entity_type)
        np.testing.assert_array_equal(entity.vertices, points[expected_indices])
        if expected_cells is not None:
            np.testing.assert_array_equal(entity.cells, expected_cells)
        np.testing.assert_array_equal(
            entity.get_data("sample")[0].values, mesh["sample"][expected_indices],
        )
        np.testing.assert_array_equal(entity.get_data("grade")[0].values, [10.])
        assert set(entity.get_data_list()) == {"sample", "grade", "Visual Parameters"}
        assert not entity.visible
        assert list(entity.visual_parameters.colour) == [12, 34, 56]
    _assert_mesh_unchanged(mesh, original)
    assert mesh.points.dtype == dtype


@pytest.mark.parametrize("container", ["single", "list", "multiblock"])
def test_write_geoh5_preserves_ten_centimetre_gap(tmp_path: Path, container):
    lower = pyvista.PolyData(UTM_VERTICES[:3].copy(), faces=[3, 0, 1, 2])
    upper = pyvista.PolyData(
        UTM_VERTICES[:3] + np.array([0., 0.1, 0.]), faces=[3, 0, 1, 2],
    )
    lower.user_dict["gh5_name"] = "lower"
    upper.user_dict["gh5_name"] = "upper"
    path = tmp_path / "gap.geoh5"
    if container == "single":
        write_geoh5(lower, path)
        write_geoh5(upper, path)
    elif container == "list":
        write_geoh5([lower, upper], path)
    else:
        write_geoh5(pyvista.MultiBlock([lower, upper]), path)
    with Workspace(path, mode="r") as ws:
        lower_vertices = ws.get_entity("lower")[0].vertices
        upper_vertices = ws.get_entity("upper")[0].vertices
        np.testing.assert_array_equal(lower_vertices, lower.points)
        np.testing.assert_array_equal(upper_vertices, upper.points)
        np.testing.assert_allclose(
            upper_vertices[:, 1] - lower_vertices[:, 1], 0.1, rtol=0, atol=1e-9,
        )


def test_vtkwrap_preserves_precision_and_existing_id_arrays(tmp_path: Path):
    mesh = pyvista.PolyData(
        UTM_VERTICES.copy(), faces=[3, 1, 3, 4, 4, 0, 1, 2, 3],
    )
    mesh.point_data["vtkOriginalPointIds"] = np.arange(5) + 100
    mesh.cell_data["vtkOriginalCellIds"] = np.array([200, 201])
    mesh.set_active_scalars("vtkOriginalPointIds")
    mesh.user_dict["gh5_name"] = "direct"
    original = mesh.copy(deep=True)
    path = tmp_path / "direct.geoh5"

    with Workspace.create(path) as ws:
        vtkwrap(mesh, ws, name="direct")

    with Workspace(path, mode="r") as ws:
        entity = ws.get_entity("direct")[0]
        np.testing.assert_array_equal(entity.vertices, UTM_VERTICES[[1, 3, 4]])
        np.testing.assert_array_equal(entity.cells, [[0, 1, 2]])
        np.testing.assert_array_equal(
            entity.get_data("vtkOriginalPointIds")[0].values, [101, 103, 104],
        )
        np.testing.assert_array_equal(
            entity.get_data("vtkOriginalCellIds")[0].values, [200],
        )
        assert set(entity.get_data_list()) == {"vtkOriginalPointIds", "vtkOriginalCellIds"}
    _assert_mesh_unchanged(mesh, original)


@pytest.fixture
def mixed_visibility_workspace(tmp_path: Path) -> Path:
    path = tmp_path / "mixed.geoh5"
    with Workspace.create(path) as ws:
        Points.create(workspace=ws, name="shown", vertices=VERTICES)
        hidden = Points.create(workspace=ws, name="hidden", vertices=VERTICES)
        hidden.visible = False
    return path


def _names(blocks) -> set[str]:
    return {
        blocks[i].user_dict["geoh5"]["display"]["name"]
        for i in range(blocks.n_blocks)
    }


def test_read_geoh5_loads_all_by_default(mixed_visibility_workspace: Path):
    blocks = read_geoh5(mixed_visibility_workspace)
    assert _names(blocks) == {"shown", "hidden"}


def test_read_geoh5_load_only_visible(mixed_visibility_workspace: Path):
    blocks = read_geoh5(mixed_visibility_workspace, load_only_visible=True)
    assert _names(blocks) == {"shown"}
    assert blocks[0].user_dict["geoh5"]["display"]["visible"] is True


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
