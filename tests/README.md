# Tests for geoh5vista

This directory contains unit tests for the geoh5vista library.

## Structure

Tests are organized as flat modules following the pytest convention:
- `test_blockmodel.py` - Tests for blockmodel module
- `test_curve.py` - Tests for curve module
- `test_data.py` - Tests for data module
- `test_drillholes.py` - Tests for drillholes module
- `test_grid2d.py` - Tests for grid2d module
- `test_points.py` - Tests for points module
- `test_slicer.py` - Tests for slicer module
- `test_surface.py` - Tests for surface module
- `test_utilities.py` - Tests for utilities module
- `test_wrapper.py` - Tests for wrapper module

## Running Tests

From the repository root, run tests with:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_blockmodel.py

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src/geoh5vista --cov-report=html
```

## Writing Tests

The blockmodel, curve, points, and surface modules contain conversion tests;
the remaining modules currently have placeholder tests. Follow these guidelines:

1. **Use descriptive test names** - Start with `test_` prefix
2. **Group related tests** - Keep related conversion cases together
3. **Keep tests focused** - Assert the relevant geometry, data, or metadata
4. **Use fixtures for setup** - For complex setup, consider adding conftest.py later
5. **Test both success and failure paths** - Include tests for error conditions

### Example

```python
def test_conversion_to_pyvista_returns_mesh():
    """Test that conversion returns a valid PyVista mesh."""
    # Arrange
    geoh5_object = ...

    # Act
    mesh = convert_to_pyvista(geoh5_object)

    # Assert
    assert isinstance(mesh, pv.PolyData)
```

## Test Data

Test data files are available in `assets/` directory at the repository root. Use these files for integration tests.
