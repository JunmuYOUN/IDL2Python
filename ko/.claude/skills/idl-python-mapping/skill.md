---
name: idl-python-mapping
description: >
  IDL↔Python 구문 매핑 레퍼런스.
  IDL 내장 함수, 배열 연산, 파일 I/O, SSW/SolarSoft 루틴의
  Python 등가물을 정리한 참조 문서. 변환 시 주의할 함정(gotcha)과
  엣지 케이스를 포함한다.
  키워드: IDL 함수, Python 매핑, 변환 규칙, SSW,
  SolarSoft, numpy, astropy, sunpy, 배열, 인덱싱,
  column-major, row-major, gotcha, 함정
---

# IDL-Python-Mapping — IDL↔Python 구문 매핑 레퍼런스

## 개요

IDL→Python 변환 시 에이전트들이 참조하는 구문 매핑 레퍼런스.
정확한 변환을 위한 1:1 대응표, 주의점(gotcha), 그리고 SSW(SolarSoft) 매핑을 제공한다.

---

## 1. 핵심 함정 (Gotchas) — 반드시 숙지

변환 시 가장 흔한 실수들. 모든 에이전트가 이 목록을 최우선 확인한다.

### 1.1 배열 인덱싱 순서 (Column-Major vs Row-Major)

**IDL**: Column-major (Fortran 순서) — 첫 번째 인덱스가 가장 빠르게 변함
**Python/NumPy**: Row-major (C 순서) — 마지막 인덱스가 가장 빠르게 변함

```
IDL:    arr = FLTARR(3, 4)     ; 3열 × 4행
Python: arr = np.zeros((4, 3))  # 4행 × 3열

IDL:    arr[col, row]
Python: arr[row, col]

IDL:    arr[*, row]      ; row번째 행의 모든 열
Python: arr[row, :]      # 동일

IDL:    arr[col, *]      ; col번째 열의 모든 행
Python: arr[:, col]      # 동일
```

**REFORM/RESHAPE 주의:**
```
IDL:    result = REFORM(data, nx, ny, nz)
Python: result = data.reshape((nz, ny, nx))  # 순서 뒤집기!
```

### 1.2 배열 슬라이싱 (Inclusive vs Exclusive)

```
IDL:    arr[3:7]     ; 인덱스 3, 4, 5, 6, 7 (inclusive end)
Python: arr[3:8]     # 인덱스 3, 4, 5, 6, 7 (exclusive end)

IDL:    arr[3:*]     ; 인덱스 3부터 끝까지
Python: arr[3:]      # 동일
```

### 1.3 WHERE 반환값

```
IDL:
  idx = WHERE(arr GT 0, count)
  IF count EQ 0 THEN ...       ; count로 확인
  IF idx[0] EQ -1 THEN ...     ; -1이 "없음" 표시

Python:
  idx = np.where(arr > 0)
  count = idx[0].size           # 또는 len(idx[0])
  if count == 0: ...            # 빈 배열이 "없음" 표시
  # 주의: Python에서 -1 체크를 하면 안 됨!
```

### 1.4 STDDEV (자유도)

```
IDL:    result = STDDEV(arr)       ; ddof=1 (N-1로 나눔, 표본 표준편차)
Python: result = np.std(arr, ddof=1)  # ddof=1 명시 필수!
        # np.std(arr)는 ddof=0 (모집단 표준편차)
```

### 1.5 정수 나눗셈

```
IDL:    result = 5 / 2      ; = 2 (정수 나눗셈)
Python: result = 5 // 2     # = 2 (// 사용)
        result = 5 / 2      # = 2.5 (Python 3에서 실수 나눗셈)
```

### 1.6 문자열 비교

```
IDL:    IF str EQ 'hello' THEN ...     ; 대소문자 구분
        IF STRUPCASE(str) EQ 'HELLO' THEN ...  ; 대소문자 무시

Python: if str == 'hello': ...         # 대소문자 구분
        if str.upper() == 'HELLO': ... # 대소문자 무시
```

### 1.7 BYTE/STRING 변환

```
IDL:    b = BYTE('A')           ; = 65
        s = STRING(65B)         ; = 'A'

Python: b = ord('A')            # = 65
        s = chr(65)             # = 'A'
```

### 1.8 논리 연산자

```
IDL:    IF (a GT 0) AND (b LT 10) THEN ...
        IF (a GT 0) OR (b LT 10) THEN ...
        IF NOT keyword_set(key) THEN ...

Python: if (a > 0) and (b < 10): ...
        if (a > 0) or (b < 10): ...
        if not key: ...  # 또는 if key is None: ...

# NumPy 배열에서는:
IDL:    idx = WHERE((a GT 0) AND (b LT 10))
Python: idx = np.where((a > 0) & (b < 10))  # & 사용 (and 아님!)
```

