---
name: test-protocol
description: >
  Test methodology for IDL→Python converted code.
  Defines the test tiers, data-acquisition strategy, numerical
  comparison criteria, and parallel test execution.
  Keywords: testing, validation, pytest, numerical comparison, tolerance,
  test data, FITS, synthetic data, parallel testing,
  unit tests, integration tests, syntax validation
---

# Test-Protocol — IDL→Python Conversion Test Methodology

> **[Parity harness note]** In this harness, **the authority that decides equivalence is not this
> document but the `parity-protocol` skill + `tools/compare_probes.py` (comparison against the oracle run).**
> Every "expected value" in the methodology below is replaced by an oracle probe (.sav) (see the
> Parity section of the test-engineer agent); this document applies only to the Phase 6 regression tests (pytest setup, parallel execution, edge cases).
> For numerical tolerance thresholds as well, `{work_path}/policy.yaml` takes precedence.

## Overview

A test methodology for verifying that the converted Python code is **functionally equivalent** to the original IDL.
It defines the test tiers, data-acquisition strategy, numerical comparison criteria, and parallel execution methods.

---

## 1. Test Tiers (Test Pyramid)

### Level 0: Syntax Check — for all files

Goal: verify that the converted Python file can be imported

```python
def test_import():
    """Check the module can be imported"""
    import importlib
    module = importlib.import_module('converted.module_name')
    assert module is not None
```

**Decision criterion**: import succeeds = PASS, SyntaxError/ImportError = FAIL

### Level 1: Unit Test — for core functions

Goal: verify that each function's inputs and outputs match the original IDL

```python
def test_function_basic():
    """Verify basic input/output"""
    result = function_name(input_data)
    assert_allclose(result, expected, rtol=1e-5)

def test_function_edge_cases():
    """Verify edge cases"""
    # empty array
    assert function_name(np.array([])).size == 0
    # NaN
    result = function_name(np.array([1.0, np.nan, 3.0]))
    assert np.isnan(result[1])
    # single element
    result = function_name(np.array([42.0]))
    assert_allclose(result, expected_single)
```

**Decision criterion**: assert_allclose passes (within tolerance)

### Level 2: Integration Test — for core workflows

Goal: verify that the full workflow chaining multiple functions works

```python
def test_full_workflow():
    """Run the full workflow"""
    # 1. Load data
    data = load_data(test_fits_path)
    # 2. Preprocess
    processed = preprocess(data)
    # 3. Analyze
    result = analyze(processed)
    # 4. Verify result
    assert result.shape == expected_shape
    assert_allclose(result, expected_result, rtol=1e-4)
```

### Level 3: Indexing-specific Test — for multidimensional array functions

Goal: focused check that the column-major → row-major conversion is correct

```python
class TestIndexingConversion:
    """Verify IDL column-major → Python row-major conversion"""

    def test_2d_array_creation(self):
        """Dimension order when creating a 2D array"""
        # IDL: arr = FLTARR(3, 4)  ; 3 cols × 4 rows
        arr = np.zeros((4, 3), dtype=np.float32)
        assert arr.shape == (4, 3)  # (rows, cols)

    def test_2d_indexing(self):
        """2D array indexing"""
        arr = np.arange(12).reshape(4, 3)
        # IDL: arr[col, row]
        # Python: arr[row, col]
        assert arr[2, 1] == 7  # row=2, col=1

    def test_reform(self):
        """REFORM → reshape dimension order"""
        data = np.arange(24)
        # IDL: REFORM(data, 2, 3, 4)
        result = data.reshape((4, 3, 2))  # reverse the order
        assert result.shape == (4, 3, 2)

    def test_total_axis(self):
        """TOTAL → np.sum axis conversion"""
        arr = np.arange(12).reshape(3, 4)
        # IDL: TOTAL(arr, 1) ; sum along the first dimension (column)
        result = np.sum(arr, axis=-1)  # last axis
        assert result.shape == (3,)

    def test_where_return_value(self):
        """WHERE return-value difference"""
        arr = np.array([1, -2, 3, -4, 5])
        idx = np.where(arr > 0)
        count = idx[0].size
        assert count == 3
        # In IDL, WHERE returns -1, but
        # in Python it returns an empty array
        idx_empty = np.where(arr > 100)
        assert idx_empty[0].size == 0
```

