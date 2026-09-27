"""Pytest configuration and shared fixtures for geoh5vista tests."""
import pytest


@pytest.fixture
def sample_data_path():
    """Return path to sample data assets."""
    from pathlib import Path
    return Path(__file__).parent.parent / "assets"
