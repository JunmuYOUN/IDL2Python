---
name: parity-protocol
description: >
  Execution-based numerical parity protocol for IDL oracle vs. converted Python.
  Defines the probe (checkpoint) convention, the policy.yaml schema, the array-axis (orientation) policy,
  the pixel-coordinate/numerical gotcha catalog, the divergence signature diagnostic table, and the oracle cache rules.
  Keywords: parity, oracle, checkpoint, probe, chk_dump, numerical comparison, execution verification,
  differential testing, readsav, axis inversion, pixel coordinates, CRPIX, rounding, interpolation,
  IoU, divergence, first divergence, waiver, tolerance
---

# Parity-Protocol — Execution-based IDL↔Python numerical parity protocol

## 0. Concepts

- **oracle**: The output obtained by actually running the original IDL code on the server. The sole ground-truth reference.
- **candidate**: The output of the converted Python code.
- **probe (checkpoint)**: A point that dumps variables mid-execution. Inserted at **semantically identical locations** in both codebases.
- **first divergence**: The first probe, in execution order, that fails comparison. The bug lies in the block between the previous PASS probe and this probe.
- **adaptive refinement**: If the divergence interval is wide, add probes only within that interval and re-instrument the oracle (cost: one IDL re-run).

Comparing only the final output ends in "IoU 0.87, cause unknown." Laying down probes narrows it to "matches through `05_ratio_masks`, diverges at `06_morph` → bug in the morphology operation block." **This localization is the reason this harness exists.**

## 1. Probe convention

### 1.1 Dump function (isomorphic on both sides)

```idl
; IDL — inserted into the instrumented copy under staging/
chk_dump, '03_thresholds', t171, t193, t211
```
```python
# Python — inserted into the converted code (harmless to leave in: no-op if CHK_DIR is unset)
chk_dump('03_thresholds', t171=t171, t193=t193, t211=t211)
```

- If the environment variable `CHK_DIR` is empty, both sides **do nothing**. Safe to leave in production code.
- The IDL side preserves variable names via `create_struct` and saves to `probe_<id>.sav` (`/COMPRESS`).
- The Python side saves to `probe_<id>.npz` via `np.savez_compressed`.
- Variable names use the **original names as seen by the caller** (IDL auto-extracts via `scope_varname`; if that fails, specify them with the `names=` keyword).

### 1.2 probe id rules

- Format: `NN_shortname` (e.g. `01_input`, `05_ratio_masks`, `99_final`). NN is the execution order — the comparator processes them in lexicographic = execution order.
- **In the IDL call site, the id must be in single quotes**: `chk_dump, '01_input', ...`.
  A double-quote + leading digit (`"01..."`) is parsed by IDL as an **octal literal** and raises a Syntax error (demonstrated in self-test).
- When inserting via refinement, use a suffix letter like `05a_`, `05b_`.
- Probes inside loops are disallowed by default. If truly necessary, conditionally dump only a specific iteration (`if iter eq 0 then chk_dump, ...`) and embed the iteration in the id (`07_iter0_x`).

### 1.3 Insertion rules (so instrumentation does not contaminate execution)

1. Insert **only at statement boundaries** (not mid-expression, not between `$` continuation lines).
2. Dump **only variables that are defined** at that point (in IDL, if an undefined variable is passed, chk_dump skips it and prints a warning).
3. A probe **does not change values or flow** — it never modifies the variables being dumped.
4. The original `inbox/*.pro` is immutable. Instrumentation goes only into the `staging/{name}_probed.pro` copy.
5. Do not place them inside GUI/plot blocks (excluded-from-conversion region = outside parity scope).

### 1.4 probe placement strategy

