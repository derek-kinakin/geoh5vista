"""Grid2D cell geometry, data alignment, and import/export integration."""

import numpy as np
import pytest
import pyvista
from geoh5py.objects import Grid2D
from geoh5py.shared.utils import xy_rotation_matrix, yz_rotation_matrix
from geoh5py.workspace import Workspace

from geoh5vista import catalog_geoh5, read_geoh5, read_geoh5_entities, write_geoh5
from geoh5vista.grid2d import (
    grid2d_geom_to_vtk,
    grid2d_to_vtk,
    vtk_geom_to_grid2d,
    vtk_to_grid2d,
)

ORIGIN = (650000.123456, 5500000.234567, 1200.345678)


@pytest.mark.parametrize("shape", [(3, 4), (1, 4), (3, 1), (1, 1)])
@pytest.mark.parametrize(
    "rotation,dip", [(0.0, 0.0), (30.0, 20.0), (-35.0, -40.0), (90.0, 90.0)]
)
@pytest.mark.parametrize("signs", [(1, 1), (-1, 1), (1, -1), (-1, -1)])
def test_geometry_and_data_round_trip(tmp_path, shape, rotation, dip, signs):
    with Workspace.create(tmp_path / "source.geoh5") as ws:
        grid = Grid2D.create(
            ws,
            name="grid",
            origin=ORIGIN,
            rotation=rotation,
            dip=dip,
            u_count=shape[0],
            v_count=shape[1],
            u_cell_size=10.0 * signs[0],
            v_cell_size=20.0 * signs[1],
        )
        values = np.arange(grid.n_cells, dtype=float) + 0.25
        grid.add_data({"grade": {"association": "CELL", "values": values}})
        grid.visible = False
        grid.add_default_visual_parameters()
        grid.visual_parameters.colour = [12, 34, 56]
        expected = grid.centroids.copy()
        mesh = grid2d_to_vtk(grid)
        assert isinstance(mesh, pyvista.ImageData)
        assert mesh.dimensions == (shape[0] + 1, shape[1] + 1, 1)
        assert mesh.n_cells == grid.n_cells
        assert mesh.spacing == (10.0, 20.0, 1.0)
        np.testing.assert_array_equal(mesh.points[0], ORIGIN)
        np.testing.assert_allclose(
            mesh.cell_centers().points, expected, rtol=0, atol=1e-8
        )
        np.testing.assert_array_equal(mesh.cell_data["grade"], values)
        assert not mesh.point_data
        original_points = mesh.points.copy()
        path = tmp_path / "export.geoh5"
        write_geoh5(mesh, path)
        np.testing.assert_array_equal(mesh.points, original_points)
        np.testing.assert_array_equal(mesh.cell_data["grade"], values)
    with Workspace(path, mode="r") as ws:
        restored = ws.get_entity("grid")[0]
        assert isinstance(restored, Grid2D)
        assert restored.shape == shape
        assert not restored.visible
        assert list(restored.visual_parameters.colour) == [12, 34, 56]
        np.testing.assert_allclose(restored.centroids, expected, rtol=0, atol=1e-8)
        np.testing.assert_array_equal(restored.get_data("grade")[0].values, values)
        converted = grid2d_to_vtk(restored)
        np.testing.assert_allclose(converted.points, original_points, rtol=0, atol=1e-8)


def test_public_readers_and_geometry_only(tmp_path):
    path = tmp_path / "readers.geoh5"
    with Workspace.create(path) as ws:
        grid = Grid2D.create(
            ws,
            origin=ORIGIN,
            rotation=30.0,
            vertical=True,
            u_count=2,
            v_count=3,
            u_cell_size=10.0,
            v_cell_size=20.0,
        )
        uid = str(grid.uid)
        expected = grid.centroids.copy()
        geometry = grid2d_geom_to_vtk(grid)
        assert not geometry.cell_data
        grid.add_data(
            {
                "id": {"association": "CELL", "values": np.arange(6, dtype=np.int32)},
                "rock": {
                    "association": "CELL",
                    "type": "REFERENCED",
                    "values": np.array([1, 2, 1, 2, 1, 2], dtype=np.uint32),
                    "value_map": {0: "Unknown", 1: "A", 2: "B"},
                },
            }
        )
    assert catalog_geoh5(path)[0].conversion_supported
    for mesh in (read_geoh5(path, mode="r")[0], read_geoh5_entities(path, [uid])[0]):
        assert mesh.n_cells == 6
        np.testing.assert_allclose(
            mesh.cell_centers().points, expected, rtol=0, atol=1e-8
        )
        np.testing.assert_array_equal(mesh.cell_data["id"], np.arange(6))
        np.testing.assert_array_equal(mesh.cell_data["rock"], [1, 2, 1, 2, 1, 2])
        assert "rock_names" in mesh.cell_data