---

## 2. 기본 구문 매핑

### 2.1 프로그램 구조

| IDL | Python | 비고 |
|---|---|---|
| `PRO name, arg1, KEY=key` | `def name(arg1, *, key=None):` | 키워드는 keyword-only |
| `FUNCTION name, arg1` | `def name(arg1): ... return result` | |
| `END` | (들여쓰기로 블록 종료) | |
| `COMPILE_OPT IDL2` | (불필요) | Python은 기본 0-based |
| `FORWARD_FUNCTION name` | (불필요) | |
| `@include_file` | `from include_file import *` 또는 exec | 상황에 따라 판단 |
| `COMMON block, var1, var2` | 모듈 레벨 변수 또는 클래스 | 아래 상세 참조 |

### 2.2 제어문

| IDL | Python |
|---|---|
| `IF cond THEN stmt` | `if cond: stmt` |
| `IF cond THEN BEGIN ... END` | `if cond: ...` |
| `IF cond THEN ... ELSE ...` | `if cond: ... else: ...` |
| `FOR i=0, n-1 DO BEGIN ... END` | `for i in range(n): ...` |
| `FOR i=0, n-1, step DO ...` | `for i in range(0, n, step): ...` |
| `WHILE cond DO BEGIN ... END` | `while cond: ...` |
| `REPEAT BEGIN ... END UNTIL cond` | `while True: ... if cond: break` |
| `CASE var OF ... ENDCASE` | `match var: ...` (Python 3.10+) 또는 `if/elif` |
| `SWITCH var OF ... ENDSWITCH` | `if/elif` (fall-through 주의) |
| `GOTO, label` | (루프/함수 구조로 리팩터링) |
| `BREAK` | `break` |
| `CONTINUE` | `continue` |
| `RETURN, value` | `return value` |

### 2.3 데이터 타입

| IDL | Python/NumPy |
|---|---|
| `BYTARR(n)` | `np.zeros(n, dtype=np.uint8)` |
| `INTARR(n)` | `np.zeros(n, dtype=np.int16)` |
| `LONARR(n)` | `np.zeros(n, dtype=np.int32)` |
| `LON64ARR(n)` | `np.zeros(n, dtype=np.int64)` |
| `FLTARR(n)` | `np.zeros(n, dtype=np.float32)` |
| `DBLARR(n)` | `np.zeros(n, dtype=np.float64)` |
| `COMPLEXARR(n)` | `np.zeros(n, dtype=np.complex64)` |
| `STRARR(n)` | `np.empty(n, dtype=object)` 또는 `[''] * n` |
| `INDGEN(n)` | `np.arange(n, dtype=np.int32)` |
| `FINDGEN(n)` | `np.arange(n, dtype=np.float32)` |
| `DINDGEN(n)` | `np.arange(n, dtype=np.float64)` |
| `LINDGEN(n)` | `np.arange(n, dtype=np.int32)` |
| `MAKE_ARRAY(dims, VALUE=v)` | `np.full(dims, v)` |
| `REPLICATE(value, dims)` | `np.full(dims, value)` |
| `FIX(x)` | `int(x)` 또는 `x.astype(np.int16)` |
| `FLOAT(x)` | `float(x)` 또는 `x.astype(np.float32)` |
| `DOUBLE(x)` | `x.astype(np.float64)` |
| `LONG(x)` | `x.astype(np.int32)` |
| `STRING(x)` | `str(x)` |
| `BYTE(x)` | `x.astype(np.uint8)` |

---

## 3. 배열 연산 상세

