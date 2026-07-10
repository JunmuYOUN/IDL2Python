---
name: idl-python-mapping
description: >
  IDL↔Python syntax mapping reference.
  A reference document cataloging the Python equivalents of IDL
  built-in functions, array operations, file I/O, and SSW/SolarSoft routines.
  Includes gotchas and edge cases to watch out for during conversion.
  Keywords: IDL functions, Python mapping, conversion rules, SSW,
  SolarSoft, numpy, astropy, sunpy, arrays, indexing,
  column-major, row-major, gotcha, pitfalls
---

# IDL-Python-Mapping — IDL↔Python Syntax Mapping Reference

## Overview

Syntax mapping reference that the agents consult during IDL→Python conversion.
Provides 1:1 correspondence tables, gotchas, and SSW (SolarSoft) mappings for accurate conversion.

---

## 1. Key Gotchas — Must Know

The most common mistakes during conversion. Every agent checks this list first.

### 1.1 Array Indexing Order (Column-Major vs Row-Major)

**IDL**: Column-major (Fortran order) — the first index varies fastest
**Python/NumPy**: Row-major (C order) — the last index varies fastest

```
IDL:    arr = FLTARR(3, 4)     ; 3 columns × 4 rows
Python: arr = np.zeros((4, 3))  # 4 rows × 3 columns

IDL:    arr[col, row]
Python: arr[row, col]

IDL:    arr[*, row]      ; all columns of the row-th row
Python: arr[row, :]      # same

IDL:    arr[col, *]      ; all rows of the col-th column
Python: arr[:, col]      # same
```

**REFORM/RESHAPE caution:**
```
IDL:    result = REFORM(data, nx, ny, nz)
Python: result = data.reshape((nz, ny, nx))  # reverse the order!
```

### 1.2 Array Slicing (Inclusive vs Exclusive)

```
IDL:    arr[3:7]     ; indices 3, 4, 5, 6, 7 (inclusive end)
Python: arr[3:8]     # indices 3, 4, 5, 6, 7 (exclusive end)

IDL:    arr[3:*]     ; from index 3 to the end
Python: arr[3:]      # same
```

### 1.3 WHERE Return Value

```
IDL:
  idx = WHERE(arr GT 0, count)
  IF count EQ 0 THEN ...       ; check via count
  IF idx[0] EQ -1 THEN ...     ; -1 marks "none found"

Python:
  idx = np.where(arr > 0)
  count = idx[0].size           # or len(idx[0])
  if count == 0: ...            # an empty array marks "none found"
  # caution: do NOT do a -1 check in Python!
```

### 1.4 STDDEV (Degrees of Freedom)

```
IDL:    result = STDDEV(arr)       ; ddof=1 (divides by N-1, sample standard deviation)
Python: result = np.std(arr, ddof=1)  # ddof=1 must be specified explicitly!
        # np.std(arr) is ddof=0 (population standard deviation)
```

### 1.5 Integer Division

```
IDL:    result = 5 / 2      ; = 2 (integer division)
Python: result = 5 // 2     # = 2 (use //)
        result = 5 / 2      # = 2.5 (float division in Python 3)
```

### 1.6 String Comparison

```
IDL:    IF str EQ 'hello' THEN ...     ; case-sensitive
        IF STRUPCASE(str) EQ 'HELLO' THEN ...  ; case-insensitive

Python: if str == 'hello': ...         # case-sensitive
        if str.upper() == 'HELLO': ... # case-insensitive
```

### 1.7 BYTE/STRING Conversion

```
IDL:    b = BYTE('A')           ; = 65
        s = STRING(65B)         ; = 'A'

Python: b = ord('A')            # = 65
        s = chr(65)             # = 'A'
```

### 1.8 Logical Operators