- First pass: **8–15 at block boundaries** (right after input load / after preprocessing / after major masks/transforms / just before final).
- The probe right after input (`01_input`) is mandatory — it first filters out mismatches in the data staging itself.
- **probe granularity = divergence-localization granularity.** Comparing only the final output ends in "IoU 0.976, cause unknown." If the interval between probes is wide, you cannot pin down which operation inside it is the cause, so **place a probe right after a suspect IDL built-in (§4.0) or a nontrivial conversion, so that one divergence narrows to one operation.** Example (CHIMERA): separate `03_tricolor` (right after bytscl), `04_masks` (right after thresholding), and `06_iarr` (right after contour/POLYFILLV) to pin each divergence to a single function.
- If the divergence interval is still wide, refine and re-instrument only that interval (§0 adaptive refinement), then fix the operation's convention with a controlled experiment (§4.0).
- At points with large arrays (4096² etc.), trust compressed storage, but if the probe count exceeds 30, report disk usage.
- **Points using random numbers such as RANDOMU**: at the first probe after the random draw, dump the random array itself, and Python proceeds with that value **injected** (seed not reproducible — see 4.11 below).

### 1.5 Instrumentation integrity check (mandatory, once)

Instrumentation is accepted as an oracle only after proving it did not change the result:

```
(a) uninstrumented baseline: run original .pro → retain final output
(b) instrumented run: staging copy + CHK_DIR set → probes + final output
(c) check that final outputs of (a) and (b) are byte/numerically identical → oracle approved only if identical
```
If a past run's output already exists, it can be reused as (a) (after confirming the same input and same code).

## 2. policy.yaml schema

```yaml
orientation: logical        # logical | memory (section 3 below)
nan_equal: true             # both sides NaN → match
dtype_strict: false         # dtype mismatch: false=warn, true=FAIL
defaults:                   # default metric per dtype kind
  float:  {metric: allclose, rtol: 1.0e-5, atol: 1.0e-6}   # float32 baseline
  double: {metric: allclose, rtol: 1.0e-10, atol: 1.0e-12}
  int:    {metric: exact}
  byte_mask: {metric: iou, min_iou: 0.999}                 # 0/1 byte array
checkpoints:                # per-probe/per-variable override
  "05_ratio_masks":
    mas: {metric: iou, min_iou: 0.999}
  "99_final":
    seg_map: {metric: labels, min_iou: 0.99}               # label-permutation-tolerant matching
waivers:                    # approved mismatches (user approval required)
  - checkpoint: "07_rot"
    var: img_rot
    reason: "IDL cubic=-0.5 vs scipy spline kernel difference — user approval 2025-06-01"
    relaxed: {metric: allclose, rtol: 1.0e-3, atol: 1.0e-4}
```

Metric types:

| metric | Use | Decision |
|---|---|---|
| `exact` | integers, indices, counts | `array_equal` |
| `allclose` | real arrays/scalars | rtol/atol + NaN policy |
| `iou` | binary masks | IoU ≥ min_iou |
| `labels` | label maps (connected-region numbers) | label IoU matrix → Hungarian matching → mean matched IoU ≥ min_iou, region counts match |

## 3. Array-axis (orientation) policy — must understand

Three coordinate systems are entangled:

| Perspective | How `FLTARR(nx, ny)` looks |
|---|---|
| IDL logical index | `a[i, j]`, i is the fast axis (x) |
| Memory (identical for both) | x is contiguous |
| `scipy.io.readsav` result | **shape reversed** `(ny, nx)` — `sav[j, i] == idl a[i, j]` |
| astropy `fits.getdata` | `(ny, nx)` — FITS NAXIS1=x is the last axis |

**Policy `logical` (default)**: the converted Python preserves IDL's logical index (`a[i,j]` as-is, `np.zeros((nx,ny))`).
→ The comparator aligns by applying `np.transpose(arr)` (reverse all axes) to the readsav array before comparing.
→ Note: in this case, the `(ny,nx)` array the Python code read via `fits.getdata` must also be handled to match the code's internal convention. In the conversion plan, **declare the code's internal convention in one sentence** (e.g. "internal representation is `img[y, x]` (numpy-natural) — logically corresponds to IDL `a[x, y]`").

