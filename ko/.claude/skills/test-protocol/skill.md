---
name: test-protocol
description: >
  IDL→Python 변환 코드의 테스트 방법론.
  테스트 계층, 데이터 확보 전략, 수치 비교 기준,
  병렬 테스트 실행법을 정의한다.
  키워드: 테스트, 검증, pytest, 수치 비교, 허용 오차,
  테스트 데이터, FITS, 합성 데이터, 병렬 테스트,
  단위 테스트, 통합 테스트, 구문 검증
---

# Test-Protocol — IDL→Python 변환 테스트 방법론

> **[Parity 하네스 주의]** 이 하네스에서 동등성의 **판정 주체는 이 문서가 아니라
> `parity-protocol` 스킬 + `tools/compare_probes.py`(오라클 실행 대조)다.**
> 아래 방법론의 "기대값"은 모두 오라클 probe(.sav)로 대체되며 (test-engineer 에이전트의
> Parity 절 참조), 이 문서는 Phase 6 회귀 테스트(pytest 구성·병렬 실행·엣지 케이스)에만 적용한다.
> 수치 허용 오차의 기준값도 `{작업경로}/policy.yaml`이 우선한다.

## 개요

변환된 Python 코드가 원본 IDL과 **기능적으로 동등**한지 검증하기 위한 테스트 방법론.
테스트 계층, 데이터 확보 전략, 수치 비교 기준, 병렬 실행 방법을 정의한다.

---

## 1. 테스트 계층 (Test Pyramid)

### Level 0: 구문 검증 (Syntax Check) — 모든 파일 대상

목표: 변환된 Python 파일이 import 가능한지 확인

```python
def test_import():
    """모듈 import 가능 여부 확인"""
    import importlib
    module = importlib.import_module('converted.module_name')
    assert module is not None
```

**판정 기준**: import 성공 = PASS, SyntaxError/ImportError = FAIL

### Level 1: 단위 테스트 (Unit Test) — 핵심 함수 대상

목표: 개별 함수의 입출력이 IDL 원본과 일치하는지 확인

```python
def test_function_basic():
    """기본 입출력 검증"""
    result = function_name(input_data)
    assert_allclose(result, expected, rtol=1e-5)

def test_function_edge_cases():
    """엣지 케이스 검증"""
    # 빈 배열
    assert function_name(np.array([])).size == 0
    # NaN
    result = function_name(np.array([1.0, np.nan, 3.0]))
    assert np.isnan(result[1])
    # 단일 요소
    result = function_name(np.array([42.0]))
    assert_allclose(result, expected_single)
```

**판정 기준**: assert_allclose 통과 (허용 오차 내)

### Level 2: 통합 테스트 (Integration Test) — 핵심 워크플로우 대상

목표: 여러 함수를 연결한 전체 워크플로우가 동작하는지 확인

```python
def test_full_workflow():
    """전체 워크플로우 실행"""
    # 1. 데이터 로드
    data = load_data(test_fits_path)
    # 2. 전처리
    processed = preprocess(data)
    # 3. 분석
    result = analyze(processed)
    # 4. 결과 검증
    assert result.shape == expected_shape
    assert_allclose(result, expected_result, rtol=1e-4)
```

### Level 3: 인덱싱 전용 테스트 — 다차원 배열 함수 대상

목표: column-major → row-major 변환이 정확한지 집중 확인

```python
class TestIndexingConversion:
    """IDL column-major → Python row-major 변환 검증"""

    def test_2d_array_creation(self):
        """2D 배열 생성 시 차원 순서"""
        # IDL: arr = FLTARR(3, 4)  ; 3열 × 4행
        arr = np.zeros((4, 3), dtype=np.float32)
        assert arr.shape == (4, 3)  # (행, 열)

    def test_2d_indexing(self):
        """2D 배열 인덱싱"""
        arr = np.arange(12).reshape(4, 3)
        # IDL: arr[col, row]
        # Python: arr[row, col]
        assert arr[2, 1] == 7  # row=2, col=1

    def test_reform(self):
        """REFORM → reshape 차원 순서"""
        data = np.arange(24)
        # IDL: REFORM(data, 2, 3, 4)
        result = data.reshape((4, 3, 2))  # 순서 뒤집기
        assert result.shape == (4, 3, 2)

    def test_total_axis(self):
        """TOTAL → np.sum 축 변환"""
        arr = np.arange(12).reshape(3, 4)
        # IDL: TOTAL(arr, 1) ; 첫 번째 차원(열)을 따라 합산
        result = np.sum(arr, axis=-1)  # 마지막 축
        assert result.shape == (3,)

    def test_where_return_value(self):
        """WHERE 반환값 차이"""
        arr = np.array([1, -2, 3, -4, 5])
        idx = np.where(arr > 0)
        count = idx[0].size
        assert count == 3
        # IDL에서는 WHERE가 -1을 반환하지만
        # Python에서는 빈 배열을 반환
        idx_empty = np.where(arr > 100)
        assert idx_empty[0].size == 0
```