```
IDL:    IF (a GT 0) AND (b LT 10) THEN ...
        IF (a GT 0) OR (b LT 10) THEN ...
        IF NOT keyword_set(key) THEN ...

Python: if (a > 0) and (b < 10): ...
        if (a > 0) or (b < 10): ...
        if not key: ...  # or if key is None: ...

# For NumPy arrays:
IDL:    idx = WHERE((a GT 0) AND (b LT 10))
Python: idx = np.where((a > 0) & (b < 10))  # use & (not and!)
```

---

## 2. Basic Syntax Mapping

### 2.1 Program Structure

| IDL | Python | Notes |
|---|---|---|
| `PRO name, arg1, KEY=key` | `def name(arg1, *, key=None):` | keywords are keyword-only |
| `FUNCTION name, arg1` | `def name(arg1): ... return result` | |
| `END` | (block ends by indentation) | |
| `COMPILE_OPT IDL2` | (not needed) | Python is 0-based by default |
| `FORWARD_FUNCTION name` | (not needed) | |
| `@include_file` | `from include_file import *` or exec | judge case by case |
| `COMMON block, var1, var2` | module-level variables or a class | see details below |

### 2.2 Control Statements

| IDL | Python |
|---|---|
| `IF cond THEN stmt` | `if cond: stmt` |
| `IF cond THEN BEGIN ... END` | `if cond: ...` |
| `IF cond THEN ... ELSE ...` | `if cond: ... else: ...` |
| `FOR i=0, n-1 DO BEGIN ... END` | `for i in range(n): ...` |
| `FOR i=0, n-1, step DO ...` | `for i in range(0, n, step): ...` |
| `WHILE cond DO BEGIN ... END` | `while cond: ...` |
| `REPEAT BEGIN ... END UNTIL cond` | `while True: ... if cond: break` |
| `CASE var OF ... ENDCASE` | `match var: ...` (Python 3.10+) or `if/elif` |
| `SWITCH var OF ... ENDSWITCH` | `if/elif` (watch for fall-through) |
| `GOTO, label` | (refactor into loop/function structure) |
| `BREAK` | `break` |
| `CONTINUE` | `continue` |
| `RETURN, value` | `return value` |

### 2.3 Data Types

| IDL | Python/NumPy |
|---|---|
| `BYTARR(n)` | `np.zeros(n, dtype=np.uint8)` |
| `INTARR(n)` | `np.zeros(n, dtype=np.int16)` |
| `LONARR(n)` | `np.zeros(n, dtype=np.int32)` |
| `LON64ARR(n)` | `np.zeros(n, dtype=np.int64)` |
| `FLTARR(n)` | `np.zeros(n, dtype=np.float32)` |
| `DBLARR(n)` | `np.zeros(n, dtype=np.float64)` |
| `COMPLEXARR(n)` | `np.zeros(n, dtype=np.complex64)` |
| `STRARR(n)` | `np.empty(n, dtype=object)` or `[''] * n` |
| `INDGEN(n)` | `np.arange(n, dtype=np.int32)` |
| `FINDGEN(n)` | `np.arange(n, dtype=np.float32)` |
| `DINDGEN(n)` | `np.arange(n, dtype=np.float64)` |
| `LINDGEN(n)` | `np.arange(n, dtype=np.int32)` |
| `MAKE_ARRAY(dims, VALUE=v)` | `np.full(dims, v)` |
| `REPLICATE(value, dims)` | `np.full(dims, value)` |
| `FIX(x)` | `int(x)` or `x.astype(np.int16)` |
| `FLOAT(x)` | `float(x)` or `x.astype(np.float32)` |
| `DOUBLE(x)` | `x.astype(np.float64)` |
| `LONG(x)` | `x.astype(np.int32)` |
| `STRING(x)` | `str(x)` |
| `BYTE(x)` | `x.astype(np.uint8)` |

---

## 3. Array Operations in Detail

