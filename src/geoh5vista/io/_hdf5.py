"""Shared HDF5 access and metadata validation."""

from uuid import UUID

import h5py


def project_group(file: h5py.File) -> h5py.Group:
    """Resolve the single project group required by the existing reader."""
    if len(file) != 1:
        raise ValueError("Expected one geoh5 project group.")
    project = file[next(iter(file))]
    if not isinstance(project, h5py.Group):
        raise ValueError(f"{project.name}: expected an HDF5 group.")  # noqa: TRY004
    return project


def text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError(f"Expected text metadata, got {type(value).__name__}.")


def uid(value: object) -> str:
    return str(UUID(text(value)))


def group(parent: h5py.Group, key: str) -> h5py.Group:
    value = parent[key]
    if not isinstance(value, h5py.Group):
        raise ValueError(f"{value.name}: expected an HDF5 group.")  # noqa: TRY004
    return value


def dataset(parent: h5py.Group, key: str) -> h5py.Dataset:
    value = parent[key]
    if not isinstance(value, h5py.Dataset):
        raise ValueError(f"{value.name}: expected an HDF5 dataset.")  # noqa: TRY004
    return value