**Policy `memory`**: the converted Python uses numpy-natural axes (`(ny,nx)`) as-is (in practice this is more natural for most image code).
→ The comparator compares the readsav array **as-is** (both sides have reversed shape, so they match).
→ In this case, note in the conversion_log that the source appears transposed as IDL `a[i,j]` ↔ Python `a[j,i]`.

Choose one per project and handle exceptions with per-variable overrides. **Mixing the two is the worst.**

## 4. Pixel-coordinate/numerical gotcha catalog

Consult this table first when converting, designing probes, or analyzing divergence. (◆ = related to pixel-coordinate policy)

### 4.0 Principle — do not blindly trust IDL built-in documentation; verify by measurement

IDL built-in functions **often behave differently from their documentation.** Porting the documented formula/description verbatim yields subtle (but definite) errors. Always **cross-check against measurement using an oracle probe**, and when ambiguous, fix the convention with a **controlled micro-experiment**.

Representative cases found in practice (CHIMERA):
- `BYTSCL`: documented as `top`, but the actual scale is `(top+0.9999)/(max-min)` — porting it as `top/range` gives ~18% pixel mismatch.
- `POLYFILLV`: the pixel-inclusion convention differs from skimage `draw.polygon` (lower-left cell vs. center) → the result is shifted by exactly 1 pixel.
- `MEDIAN`: returns the upper element for even N (not the mean); the mean only with `/EVEN`.
- `STDDEV`: ddof=1. `ROUND`: half-away. `FIX`: truncate toward 0. (§4.5, §4.6)

**Controlled-experiment technique** (the fastest, most reliable way to fix a convention):
1. Isolate the single built-in whose convention is suspect and apply it, in both IDL and Python, to a **small known input** (e.g. a 10×10 block in a 20×20 array).
2. Directly compare the output's index range, count, and values → immediately pin down the offset / inclusion convention / rounding direction.
3. Faster than guessing on real data (minutes), reproducible, and serves as the basis for the fix.
   - e.g. an `a[5:14]=1` block → IDL POLYFILLV gives `[4..13]`, draw.polygon gives `[5..14]` → confirms "exactly −1".

**Rule**: when mapping a new IDL built-in, either (a) place an oracle probe so it passes right after that function, or (b) fix the convention with a controlled experiment before converting. "The docs say so, so it must be right" is forbidden.

### 4.1 ◆ FITS/WCS origin
- FITS `CRPIX` is **1-based**, with pixel centers at integer coordinates.
- IDL arrays are 0-based → check in the original whether the SSW code already applied `crpix-1`.
- Choosing the `origin` argument (0 or 1) of astropy `wcs_pix2world(..., origin)` wrong makes exactly a 1-pixel offset.
- sunpy `Map.reference_pixel` is already 0-based (CRPIX−1).

### 4.2 ◆ Resample grid alignment (0.5-pixel gotcha)
- IDL `CONGRID(a, nx2, ny2)`: default is nearest-neighbor; with `/INTERP` it is not just the x-axis that becomes linear — the whole convention changes. Depending on `/CENTER`, the sample grid shifts by 0.5 pixel. The `MINUS_ONE` keyword changes endpoint-inclusion behavior.
- `REBIN`: integer factors only; downsampling is neighbor averaging, upsampling is linear — the kernel differs from scipy `zoom`.
- scipy `ndimage.zoom`, skimage `resize`, and cv2 `resize` each have different grid-alignment conventions.
- **Response**: do not blind-map the resample; reproduce it explicitly by comparing the per-axis source-coordinate formula against the original. The diagnostic signature on divergence is an "edge dipole" (section 5).

### 4.3 ◆ Rotation/shift
- IDL `ROT(a, ang, mag, x0, y0)`: rotation-center convention + `cubic=-0.5` is **cubic convolution** (a different kernel from scipy `order=3` B-spline!).
- scipy `ndimage.rotate/shift`: spline-based; `mode` (boundary extrapolation) also differs from IDL `missing`.
- **Response**: check the original keywords for whether it can be unified to bilinear (`order=1`). If cubic is required, implement cubic convolution directly or waiver.

