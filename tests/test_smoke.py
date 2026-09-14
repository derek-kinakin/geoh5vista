import geoh5vista


def test_package_exposes_version_string():
    assert isinstance(geoh5vista.__version__, str)
    assert geoh5vista.__version__


def test_public_api_is_importable():
    for name in ("geoh5wrap", "read_geoh5", "vtkwrap", "write_geoh5"):
        assert callable(getattr(geoh5vista, name))