| IDL | Python | Notes |
|---|---|---|
| `N_ELEMENTS(arr)` | `arr.size` | total number of elements |
| `SIZE(arr, /N_DIM)` | `arr.ndim` | number of dimensions |
| `SIZE(arr, /DIM)` | `arr.shape` | size of each dimension |
| `SIZE(arr, /TYPE)` | `arr.dtype` | data type |
| `TOTAL(arr)` | `np.sum(arr)` | |
| `TOTAL(arr, dim)` | `np.sum(arr, axis=...)` | axis number must be converted! |
| `PRODUCT(arr)` | `np.prod(arr)` | |
| `MIN(arr, idx)` | `np.min(arr)`, `np.argmin(arr)` | |
| `MAX(arr, idx)` | `np.max(arr)`, `np.argmax(arr)` | |
| `SORT(arr)` | `np.argsort(arr)` | IDL returns indices |
| `UNIQ(arr, SORT(arr))` | `np.unique(arr)` | |
| `REVERSE(arr)` | `arr[::-1]` | |
| `SHIFT(arr, n)` | `np.roll(arr, n)` | |
| `ROTATE(arr, dir)` | `np.rot90(arr, k)` | dir→k mapping needed |
| `TRANSPOSE(arr)` | `arr.T` | |
| `CONGRID(arr, nx, ny)` | `scipy.ndimage.zoom(arr, ...)` | check interpolation method |
| `REBIN(arr, nx, ny)` | `np.repeat` + `np.reshape` or `scipy.ndimage.zoom` | distinguish integer/non-integer factor |
| `HISTOGRAM(arr)` | `np.histogram(arr)` | return format differs |
| `ARRAY_INDICES(arr, idx)` | `np.unravel_index(idx, arr.shape)` | |

### Axis Conversion for TOTAL

IDL dimension numbers and NumPy axes run in the opposite order:
```
IDL:    TOTAL(arr, 1)   ; sum along the first dimension (columns)
Python: np.sum(arr, axis=-1)  # or axis=ndim-1 (last dimension)

IDL dimension 1 → NumPy axis (ndim - 1)
IDL dimension 2 → NumPy axis (ndim - 2)
...generalized: IDL dimension d → NumPy axis (ndim - d)
```

---

## 4. Math / Statistics Functions

| IDL | Python | Notes |
|---|---|---|
| `ABS(x)` | `np.abs(x)` | |
| `SQRT(x)` | `np.sqrt(x)` | |
| `EXP(x)` | `np.exp(x)` | |
| `ALOG(x)` | `np.log(x)` | natural log |
| `ALOG10(x)` | `np.log10(x)` | base-10 log |
| `ALOG2(x)` | `np.log2(x)` | |
| `SIN(x)`, `COS(x)`, `TAN(x)` | `np.sin(x)`, `np.cos(x)`, `np.tan(x)` | |
| `ASIN(x)`, `ACOS(x)`, `ATAN(x)` | `np.arcsin(x)`, `np.arccos(x)`, `np.arctan(x)` | |
| `ATAN(y, x)` | `np.arctan2(y, x)` | 2-argument |
| `CEIL(x)` | `np.ceil(x)` | |
| `FLOOR(x)` | `np.floor(x)` | |
| `ROUND(x)` | `np.round(x)` | |
| `MEAN(arr)` | `np.mean(arr)` | |
| `MEDIAN(arr)` | `np.median(arr)` | |
| `STDDEV(arr)` | `np.std(arr, ddof=1)` | **ddof=1 required!** |
| `VARIANCE(arr)` | `np.var(arr, ddof=1)` | **ddof=1 required!** |
| `POLY_FIT(x, y, deg)` | `np.polyfit(x, y, deg)` | |
| `POLY(x, coeff)` | `np.polyval(coeff, x)` | check coefficient order! |
| `INTERPOL(y, x, xnew)` | `np.interp(xnew, x, y)` | argument order differs! |
| `SPLINE(x, y, xnew)` | `scipy.interpolate.CubicSpline(x, y)(xnew)` | |
| `SMOOTH(arr, w)` | `scipy.ndimage.uniform_filter(arr, w)` | |
| `CONVOL(arr, kern)` | `scipy.signal.convolve(arr, kern, mode='same')` | check mode |
| `FFT(arr)` | `np.fft.fft(arr)` | |
| `FFT(arr, -1)` | `np.fft.ifft(arr)` | inverse transform |
| `CORRELATE(x, y)` | `np.corrcoef(x, y)[0,1]` | |
| `DERIV(y)` / `DERIV(x,y)` | `np.gradient(y)` / `np.gradient(y, x)` | |
| `INT_TABULATED(x, y)` | `np.trapz(y, x)` | trapezoidal integration |
| `RANDOMU(seed, n)` | `np.random.random(n)` | uniform distribution |
| `RANDOMN(seed, n)` | `np.random.randn(n)` | normal distribution |
| `FINITE(x)` | `np.isfinite(x)` | |
| `!PI` | `np.pi` | |
| `!DTOR` | `np.deg2rad(1)` or `np.pi/180` | |
| `!RADEG` | `np.rad2deg(1)` or `180/np.pi` | |