---

## 2. 테스트 데이터 확보 전략

### 우선순위

| 순위 | 방법 | 장점 | 단점 |
|---|---|---|---|
| 1 | **합성 데이터** (NumPy 생성) | 외부 의존 없음, 빠름, 재현성 | 실제 데이터 특성 부재 |
| 2 | **로컬 캐시** | 네트워크 불필요 | 사전 다운로드 필요 |
| 3 | **공개 데이터 쿼리** (SunPy Fido) | 실제 데이터, 인증 불필요 | 네트워크 필요, 느림 |
| 4 | **JSOC 직접 쿼리** | 최신/특정 데이터 | 이메일 등록 필요 |

### 합성 데이터 생성 템플릿

```python
"""테스트용 합성 데이터 생성기"""
import numpy as np
from astropy.io import fits
from pathlib import Path


def create_synthetic_fits(filepath, nx=512, ny=512, instrument='AIA'):
    """합성 FITS 파일 생성

    Parameters
    ----------
    filepath : str or Path
        출력 파일 경로
    nx, ny : int
        이미지 크기
    instrument : str
        가상 계측기 이름 (헤더에 기록)
    """
    # 가우시안 노이즈 + 원형 구조물
    y, x = np.mgrid[-ny//2:ny//2, -nx//2:nx//2]
    r = np.sqrt(x**2 + y**2)
    data = np.exp(-r**2 / (2 * (nx//4)**2)) * 1000
    data += np.random.normal(0, 10, (ny, nx))
    data = data.astype(np.float32)

    # 헤더
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
    """합성 광도곡선 생성

    Returns
    -------
    time : np.ndarray
        시간 배열 (초)
    flux : np.ndarray
        플럭스 배열
    """
    time = np.arange(n_points) * cadence
    # 기본 수준 + 플레어 (가우시안)
    flux = 1e-6 * np.ones(n_points)
    peak_idx = n_points // 2
    sigma = 20
    flare = 1e-4 * np.exp(-(np.arange(n_points) - peak_idx)**2 / (2 * sigma**2))
    flux += flare
    flux += np.random.normal(0, 1e-7, n_points)
    return time, flux


def create_synthetic_spectrum(n_wavelengths=2048, n_pixels=100):
    """합성 스펙트럼 데이터 생성

    Returns
    -------
    wavelength : np.ndarray
        파장 배열 (Angstrom)
    spectrum : np.ndarray
        스펙트럼 (n_pixels × n_wavelengths)
    """
    wavelength = np.linspace(1700, 1800, n_wavelengths)
    spectrum = np.zeros((n_pixels, n_wavelengths), dtype=np.float32)
    # 연속 스펙트럼 + 방출선
    for i in range(n_pixels):
        spectrum[i] = 100 * np.exp(-(wavelength - 1750)**2 / (2 * 20**2))
        # 방출선
        line_center = 1750 + np.random.normal(0, 2)
        spectrum[i] += 500 * np.exp(-(wavelength - line_center)**2 / (2 * 0.5**2))
        spectrum[i] += np.random.normal(0, 5, n_wavelengths)
    return wavelength, spectrum
```

### 공개 데이터 쿼리 템플릿

```python
"""SunPy Fido를 활용한 테스트 데이터 다운로드"""
import astropy.units as u
from sunpy.net import Fido, attrs as a
from pathlib import Path


def download_test_aia(data_dir, wavelength=171):
    """테스트용 AIA 이미지 1장 다운로드"""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    result = Fido.search(
        a.Time('2023-01-01 00:00', '2023-01-01 00:01'),
        a.Instrument.aia,
        a.Wavelength(wavelength * u.angstrom),
        a.Sample(12 * u.s)  # 1장만
    )

    if len(result[0]) > 0:
        downloaded = Fido.fetch(result[0, 0], path=str(data_dir))
        return downloaded[0]
    return None


def download_test_goes(data_dir):
    """테스트용 GOES XRS 데이터 다운로드"""
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

## 3. 수치 비교 기준

### 허용 오차 테이블

| 데이터 타입 | rtol (상대) | atol (절대) | 사용 상황 |
|---|---|---|---|
| float32 연산 | 1e-5 | 1e-6 | IDL 기본 정밀도 |
| float64 연산 | 1e-10 | 1e-12 | 고정밀 계산 |
| integer 연산 | 0 | 0 | 정확 일치 |
| 좌표 변환 | 1e-3 | 0.001 arcsec | 단위 변환 오차 |
| 시간 변환 | — | 0.001 sec | 시간 정밀도 |
| 보간 결과 | 1e-3 | 1e-4 | 보간 알고리즘 차이 |
| FFT 결과 | 1e-5 | 1e-6 | 부동소수점 누적 오차 |

### 비교 유틸리티

```python
"""수치 비교 헬퍼"""
import numpy as np
from numpy.testing import assert_allclose, assert_array_equal