---

## 2. Test Data Acquisition Strategy

### Priority

| Rank | Method | Pros | Cons |
|---|---|---|---|
| 1 | **Synthetic data** (NumPy-generated) | No external dependency, fast, reproducible | Lacks real-data characteristics |
| 2 | **Local cache** | No network needed | Requires prior download |
| 3 | **Public data query** (SunPy Fido) | Real data, no authentication needed | Requires network, slow |
| 4 | **Direct JSOC query** | Latest/specific data | Requires email registration |

### Synthetic Data Generation Template

```python
"""Synthetic data generator for testing"""
import numpy as np
from astropy.io import fits
from pathlib import Path


def create_synthetic_fits(filepath, nx=512, ny=512, instrument='AIA'):
    """Create a synthetic FITS file

    Parameters
    ----------
    filepath : str or Path
        Output file path
    nx, ny : int
        Image size
    instrument : str
        Virtual instrument name (recorded in the header)
    """
    # Gaussian noise + circular structure
    y, x = np.mgrid[-ny//2:ny//2, -nx//2:nx//2]
    r = np.sqrt(x**2 + y**2)
    data = np.exp(-r**2 / (2 * (nx//4)**2)) * 1000
    data += np.random.normal(0, 10, (ny, nx))
    data = data.astype(np.float32)

    # header
    header = fits.Header()
    header['NAXIS1'] = nx
    header['NAXIS2'] = ny
    header['CRPIX1'] = nx / 2.0
    header['CRPIX2'] = ny / 2.0
    header['CDELT1'] = 0.6  # arcsec/pixel
    header['CDELT2'] = 0.6
    header['CRVAL1'] = 0.0
    header['CRVAL2'] = 0.0
    header['CTYPE1'] = 'HPLN-TAN'
    header['CTYPE2'] = 'HPLT-TAN'
    header['CUNIT1'] = 'arcsec'
    header['CUNIT2'] = 'arcsec'
    header['INSTRUME'] = instrument
    header['DATE-OBS'] = '2023-01-01T00:00:00.000'
    header['WAVELNTH'] = 171

    fits.writeto(filepath, data, header, overwrite=True)
    return filepath


def create_synthetic_lightcurve(n_points=1000, cadence=12.0):
    """Create a synthetic light curve

    Returns
    -------
    time : np.ndarray
        Time array (seconds)
    flux : np.ndarray
        Flux array
    """
    time = np.arange(n_points) * cadence
    # Baseline level + flare (Gaussian)
    flux = 1e-6 * np.ones(n_points)
    peak_idx = n_points // 2
    sigma = 20
    flare = 1e-4 * np.exp(-(np.arange(n_points) - peak_idx)**2 / (2 * sigma**2))
    flux += flare
    flux += np.random.normal(0, 1e-7, n_points)
    return time, flux


def create_synthetic_spectrum(n_wavelengths=2048, n_pixels=100):
    """Create synthetic spectrum data

    Returns
    -------
    wavelength : np.ndarray
        Wavelength array (Angstrom)
    spectrum : np.ndarray
        Spectrum (n_pixels × n_wavelengths)
    """
    wavelength = np.linspace(1700, 1800, n_wavelengths)
    spectrum = np.zeros((n_pixels, n_wavelengths), dtype=np.float32)
    # Continuum spectrum + emission lines
    for i in range(n_pixels):
        spectrum[i] = 100 * np.exp(-(wavelength - 1750)**2 / (2 * 20**2))
        # emission line
        line_center = 1750 + np.random.normal(0, 2)
        spectrum[i] += 500 * np.exp(-(wavelength - line_center)**2 / (2 * 0.5**2))
        spectrum[i] += np.random.normal(0, 5, n_wavelengths)
    return wavelength, spectrum
```