---

## 5. String Functions

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
| `STRING(val, FORMAT=fmt)` | `f'{val:fmt}'` or `format(val, fmt)` |
| `READS, s, var` | `var = type(s)` (parsing) |
| `STREGEX(s, pattern, /EXTRACT)` | `re.search(pattern, s).group()` |
| `STRMATCH(s, pattern)` | `fnmatch.fnmatch(s, pattern)` |

---

## 6. File I/O

| IDL | Python | Notes |
|---|---|---|
| `FITS_READ, file, data, hdr` | `data, hdr = fits.getdata(file, header=True)` | astropy.io.fits |
| `READFITS(file)` | `fits.getdata(file)` | |
| `WRITEFITS, file, data, hdr` | `fits.writeto(file, data, hdr, overwrite=True)` | |
| `MREADFITS, file, index, data` | `fits.open(file)` + index access | |
| `FXREAD, file, data` | `fits.getdata(file)` | |
| `SAVE, v1, v2, FILE=f` | `np.savez(f, v1=v1, v2=v2)` | or pickle |
| `RESTORE, f` | `scipy.io.readsav(f)` | IDL .sav file |
| `OPENR, lun, file` | `f = open(file, 'r')` | context manager recommended |
| `OPENW, lun, file` | `f = open(file, 'w')` | |
| `OPENU, lun, file` | `f = open(file, 'r+')` | |
| `GET_LUN, lun` | (not needed) | |
| `FREE_LUN, lun` | `f.close()` | |
| `READF, lun, var` | `var = f.readline()` | additional parsing needed |
| `PRINTF, lun, var` | `f.write(str(var) + '\n')` | |
| `READU, lun, var` | `var = np.fromfile(f, dtype=...)` | binary |
| `WRITEU, lun, var` | `var.tofile(f)` | binary |
| `POINT_LUN, lun, pos` | `f.seek(pos)` | |
| `EOF(lun)` | end-of-file check logic | |
| `FILE_TEST(path)` | `os.path.exists(path)` or `Path(path).exists()` | |
| `FILE_SEARCH(pattern)` | `glob.glob(pattern)` | |
| `FILE_MKDIR, path` | `os.makedirs(path, exist_ok=True)` | |
| `FILE_BASENAME(path)` | `os.path.basename(path)` | |
| `FILE_DIRNAME(path)` | `os.path.dirname(path)` | |

---

## 7. SSW (SolarSoft) → SunPy/Astropy Mapping

### Time Handling