| IDL | Python | 비고 |
|---|---|---|
| `N_ELEMENTS(arr)` | `arr.size` | 전체 요소 수 |
| `SIZE(arr, /N_DIM)` | `arr.ndim` | 차원 수 |
| `SIZE(arr, /DIM)` | `arr.shape` | 각 차원 크기 |
| `SIZE(arr, /TYPE)` | `arr.dtype` | 데이터 타입 |
| `TOTAL(arr)` | `np.sum(arr)` | |
| `TOTAL(arr, dim)` | `np.sum(arr, axis=...)` | 축 번호 변환 필요! |
| `PRODUCT(arr)` | `np.prod(arr)` | |
| `MIN(arr, idx)` | `np.min(arr)`, `np.argmin(arr)` | |
| `MAX(arr, idx)` | `np.max(arr)`, `np.argmax(arr)` | |
| `SORT(arr)` | `np.argsort(arr)` | IDL은 인덱스 반환 |
| `UNIQ(arr, SORT(arr))` | `np.unique(arr)` | |
| `REVERSE(arr)` | `arr[::-1]` | |
| `SHIFT(arr, n)` | `np.roll(arr, n)` | |
| `ROTATE(arr, dir)` | `np.rot90(arr, k)` | dir→k 매핑 필요 |
| `TRANSPOSE(arr)` | `arr.T` | |
| `CONGRID(arr, nx, ny)` | `scipy.ndimage.zoom(arr, ...)` | 보간 방법 확인 |
| `REBIN(arr, nx, ny)` | `np.repeat` + `np.reshape` 또는 `scipy.ndimage.zoom` | 정수배/비정수배 구분 |
| `HISTOGRAM(arr)` | `np.histogram(arr)` | 반환 형식 차이 |
| `ARRAY_INDICES(arr, idx)` | `np.unravel_index(idx, arr.shape)` | |

### TOTAL의 axis 변환

IDL의 차원 번호와 NumPy의 axis는 순서가 반대:
```
IDL:    TOTAL(arr, 1)   ; 첫 번째 차원(열)을 따라 합산
Python: np.sum(arr, axis=-1)  # 또는 axis=ndim-1 (마지막 차원)

IDL 차원 1 → NumPy axis (ndim - 1)
IDL 차원 2 → NumPy axis (ndim - 2)
...일반화: IDL 차원 d → NumPy axis (ndim - d)
```

---

## 4. 수학/통계 함수

| IDL | Python | 비고 |
|---|---|---|
| `ABS(x)` | `np.abs(x)` | |
| `SQRT(x)` | `np.sqrt(x)` | |
| `EXP(x)` | `np.exp(x)` | |
| `ALOG(x)` | `np.log(x)` | 자연로그 |
| `ALOG10(x)` | `np.log10(x)` | 상용로그 |
| `ALOG2(x)` | `np.log2(x)` | |
| `SIN(x)`, `COS(x)`, `TAN(x)` | `np.sin(x)`, `np.cos(x)`, `np.tan(x)` | |
| `ASIN(x)`, `ACOS(x)`, `ATAN(x)` | `np.arcsin(x)`, `np.arccos(x)`, `np.arctan(x)` | |
| `ATAN(y, x)` | `np.arctan2(y, x)` | 2-argument |
| `CEIL(x)` | `np.ceil(x)` | |
| `FLOOR(x)` | `np.floor(x)` | |
| `ROUND(x)` | `np.round(x)` | |
| `MEAN(arr)` | `np.mean(arr)` | |
| `MEDIAN(arr)` | `np.median(arr)` | |
| `STDDEV(arr)` | `np.std(arr, ddof=1)` | **ddof=1 필수!** |
| `VARIANCE(arr)` | `np.var(arr, ddof=1)` | **ddof=1 필수!** |
| `POLY_FIT(x, y, deg)` | `np.polyfit(x, y, deg)` | |
| `POLY(x, coeff)` | `np.polyval(coeff, x)` | 계수 순서 확인! |
| `INTERPOL(y, x, xnew)` | `np.interp(xnew, x, y)` | 인자 순서 다름! |
| `SPLINE(x, y, xnew)` | `scipy.interpolate.CubicSpline(x, y)(xnew)` | |
| `SMOOTH(arr, w)` | `scipy.ndimage.uniform_filter(arr, w)` | |
| `CONVOL(arr, kern)` | `scipy.signal.convolve(arr, kern, mode='same')` | mode 확인 |
| `FFT(arr)` | `np.fft.fft(arr)` | |
| `FFT(arr, -1)` | `np.fft.ifft(arr)` | 역변환 |
| `CORRELATE(x, y)` | `np.corrcoef(x, y)[0,1]` | |
| `DERIV(y)` / `DERIV(x,y)` | `np.gradient(y)` / `np.gradient(y, x)` | |
| `INT_TABULATED(x, y)` | `np.trapz(y, x)` | 사다리꼴 적분 |
| `RANDOMU(seed, n)` | `np.random.random(n)` | 균일 분포 |
| `RANDOMN(seed, n)` | `np.random.randn(n)` | 정규 분포 |
| `FINITE(x)` | `np.isfinite(x)` | |
| `!PI` | `np.pi` | |
| `!DTOR` | `np.deg2rad(1)` 또는 `np.pi/180` | |
| `!RADEG` | `np.rad2deg(1)` 또는 `180/np.pi` | |

---

## 5. 문자열 함수