### 4.4 ◆ Interpolation functions
- IDL `INTERPOLATE(a, x, y)`: default is **clamp** outside the grid (edge value); with `missing=` a substitute value.
- scipy `map_coordinates`: `mode='nearest'` approximates clamp; the default `mode='constant'(0)` differs. `order=1` is bilinear.

### 4.5 ◆ Rounding/truncation
- IDL `ROUND`: half-away-from-zero (2.5→3, −2.5→−3).
- `np.round`/Python `round`: **half-even** (2.5→2). → causes an off-by-one pixel when used in index computation.
  Equivalent implementation: `np.floor(x + 0.5)` (for negatives, `np.trunc(x + np.copysign(0.5, x))`).
- IDL `FIX`: truncate toward 0 = `np.trunc` (not `np.floor` — differs for negatives).
- Integer division: IDL `5/2=2`, Python `5/2=2.5` → `//` needed. But IDL negative integer division is toward 0 (−5/2=−2), while Python `//` is toward −∞ (−3), so they **differ for negatives**.

### 4.6 Statistics functions
- `STDDEV`/`VARIANCE`: IDL uses N−1 → specify `np.std(a, ddof=1)`.
- `MEDIAN`: **IDL default returns the upper element for even N** (not the mean!). Only with `/EVEN` is it the mean = numpy default. → if it differs from `np.median`, suspect here first.
- `MEAN`/`TOTAL`: for float32 input, IDL accumulates in float32 (without `/DOUBLE`). numpy uses pairwise summation → a few ULP difference on large arrays. Absorb it with rtol, but you can narrow it with `np.sum(a, dtype=np.float32)`.

### 4.7 SMOOTH/CONVOL/HISTOGRAM
- `SMOOTH`: default **leaves edges unprocessed** (keeps original values); only with `/EDGE_TRUNCATE` are boundaries handled — the boundary convention differs from scipy `uniform_filter`.
- `CONVOL`: default boundary is not 0-padding (edges skipped); check the `/EDGE_*` keywords. Differs from scipy `convolve` in kernel flipping / normalization (`/NORMALIZE`).
- `HISTOGRAM`: `binsize/min/max` convention, last-bin inclusion rule, `REVERSE_INDICES` structure → differs from `np.histogram` bin edges. If a pixel near the threshold falls into the neighboring bin, the mask changes.

### 4.8 BYTSCL/scaling
- `BYTSCL(a, min=, max=, top=)`: the internal rounding convention of `byte(top * (a-min)/(max-min))` + NaN handling. If for visualization, recommend excluding it from parity scope; if used in the algorithm (e.g. multi-channel threshold masks), exact reproduction is required: check `np.clip` + the truncation method.

### 4.9 WHERE / 1D subscript
- `WHERE` → −1 for no result vs. an empty array. Check the pattern of returning `count` at the same time.
- IDL 1D subscript `a[idx]` operates as a flat index even on multidimensional arrays → numpy `a.flat[idx]` or `np.unravel_index`. **The flat order differs by orientation policy** — under the logical policy, IDL flat order is Fortran order: convert relative to `np.ravel(a, order='F')`.

### 4.10 dtype/overflow
- IDL's default integer is 16-bit! (without `COMPILE_OPT IDL2`). `FIX(70000)` overflows — check whether the original depends on this behavior.
- BYTE arithmetic wraps around mod 256 → same as numpy uint8, but the intermediate-promotion rules differ.
- In the parity stage, keep the **same dtype as IDL** (float32/int16/uint8). float64 promotion comes after passing.

### 4.11 Random numbers / time dependence
- `RANDOMU/RANDOMN` seeds are not reproducible in numpy → dump the random array from IDL as a probe and **inject** it into Python.
- Time-dependent branches such as `SYSTIME` are fixed as inputs.