| SSW/IDL | Python | Package |
|---|---|---|
| `anytim(time)` | `sunpy.time.parse_time(time)` | sunpy |
| `anytim(time, /TAI)` | `sunpy.time.parse_time(time).tai` | sunpy |
| `anytim(time, /UTC_EXT)` | `sunpy.time.parse_time(time).datetime` | sunpy |
| `ssw_time2str(time)` | `Time(time).iso` | astropy.time |
| `utplot, x, y` | `ax.plot(parse_time(x).datetime, y)` | sunpy+matplotlib |
| `anytim2jd(time)` | `Time(time).jd` | astropy.time |
| `anytim2tai(time)` | `Time(time).unix_tai` | astropy.time |
| `timegen(n, START=s, STEP=dt)` | `[s + i*dt for i in range(n)]` | |

### Data Access

| SSW/IDL | Python | Package |
|---|---|---|
| `read_sdo, file, index, data` | `smap = sunpy.map.Map(file)` | sunpy |
| `aia_prep, index, data` | `aiapy.calibrate.register(smap)` | aiapy |
| `vso_search(...)` | `Fido.search(...)` | sunpy.net |
| `vso_get(record)` | `Fido.fetch(result)` | sunpy.net |
| `ssw_jsoc_time2data(...)` | `drms.Client().query(...)` | drms |
| `read_goes_nc, file, data` | `TimeSeries(file)` | sunpy.timeseries |

### Coordinate Transformation

| SSW/IDL | Python | Package |
|---|---|---|
| `wcs_convert_from_coord(...)` | `SkyCoord` + `Helioprojective` | astropy+sunpy |
| `arcmin2hel(x, y)` | `SkyCoord(x, y, frame='helioprojective').transform_to('heliographic_stonyhurst')` | sunpy |
| `hel2arcmin(lat, lon)` | `SkyCoord(lon, lat, frame='heliographic_stonyhurst').transform_to('helioprojective')` | sunpy |
| `pb0r(date)` | `sunpy.coordinates.sun.B0(date)`, `sun.P(date)`, `sun.angular_radius(date)` | sunpy |

### Visualization

| SSW/IDL | Python | Notes |
|---|---|---|
| `PLOT, x, y` | `plt.plot(x, y)` | matplotlib |
| `OPLOT, x, y` | `plt.plot(x, y)` (same axes) | |
| `PLOT_IMAGE, img` | `plt.imshow(img)` | watch origin |
| `TVSCL, img` | `plt.imshow(img, vmin=..., vmax=...)` | |
| `CONTOUR, z, x, y` | `plt.contour(x, y, z)` | argument order differs! |
| `XYOUTS, x, y, text` | `plt.text(x, y, text)` | |
| `LOADCT, n` | `plt.set_cmap(cmap_name)` | colormap name mapping needed |
| `DEVICE, /COLOR, BITS=8` | (not needed) | |
| `!P.MULTI = [0, nx, ny]` | `fig, axes = plt.subplots(ny, nx)` | reverse the order! |
| `WINDOW, n, XSIZE=x, YSIZE=y` | `fig = plt.figure(n, figsize=(x/100, y/100))` | unit conversion |

---

## 8. COMMON Block Conversion Strategy

An IDL COMMON block is a set of global variables shared across multiple procedures.

### Strategy 1: Module-Level Variables (Simple Case)

```
; IDL
COMMON shared_data, data_array, header_info

PRO process_data
  COMMON shared_data
  data_array = data_array * 2.0
END
```

```python
# Python — module level
_shared = {
    'data_array': None,
    'header_info': None,
}

def process_data():
    _shared['data_array'] = _shared['data_array'] * 2.0
```

### Strategy 2: Class (Complex Case)

```python
# Python — class
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

## 9. Error Handling Conversion

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
ON_ERROR, 2   ; return to caller on error
```

```python
# Python — replace with function structure (ON_ERROR has no direct equivalent)
# raising an error naturally propagates it to the caller
```

---

## 10. Keyword Argument Conversion

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

**KEYWORD_SET vs N_ELEMENTS difference:**
- `KEYWORD_SET(key)` → `key is not None and key` (0 or an empty string is False)
- `N_ELEMENTS(key) GT 0` → `key is not None` (True if passed, even if 0)