| IDL | Python |
|---|---|
| `STRLEN(s)` | `len(s)` |
| `STRMID(s, pos, len)` | `s[pos:pos+len]` |
| `STRPOS(s, sub)` | `s.find(sub)` |
| `STRTRIM(s, 0)` | `s.lstrip()` |
| `STRTRIM(s, 1)` | `s.rstrip()` |
| `STRTRIM(s, 2)` | `s.strip()` |
| `STRUPCASE(s)` | `s.upper()` |
| `STRLOWCASE(s)` | `s.lower()` |
| `STRSPLIT(s, delim, /EXTRACT)` | `s.split(delim)` |
| `STRJOIN(arr, delim)` | `delim.join(arr)` |
| `STRCOMPRESS(s, /REMOVE_ALL)` | `s.replace(' ', '')` |
| `STRCOMPRESS(s)` | `' '.join(s.split())` |
| `STRING(val, FORMAT=fmt)` | `f'{val:fmt}'` 또는 `format(val, fmt)` |
| `READS, s, var` | `var = type(s)` (파싱) |
| `STREGEX(s, pattern, /EXTRACT)` | `re.search(pattern, s).group()` |
| `STRMATCH(s, pattern)` | `fnmatch.fnmatch(s, pattern)` |

---

## 6. 파일 I/O

| IDL | Python | 비고 |
|---|---|---|
| `FITS_READ, file, data, hdr` | `data, hdr = fits.getdata(file, header=True)` | astropy.io.fits |
| `READFITS(file)` | `fits.getdata(file)` | |
| `WRITEFITS, file, data, hdr` | `fits.writeto(file, data, hdr, overwrite=True)` | |
| `MREADFITS, file, index, data` | `fits.open(file)` + 인덱스 접근 | |
| `FXREAD, file, data` | `fits.getdata(file)` | |
| `SAVE, v1, v2, FILE=f` | `np.savez(f, v1=v1, v2=v2)` | 또는 pickle |
| `RESTORE, f` | `scipy.io.readsav(f)` | IDL .sav 파일 |
| `OPENR, lun, file` | `f = open(file, 'r')` | context manager 권장 |
| `OPENW, lun, file` | `f = open(file, 'w')` | |
| `OPENU, lun, file` | `f = open(file, 'r+')` | |
| `GET_LUN, lun` | (불필요) | |
| `FREE_LUN, lun` | `f.close()` | |
| `READF, lun, var` | `var = f.readline()` | 파싱 추가 필요 |
| `PRINTF, lun, var` | `f.write(str(var) + '\n')` | |
| `READU, lun, var` | `var = np.fromfile(f, dtype=...)` | 바이너리 |
| `WRITEU, lun, var` | `var.tofile(f)` | 바이너리 |
| `POINT_LUN, lun, pos` | `f.seek(pos)` | |
| `EOF(lun)` | 파일 끝 확인 로직 | |
| `FILE_TEST(path)` | `os.path.exists(path)` 또는 `Path(path).exists()` | |
| `FILE_SEARCH(pattern)` | `glob.glob(pattern)` | |
| `FILE_MKDIR, path` | `os.makedirs(path, exist_ok=True)` | |
| `FILE_BASENAME(path)` | `os.path.basename(path)` | |
| `FILE_DIRNAME(path)` | `os.path.dirname(path)` | |

---

## 7. SSW(SolarSoft) → SunPy/Astropy 매핑

### 시간 처리

| SSW/IDL | Python | 패키지 |
|---|---|---|
| `anytim(time)` | `sunpy.time.parse_time(time)` | sunpy |
| `anytim(time, /TAI)` | `sunpy.time.parse_time(time).tai` | sunpy |
| `anytim(time, /UTC_EXT)` | `sunpy.time.parse_time(time).datetime` | sunpy |
| `ssw_time2str(time)` | `Time(time).iso` | astropy.time |
| `utplot, x, y` | `ax.plot(parse_time(x).datetime, y)` | sunpy+matplotlib |
| `anytim2jd(time)` | `Time(time).jd` | astropy.time |
| `anytim2tai(time)` | `Time(time).unix_tai` | astropy.time |
| `timegen(n, START=s, STEP=dt)` | `[s + i*dt for i in range(n)]` | |

### 데이터 접근

| SSW/IDL | Python | 패키지 |
|---|---|---|
| `read_sdo, file, index, data` | `smap = sunpy.map.Map(file)` | sunpy |
| `aia_prep, index, data` | `aiapy.calibrate.register(smap)` | aiapy |
| `vso_search(...)` | `Fido.search(...)` | sunpy.net |
| `vso_get(record)` | `Fido.fetch(result)` | sunpy.net |
| `ssw_jsoc_time2data(...)` | `drms.Client().query(...)` | drms |
| `read_goes_nc, file, data` | `TimeSeries(file)` | sunpy.timeseries |