### 4.12 Astronomical ephemeris/constants (solar physics)
- `pb0r`, `get_sun` (SSW) vs `sunpy.coordinates.sun.*`: B0 / P-angle / radius can differ at the arcsec level → mask pixels near the limb change.
- **Response**: the standard approach is to dump the ephemeris values computed by the oracle IDL as a probe and inject them as-is into Python (for parity purposes). Using sunpy values is a post-pass option + waiver.
- `anytim` vs astropy Time: check the reference frame (UTC/TAI) and leap seconds.

### 4.13 String/formatted output
- For .txt output containing numbers, do not compare strings; **parse then compare numerically** (`1.00000e+00` vs `1.0`).

## 5. Divergence signature diagnostic table

compare_probes.py attempts automatic diagnosis on failing arrays. Use this table for manual analysis too:

| Signature (diff image/statistics) | Likely cause | Check first |
|---|---|---|
| matches when transposed (`transpose_match=true`) | axis order / orientation violation | section 3 policy, REFORM/TOTAL axis |
| matches under integer shift (`shift_match: {axis0, axis1}` — axes in the comparison orientation) | origin/CRPIX/subarray off-by-one | 4.1, hextract/subarray boundary |
| edge dipole (large diff only at boundaries) | resample/interpolation grid 0.5px mismatch | 4.2, 4.3, 4.4 |
| linear scale `py ≈ a·idl + b` | normalization/unit/exposure-correction difference | BYTSCL, exposure time, DN/s |
| speckled differences only at the threshold boundary | rounding/median/histogram convention | 4.5, 4.6, 4.7 |
| NaN on one side only | NaN propagation / `/NAN` keyword | /NAN of MIN/MAX/TOTAL |
| same label count, only numbers differ | label order (scan-order difference) | set metric to `labels` |
| completely unrelated (no correlation) | wrong variable correspondence / probe location mismatch | recheck probe plan |
| tiny ULP level (slightly exceeds rtol) | accumulation order / dtype promotion | 4.6 TOTAL, revisit rtol |

## 6. Running the comparator

```bash
# In the `idl2py` environment
python tools/compare_probes.py \
    --oracle {workpath}/probes/idl \
    --py     {workpath}/probes/py/run_01 \
    --policy {workpath}/policy.yaml \
    --out    {workpath}/reports/parity/run_01 \
    --png
# exit 0 = ALL PASS / 1 = divergence present / 2 = execution error
```

Outputs:
- `report.json` — for machines (loop control)
- `report.md` — probe×variable table, first-divergence highlight, statistics (max_abs/rel, mismatch_frac, argmax location), automatic diagnosis
- `diff_{probe}_{var}.png` — [oracle | python | diff] panels for the failed 2D array

## 7. Oracle execution / cache rules

1. Pre-run checks: license (`idl -e 'print,!version'`), input files exist, `CHK_DIR` created.
2. Generate the batch from `tools/idl/batch_template.pro` — it must end with `exit`, and the launcher call uses `< /dev/null` + timeout.
3. In the run log (`logs/idl_run_*.log`), confirm `>>> BATCH done` + confirm the expected outputs exist. If absent, treat as failure (attach the log).
4. Cache key: a summary of `sha256(instrumented .pro) + sha256(input file list/contents) + sha256(probe plan)` → store the probes and final outputs in `_cache/oracle/{key}/`, plus `meta.json` (IDL version, SSW path, run time, input manifest).
5. If the same key is in the cache, do not re-run. The Python fix loop **never runs IDL again**.
6. The harness does not delete caches/probes (only informs the user).

## 8. parity certificate (mandatory items in the final report)

- Environment provenance: IDL version / SSW path / license server, Python/package versions, execution host
- Input manifest: files, sha256, source (route A/B/C), date
- probe plan version + oracle cache key
- Full probe×variable decision table + the policy used (attach a copy of policy.yaml)
- waiver list (cause, relaxed criterion, approval date)
- Loop history: per-iteration divergence → fix summary
- State the limits: "this parity holds under N input sets, this SSW version, and this policy"