### Public Data Query Template

```python
"""Download test data using SunPy Fido"""
import astropy.units as u
from sunpy.net import Fido, attrs as a
from pathlib import Path


def download_test_aia(data_dir, wavelength=171):
    """Download one AIA image for testing"""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    result = Fido.search(
        a.Time('2023-01-01 00:00', '2023-01-01 00:01'),
        a.Instrument.aia,
        a.Wavelength(wavelength * u.angstrom),
        a.Sample(12 * u.s)  # only one
    )

    if len(result[0]) > 0:
        downloaded = Fido.fetch(result[0, 0], path=str(data_dir))
        return downloaded[0]
    return None


def download_test_goes(data_dir):
    """Download GOES XRS data for testing"""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    result = Fido.search(
        a.Time('2023-01-01', '2023-01-02'),
        a.Instrument.xrs,
        a.goes.SatelliteNumber(16)
    )

    if len(result[0]) > 0:
        downloaded = Fido.fetch(result[0, 0], path=str(data_dir))
        return downloaded[0]
    return None
```

---

## 3. Numerical Comparison Criteria

### Tolerance Table

| Data type | rtol (relative) | atol (absolute) | When used |
|---|---|---|---|
| float32 operations | 1e-5 | 1e-6 | IDL default precision |
| float64 operations | 1e-10 | 1e-12 | High-precision computation |
| integer operations | 0 | 0 | Exact match |
| Coordinate transforms | 1e-3 | 0.001 arcsec | Unit-conversion error |
| Time conversions | — | 0.001 sec | Time precision |
| Interpolation results | 1e-3 | 1e-4 | Interpolation-algorithm differences |
| FFT results | 1e-5 | 1e-6 | Floating-point accumulation error |

### Comparison Utility

```python
"""Numerical comparison helper"""
import numpy as np
from numpy.testing import assert_allclose, assert_array_equal


def compare_idl_python(python_result, expected, data_type='float32', label=''):
    """Compare IDL-Python output

    Parameters
    ----------
    python_result : array-like
        Output of the converted Python code
    expected : array-like
        Expected output of the original IDL
    data_type : str
        Data type ('float32', 'float64', 'integer')
    label : str
        Comparison description (included in the error message)
    """
    tolerances = {
        'float32': {'rtol': 1e-5, 'atol': 1e-6},
        'float64': {'rtol': 1e-10, 'atol': 1e-12},
        'integer': {'rtol': 0, 'atol': 0},
        'coordinate': {'rtol': 1e-3, 'atol': 1e-3},
        'interpolation': {'rtol': 1e-3, 'atol': 1e-4},
    }

    tol = tolerances.get(data_type, tolerances['float32'])

    if data_type == 'integer':
        assert_array_equal(python_result, expected,
                          err_msg=f"IDL-Python mismatch: {label}")
    else:
        assert_allclose(python_result, expected,
                       rtol=tol['rtol'], atol=tol['atol'],
                       err_msg=f"IDL-Python mismatch: {label}")
```

---

## 4. Parallel Test Execution

### pytest-xdist Approach (recommended)

```bash
# Install
pip install pytest-xdist

# Automatic worker count (number of CPU cores)
pytest tests/ -n auto -v --tb=short

# Specify worker count
pytest tests/ -n 4 -v --tb=short

# Parallelize only specific tests
pytest tests/test_utils.py tests/test_loader.py -n 2
```

### Python concurrent.futures Approach