### 좌표 변환

| SSW/IDL | Python | 패키지 |
|---|---|---|
| `wcs_convert_from_coord(...)` | `SkyCoord` + `Helioprojective` | astropy+sunpy |
| `arcmin2hel(x, y)` | `SkyCoord(x, y, frame='helioprojective').transform_to('heliographic_stonyhurst')` | sunpy |
| `hel2arcmin(lat, lon)` | `SkyCoord(lon, lat, frame='heliographic_stonyhurst').transform_to('helioprojective')` | sunpy |
| `pb0r(date)` | `sunpy.coordinates.sun.B0(date)`, `sun.P(date)`, `sun.angular_radius(date)` | sunpy |

### 시각화

| SSW/IDL | Python | 비고 |
|---|---|---|
| `PLOT, x, y` | `plt.plot(x, y)` | matplotlib |
| `OPLOT, x, y` | `plt.plot(x, y)` (같은 axes) | |
| `PLOT_IMAGE, img` | `plt.imshow(img)` | origin 주의 |
| `TVSCL, img` | `plt.imshow(img, vmin=..., vmax=...)` | |
| `CONTOUR, z, x, y` | `plt.contour(x, y, z)` | 인자 순서 다름! |
| `XYOUTS, x, y, text` | `plt.text(x, y, text)` | |
| `LOADCT, n` | `plt.set_cmap(cmap_name)` | 컬러맵 이름 매핑 필요 |
| `DEVICE, /COLOR, BITS=8` | (불필요) | |
| `!P.MULTI = [0, nx, ny]` | `fig, axes = plt.subplots(ny, nx)` | 순서 뒤집기! |
| `WINDOW, n, XSIZE=x, YSIZE=y` | `fig = plt.figure(n, figsize=(x/100, y/100))` | 단위 변환 |

---

## 8. COMMON 블록 변환 전략

IDL의 COMMON 블록은 여러 프로시저가 공유하는 전역 변수 집합이다.

### 전략 1: 모듈 레벨 변수 (단순한 경우)

```
; IDL
COMMON shared_data, data_array, header_info

PRO process_data
  COMMON shared_data
  data_array = data_array * 2.0
END
```

```python
# Python — 모듈 레벨
_shared = {
    'data_array': None,
    'header_info': None,
}

def process_data():
    _shared['data_array'] = _shared['data_array'] * 2.0
```

### 전략 2: 클래스 (복잡한 경우)

```python
# Python — 클래스
from dataclasses import dataclass, field
import numpy as np

@dataclass
class SharedData:
    data_array: np.ndarray = field(default_factory=lambda: np.array([]))
    header_info: dict = field(default_factory=dict)

shared = SharedData()

def process_data():
    shared.data_array = shared.data_array * 2.0
```

---

## 9. 에러 처리 변환

```
; IDL
CATCH, err
IF err NE 0 THEN BEGIN
  CATCH, /CANCEL
  PRINT, 'Error: ' + !ERROR_STATE.MSG
  RETURN, -1
ENDIF
```

```python
# Python
try:
    ...
except Exception as err:
    print(f'Error: {err}')
    return -1
```

```
; IDL — ON_ERROR
ON_ERROR, 2   ; 에러 시 호출자로 복귀
```

```python
# Python — 함수 구조로 대체 (ON_ERROR는 직접 대응 없음)
# 에러를 raise하면 자연스럽게 호출자로 전파됨
```

---

## 10. 키워드 인자 변환

```
; IDL
PRO plot_data, x, y, COLOR=color, THICK=thick, TITLE=title, /LOG

  IF NOT KEYWORD_SET(color) THEN color = 'black'
  IF NOT KEYWORD_SET(thick) THEN thick = 1
  IF KEYWORD_SET(log) THEN y = ALOG10(y)
  ...
END
```

```python
# Python
def plot_data(x, y, *, color=None, thick=None, title=None, log=False):
    if color is None:
        color = 'black'
    if thick is None:
        thick = 1
    if log:
        y = np.log10(y)
    ...
```

**KEYWORD_SET vs N_ELEMENTS 차이:**
- `KEYWORD_SET(key)` → `key is not None and key` (0이나 빈 문자열은 False)
- `N_ELEMENTS(key) GT 0` → `key is not None` (0이라도 전달되었으면 True)
