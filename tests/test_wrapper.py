"""Tests for the wrapper module."""

from pathlib import Path

import numpy as np
import pytest
from geoh5py.objects.points import Points
from geoh5py.workspace import Workspace

from geoh5vista.wrapper import read_geoh5

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