```python
"""Parallel test runner — alternative when pytest-xdist is not installed"""
import concurrent.futures
import subprocess
import json
from pathlib import Path


def run_single_test(test_file):
    """Run a single test file"""
    result = subprocess.run(
        ['python', '-m', 'pytest', str(test_file),
         '-v', '--tb=short', '--no-header', '-q'],
        capture_output=True, text=True, timeout=300
    )
    return {
        'file': str(test_file),
        'returncode': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'passed': result.returncode == 0
    }


def run_parallel_tests(test_dir, max_workers=None):
    """Run independent test files in parallel"""
    test_files = sorted(Path(test_dir).glob('test_*.py'))
    results = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single_test, f): f for f in test_files}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            status = 'PASS' if result['passed'] else 'FAIL'
            print(f"  [{status}] {result['file']}")
            results.append(result)

    # Summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\nTotal {total} test files: {passed} PASS, {total - passed} FAIL")
    return results
```

---

## 5. conftest.py Template

```python
"""Common pytest configuration and fixtures"""
import pytest
import numpy as np
from pathlib import Path
import sys

# Add the converted/ directory to the Python path
WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE / 'converted'))

TEST_DATA_DIR = WORKSPACE / 'data'


@pytest.fixture(scope='session')
def test_data_dir():
    """Test data directory (created if absent)"""
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TEST_DATA_DIR


@pytest.fixture
def sample_2d_array():
    """2D array for testing"""
    np.random.seed(42)
    return np.random.rand(100, 200).astype(np.float32)


@pytest.fixture
def sample_1d_array():
    """1D array for testing"""
    return np.arange(100, dtype=np.float64)


@pytest.fixture
def sample_fits(test_data_dir):
    """FITS file for testing (synthesized if absent)"""
    from astropy.io import fits

    filepath = test_data_dir / 'sample.fits'
    if not filepath.exists():
        np.random.seed(42)
        data = np.random.rand(512, 512).astype(np.float32)
        header = fits.Header()
        header['NAXIS1'] = 512
        header['NAXIS2'] = 512
        header['INSTRUME'] = 'TEST'
        fits.writeto(filepath, data, header, overwrite=True)
    return filepath


@pytest.fixture
def empty_array():
    """Empty array"""
    return np.array([])


@pytest.fixture
def nan_array():
    """Array containing NaN"""
    return np.array([1.0, np.nan, 3.0, np.nan, 5.0])
```

---

## 6. Test Report Format

```markdown
# Test Result Report

## Execution Environment
- Python: {version}
- NumPy: {version}
- pytest: {version}
- Run timestamp: {timestamp}

## Overall Summary
| Item | Value |
|---|---|
| Modules under test | N |
| Total test cases | K |
| PASS | P ({P/K*100:.1f}%) |
| FAIL | F |
| SKIP | S |
| Run time | {total_time:.1f}s |

## Results by Tier

### Level 0: Syntax Check
| Module | Importable | Notes |
|---|---|---|
| module_a.py | OK | |
| module_b.py | FAIL | NameError: 'xyz' is not defined |

### Level 1: Unit Tests
| Module | Test count | PASS | FAIL | Notes |
|---|---|---|---|---|
| module_a.py | 12 | 12 | 0 | |
| module_b.py | 8 | 6 | 2 | 2 indexing cases |

### Level 2: Integration Tests
| Workflow | Result | Run time | Notes |
|---|---|---|---|
| full_pipeline | PASS | 3.2s | |

### Level 3: Indexing-specific
| Check item | Result | Notes |
|---|---|---|
| 2D array creation | PASS | |
| 2D indexing | PASS | |
| REFORM→reshape | FAIL | dimension order not transposed |
| TOTAL→sum axis | PASS | |
| WHERE return value | PASS | |

## FAIL Details

### module_b::test_array_indexing
- **Expected**: shape (4, 3)
- **Actual**: shape (3, 4)
- **Cause**: converted FLTARR(3, 4) → np.zeros((3, 4)) (order transposition omitted)
- **Suggested fix**: change to np.zeros((4, 3))

## Test Data Usage
| Data | Source | Purpose |
|---|---|---|
| sample.fits | Synthetic (NumPy) | FITS I/O test |
| lightcurve.npz | Synthetic (NumPy) | Time-series processing test |
```
