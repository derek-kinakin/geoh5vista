"""Tests for the utilities module."""

import numpy as np
import pytest

from geoh5vista.utilities import normalize_visibility


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        (2, True),
        (np.bool_(True), True),
        (np.bool_(False), False),
        (np.int8(1), True),
        (np.int8(0), False),
        (np.uint8(0), False),
        (np.int64(3), True),
        (None, True),
        (np.array(0, dtype=np.int8), False),
        (np.array([0, 0], dtype=np.int8), False),
        (np.array([0, 1], dtype=np.int8), True),
        (np.array([], dtype=np.int8), False),
        ([0, 1], True),
        ([], False),
        ({"Visible": np.array([0, 0], dtype=np.int8)}, False),
        ({"Visible": np.array([1, 0], dtype=np.int8)}, True),
        ({"Visible": np.array([True])}, True),
        ({"Visible": np.int8(0)}, False),
        ({"Visible": False}, False),
        (
            np.array(
                [(b"{view-1}", 0), (b"{view-2}", 0)],
                dtype=[("ViewID", "S36"), ("Visible", np.int32)],
            ),
            False,
        ),
        (
            np.array(
                [(b"{view-1}", 0), (b"{view-2}", 1)],
                dtype=[("ViewID", "S36"), ("Visible", np.int32)],
            ),
            True,
        ),
    ],
)
def test_normalize_visibility(value, expected):
    result = normalize_visibility(value)
    assert result is expected


@pytest.mark.parametrize(
    "value",
    ["yes", 1.0, {"Other": 1}, object(), np.array(["a"])],
)
def test_normalize_visibility_unrecognized_warns_and_is_visible(value):
    with pytest.warns(UserWarning, match="Unrecognized visibility value"):
        assert normalize_visibility(value) is True