@pytest.mark.parametrize("normal_sign", [1.0, -1.0])
def test_export_nonzero_extent_and_normal_direction(tmp_path, normal_sign):
    direction = xy_rotation_matrix(np.deg2rad(30.0)) @ yz_rotation_matrix(
        np.deg2rad(120.0)
    )
    direction[:, 2] *= normal_sign
    mesh = pyvista.ImageData(
        dimensions=(4, 5, 1),
        origin=ORIGIN,
        spacing=(10.0, 20.0, 1.0),
        direction_matrix=direction,
    )
    mesh.offset = (3, -2, 5)
    mesh.cell_data["grade"] = np.arange(mesh.n_cells, dtype=float)
    with Workspace.create(tmp_path / "offset.geoh5") as ws:
        grid = vtk_to_grid2d(mesh, ws, "offset")
        np.testing.assert_allclose(
            grid.origin.tolist(), mesh.points[0], rtol=0, atol=1e-8
        )
        np.testing.assert_allclose(
            grid.centroids,
            mesh.cell_centers().points,
            rtol=0,
            atol=1e-8,
        )
        np.testing.assert_array_equal(grid.get_data("grade")[0].values, mesh["grade"])


@pytest.mark.parametrize(
    "kind", ["volume", "line", "xz-plane", "tilted-u", "shear", "scale", "nan"]
)
@pytest.mark.parametrize("converter", [vtk_geom_to_grid2d, vtk_to_grid2d])
def test_export_rejects_unrepresentable_geometry(tmp_path, kind, converter):
    mesh = pyvista.ImageData(dimensions=(3, 4, 1))
    if kind == "volume":
        mesh.dimensions = (3, 4, 2)
    elif kind == "line":
        mesh.dimensions = (3, 1, 1)
    elif kind == "xz-plane":
        mesh.dimensions = (3, 1, 4)
    elif kind == "tilted-u":
        mesh.direction_matrix = yz_rotation_matrix(0.3) @ xy_rotation_matrix(0.4)
    elif kind == "shear":
        mesh.direction_matrix = np.array(
            [[1.0, 0.1, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        )
    elif kind == "scale":
        mesh.direction_matrix = np.diag([2.0, 1.0, 1.0])
    else:
        mesh.origin = (np.nan, 0.0, 0.0)
    with Workspace.create(tmp_path / "invalid.geoh5") as ws:
        with pytest.raises(ValueError):
            converter(mesh, ws, "invalid")
        assert ws.get_entity("invalid") == [None]


def test_export_rejects_wrong_type_and_point_data(tmp_path):
    with Workspace.create(tmp_path / "invalid.geoh5") as ws:
        with pytest.raises(TypeError, match="ImageData"):
            vtk_geom_to_grid2d(pyvista.UnstructuredGrid(), ws, "wrong_type")
        mesh = pyvista.ImageData(dimensions=(3, 4, 1))
        mesh.point_data["samples"] = np.arange(mesh.n_points, dtype=float)
        with pytest.raises(ValueError, match="point data"):
            vtk_to_grid2d(mesh, ws, "point_data")
        assert ws.get_entity("point_data") == [None]


@pytest.mark.parametrize("axis", ["u", "v"])
@pytest.mark.parametrize("size", [0.0, np.nan, np.inf])
def test_import_rejects_invalid_spacing(tmp_path, axis, size):
    with Workspace.create(tmp_path / "spacing.geoh5") as ws:
        grid = Grid2D.create(ws, **{f"{axis}_cell_size": size})
        with pytest.raises(ValueError, match="finite.*nonzero"):
            grid2d_geom_to_vtk(grid)


def test_cell_center_point_view(tmp_path):
    with Workspace.create(tmp_path / "centers.geoh5") as ws:
        grid = Grid2D.create(
            ws,
            origin=ORIGIN,
            rotation=30.0,
            dip=20.0,
            u_count=3,
            v_count=4,
            u_cell_size=10.0,
            v_cell_size=20.0,
        )
        values = np.arange(grid.n_cells, dtype=float)
        grid.add_data({"grade": {"association": "CELL", "values": values}})
        mesh = grid2d_to_vtk(grid)
        samples = mesh.cells_to_points()
        np.testing.assert_allclose(samples.points, grid.centroids, rtol=0, atol=1e-8)
        np.testing.assert_array_equal(samples.point_data["grade"], values)
        restored = samples.points_to_cells()
        np.testing.assert_allclose(restored.points, mesh.points, rtol=0, atol=1e-8)
        np.testing.assert_array_equal(restored.cell_data["grade"], values)