def compare_idl_python(python_result, expected, data_type='float32', label=''):
    """IDL-Python 출력 비교

    Parameters
    ----------
    python_result : array-like
        Python 변환 코드의 출력
    expected : array-like
        IDL 원본의 기대 출력
    data_type : str
        데이터 타입 ('float32', 'float64', 'integer')
    label : str
        비교 설명 (에러 메시지에 포함)
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
                          err_msg=f"IDL-Python 불일치: {label}")
    else:
        assert_allclose(python_result, expected,
                       rtol=tol['rtol'], atol=tol['atol'],
                       err_msg=f"IDL-Python 불일치: {label}")
```

---

## 4. 병렬 테스트 실행

### pytest-xdist 방식 (권장)

```bash
# 설치
pip install pytest-xdist

# 자동 워커 수 (CPU 코어 수)
pytest tests/ -n auto -v --tb=short

# 워커 수 지정
pytest tests/ -n 4 -v --tb=short

# 특정 테스트만 병렬
pytest tests/test_utils.py tests/test_loader.py -n 2
```

### Python concurrent.futures 방식

```python
"""병렬 테스트 러너 — pytest-xdist 미설치 시 대안"""
import concurrent.futures
import subprocess
import json
from pathlib import Path


def run_single_test(test_file):
    """단일 테스트 파일 실행"""
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
    """독립 테스트 파일들을 병렬 실행"""
    test_files = sorted(Path(test_dir).glob('test_*.py'))
    results = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single_test, f): f for f in test_files}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            status = 'PASS' if result['passed'] else 'FAIL'
            print(f"  [{status}] {result['file']}")
            results.append(result)

    # 요약
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\n총 {total}개 테스트 파일: {passed} PASS, {total - passed} FAIL")
    return results
```

---

## 5. conftest.py 템플릿

```python
"""공통 pytest 설정 및 fixtures"""
import pytest
import numpy as np
from pathlib import Path
import sys

# converted/ 디렉토리를 Python path에 추가
WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE / 'converted'))

TEST_DATA_DIR = WORKSPACE / 'data'


@pytest.fixture(scope='session')
def test_data_dir():
    """테스트 데이터 디렉토리 (없으면 생성)"""
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TEST_DATA_DIR


@pytest.fixture
def sample_2d_array():
    """테스트용 2D 배열"""
    np.random.seed(42)
    return np.random.rand(100, 200).astype(np.float32)


@pytest.fixture
def sample_1d_array():
    """테스트용 1D 배열"""
    return np.arange(100, dtype=np.float64)


@pytest.fixture
def sample_fits(test_data_dir):
    """테스트용 FITS 파일 (없으면 합성 생성)"""
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
    """빈 배열"""
    return np.array([])


@pytest.fixture
def nan_array():
    """NaN 포함 배열"""
    return np.array([1.0, np.nan, 3.0, np.nan, 5.0])
```

---

## 6. 테스트 보고서 형식

```markdown
# 테스트 결과 보고서

## 실행 환경
- Python: {version}
- NumPy: {version}
- pytest: {version}
- 실행 일시: {timestamp}

## 전체 요약
| 항목 | 값 |
|---|---|
| 테스트 대상 모듈 | N개 |
| 총 테스트 케이스 | K개 |
| PASS | P개 ({P/K*100:.1f}%) |
| FAIL | F개 |
| SKIP | S개 |
| 실행 시간 | {total_time:.1f}s |

## 계층별 결과

### Level 0: 구문 검증
| 모듈 | import 가능 | 비고 |
|---|---|---|
| module_a.py | OK | |
| module_b.py | FAIL | NameError: 'xyz' is not defined |

### Level 1: 단위 테스트
| 모듈 | 테스트 수 | PASS | FAIL | 비고 |
|---|---|---|---|---|
| module_a.py | 12 | 12 | 0 | |
| module_b.py | 8 | 6 | 2 | 인덱싱 2건 |

### Level 2: 통합 테스트
| 워크플로우 | 결과 | 실행 시간 | 비고 |
|---|---|---|---|
| full_pipeline | PASS | 3.2s | |

### Level 3: 인덱싱 전용
| 검증 항목 | 결과 | 비고 |
|---|---|---|
| 2D 배열 생성 | PASS | |
| 2D 인덱싱 | PASS | |
| REFORM→reshape | FAIL | 차원 순서 미전치 |
| TOTAL→sum axis | PASS | |
| WHERE 반환값 | PASS | |

## FAIL 상세

### module_b::test_array_indexing
- **기대값**: shape (4, 3)
- **실제값**: shape (3, 4)
- **원인**: FLTARR(3, 4) → np.zeros((3, 4))로 변환 (순서 전치 누락)
- **수정 제안**: np.zeros((4, 3))으로 수정

## 테스트 데이터 사용 내역
| 데이터 | 출처 | 용도 |
|---|---|---|
| sample.fits | 합성 (NumPy) | FITS I/O 테스트 |
| lightcurve.npz | 합성 (NumPy) | 시계열 처리 테스트 |
```
