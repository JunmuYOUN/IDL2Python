---
name: parity-protocol
description: >
  IDL 오라클 vs 변환 Python의 실행 기반 수치 대조(parity) 프로토콜.
  probe(체크포인트) 규약, policy.yaml 스키마, 배열 축(orientation) 정책,
  픽셀 좌표·수치 함정 카탈로그, 발산 시그니처 진단표, 오라클 캐시 규칙을 정의한다.
  키워드: parity, 오라클, 체크포인트, probe, chk_dump, 수치 대조, 실행 검증,
  differential testing, readsav, 축 반전, 픽셀 좌표, CRPIX, 반올림, 보간,
  IoU, 발산, first divergence, waiver, 허용 오차
---

# Parity-Protocol — 실행 기반 IDL↔Python 수치 대조 프로토콜

## 0. 개념

- **오라클(oracle)**: 원본 IDL 코드를 서버에서 실제 실행해 얻은 산출물. 유일한 정답 기준.
- **후보(candidate)**: 변환된 Python 코드의 산출물.
- **probe(체크포인트)**: 코드 실행 중간에 변수들을 덤프하는 지점. 양쪽 코드에 **의미적으로 동일한 위치**에 삽입한다.
- **최초 발산(first divergence)**: 실행 순서상 처음으로 비교에 실패한 probe. 버그는 직전 PASS probe와 이 probe 사이 블록에 있다.
- **적응적 세분화**: 발산 구간이 넓으면 그 구간에만 probe를 추가해 오라클을 재계측한다(비용: IDL 1회 재실행).

최종 출력만 비교하면 "IoU 0.87, 원인 불명"으로 끝난다. probe를 깔면 "`05_ratio_masks`까지 일치, `06_morph`에서 발산 → 형태학 연산 블록의 버그"로 좁혀진다. **이 국소화가 이 하네스의 존재 이유다.**

## 1. Probe 규약

### 1.1 덤프 함수 (양쪽 동형)

```idl
; IDL — staging/의 계측 사본에 삽입
chk_dump, '03_thresholds', t171, t193, t211
```
```python
# Python — 변환 코드에 삽입 (남겨둬도 무해: CHK_DIR 없으면 no-op)
chk_dump('03_thresholds', t171=t171, t193=t193, t211=t211)
```

- 환경변수 `CHK_DIR`가 비어 있으면 양쪽 다 **아무것도 하지 않는다**. 배포 코드에 남아도 안전.
- IDL 쪽은 `create_struct`로 변수명을 보존해 `probe_<id>.sav`(`/COMPRESS`)로 저장.
- Python 쪽은 `np.savez_compressed`로 `probe_<id>.npz` 저장.
- 변수명은 **호출자 기준 원래 이름**을 쓴다 (IDL은 `scope_varname` 자동 추출, 실패 시 `names=` 키워드로 명시).

### 1.2 probe id 규칙

- 형식: `NN_짧은이름` (예: `01_input`, `05_ratio_masks`, `99_final`). NN은 실행 순서 — 비교기는 사전순 = 실행순으로 처리한다.
- **IDL 호출부에서 id는 반드시 작은따옴표로**: `chk_dump, '01_input', ...`.
  큰따옴표+숫자 시작(`"01..."`)은 IDL이 **8진수 리터럴**로 파싱해 Syntax error가 난다 (셀프테스트에서 실증).
- 세분화로 끼워 넣을 때는 `05a_`, `05b_` 처럼 접미 문자를 쓴다.
- 루프 내부 probe는 기본 금지. 꼭 필요하면 특정 회차만 조건부 덤프 (`if iter eq 0 then chk_dump, ...`)하고 id에 회차를 박는다 (`07_iter0_x`).

### 1.3 삽입 규칙 (계측이 실행을 오염시키지 않도록)

1. **문장 경계에만** 삽입한다 (식 중간, `$` 연속행 사이 금지).
2. 그 시점에 **정의되어 있는 변수만** 덤프한다 (IDL은 미정의 변수를 넘기면 chk_dump가 스킵하고 경고 출력).
3. probe는 **값·흐름을 바꾸지 않는다** — 덤프 대상 변수를 절대 수정하지 않는다.
4. 원본 `inbox/*.pro`는 불변. 계측은 `staging/{이름}_probed.pro` 사본에만.
5. GUI/플롯 블록 안에는 넣지 않는다 (변환 제외 영역 = parity 범위 밖).

### 1.4 probe 배치 전략

- 1차: **블록 경계 기준 8~15개** (입력 로드 직후 / 전처리 후 / 주요 마스크·변환 후 / 최종 직전).
- 입력 직후 probe(`01_input`)는 필수 — 데이터 staging 자체의 불일치를 먼저 걸러낸다.
- **probe 단위 = 발산 국소화 단위.** 최종 출력만 비교하면 "IoU 0.976, 원인 불명"으로 끝난다. probe 사이 구간이 넓으면 그 안의 어느 연산이 원인인지 못 짚으므로, **의심스러운 IDL 내장함수(§4.0)나 비자명한 변환의 직후에 probe를 둬서, 하나의 발산이 하나의 연산으로 좁혀지게** 배치한다. 예(CHIMERA): `03_tricolor`(bytscl 직후)·`04_masks`(임계 직후)·`06_iarr`(contour/POLYFILLV 직후)를 분리해 각 발산을 단일 함수로 특정.
- 발산 구간이 여전히 넓으면 그 구간만 세분화 재계측(§0 적응적 세분화) 후, 통제 실험(§4.0)으로 해당 연산의 규약을 확정한다.
- 배열 크기가 큰 지점(4096² 등)은 압축 저장을 신뢰하되, probe 수가 30개를 넘으면 디스크 사용량을 보고한다.
- **RANDOMU 등 난수 사용 지점**: 난수 이후 첫 probe에서 난수 배열 자체를 덤프하고, Python은 그 값을 **주입**받아 진행한다 (시드 재현 불가 — 아래 4.11).

### 1.5 계측 무결성 확인 (필수, 1회)

계측이 결과를 바꾸지 않았음을 증명해야 오라클로 인정한다:

```
(a) 무계측 기준선: 원본 .pro 실행 → 최종 산출물 保管
(b) 계측 실행: staging 사본 + CHK_DIR 설정 → probes + 최종 산출물
(c) (a)와 (b)의 최종 산출물이 byte/수치 동일한지 확인 → 동일해야 오라클 승인
```
과거 실행 산출물이 이미 있으면 (a)로 재사용 가능 (같은 입력·같은 코드 확인 후).

## 2. policy.yaml 스키마

```yaml
orientation: logical        # logical | memory (아래 3장)
nan_equal: true             # 양쪽 다 NaN → 일치
dtype_strict: false         # dtype 불일치: false=경고, true=FAIL
defaults:                   # dtype kind별 기본 지표
  float:  {metric: allclose, rtol: 1.0e-5, atol: 1.0e-6}   # float32 기준
  double: {metric: allclose, rtol: 1.0e-10, atol: 1.0e-12}
  int:    {metric: exact}
  byte_mask: {metric: iou, min_iou: 0.999}                 # 0/1 byte 배열
checkpoints:                # probe/변수별 오버라이드
  "05_ratio_masks":
    mas: {metric: iou, min_iou: 0.999}
  "99_final":
    seg_map: {metric: labels, min_iou: 0.99}               # 라벨 순열 허용 매칭
waivers:                    # 승인된 불일치 (사용자 승인 필수)
  - checkpoint: "07_rot"
    var: img_rot
    reason: "IDL cubic=-0.5 vs scipy spline 커널 차이 — 사용자 승인 2026-07-09"
    relaxed: {metric: allclose, rtol: 1.0e-3, atol: 1.0e-4}
```

지표(metric) 종류:

| metric | 용도 | 판정 |
|---|---|---|
| `exact` | 정수, 인덱스, 카운트 | `array_equal` |
| `allclose` | 실수 배열/스칼라 | rtol/atol + NaN 정책 |
| `iou` | 이진 마스크 | IoU ≥ min_iou |
| `labels` | 라벨맵(연결 영역 번호) | 라벨 IoU 행렬 → 헝가리안 매칭 → 매칭 IoU 평균 ≥ min_iou, 영역 수 일치 |

## 3. 배열 축(orientation) 정책 — 반드시 이해할 것

세 좌표계가 얽힌다:

| 관점 | `FLTARR(nx, ny)` 의 모습 |
|---|---|
| IDL 논리 인덱스 | `a[i, j]`, i가 빠른 축(x) |
| 메모리(둘 다 동일) | x가 연속 |
| `scipy.io.readsav` 결과 | **shape이 역순** `(ny, nx)` — `sav[j, i] == idl a[i, j]` |
| astropy `fits.getdata` | `(ny, nx)` — FITS NAXIS1=x가 마지막 축 |

**정책 `logical`(기본)**: 변환 Python이 IDL의 논리 인덱스를 보존 (`a[i,j]` 그대로, `np.zeros((nx,ny))`).
→ 비교기는 readsav 배열에 `np.transpose(arr)`(전 축 역순)를 적용해 정렬한 뒤 비교한다.
→ 주의: 이 경우 Python 코드가 `fits.getdata`로 읽은 `(ny,nx)` 배열도 코드 내부 규약에 맞게 다뤄야 한다. 변환 계획에서 **코드 내부 규약을 한 문장으로 선언**할 것 (예: "내부 표현은 `img[y, x]`(numpy 자연) — IDL `a[x, y]`와 논리 대응").

**정책 `memory`**: 변환 Python이 numpy 자연 축(`(ny,nx)`)을 그대로 사용 (사실상 대부분의 이미지 코드가 이 편이 자연스럽다).
→ 비교기는 readsav 배열을 **그대로** 비교한다 (양쪽 다 역순 shape이므로 일치).
→ 이 경우 IDL `a[i,j]` ↔ Python `a[j,i]`로 소스가 전치되어 보인다는 점을 conversion_log에 명시.

프로젝트당 하나를 선택하고 per-variable 오버라이드로 예외를 처리한다. **혼용이 최악이다.**

## 4. 픽셀 좌표·수치 함정 카탈로그

변환·probe 설계·발산 분석 시 이 표를 우선 대조한다. (◆ = 픽셀 좌표 정책 관련)

### 4.0 원칙 — IDL 내장함수 문서를 맹신하지 말고 실측 검증한다

IDL 내장함수는 **문서와 다르게 동작하는 경우가 흔하다.** 문서의 수식/설명을 그대로 옮기면 미세하게(하지만 확실하게) 틀린다. 반드시 **오라클 probe로 실측 대조**하고, 애매하면 **통제 실험(controlled micro-experiment)**으로 규약을 확정한다.

실전에서 발견된 대표 사례(CHIMERA):
- `BYTSCL`: 문서상 `top`이지만 실제 스케일은 `(top+0.9999)/(max-min)` — `top/range`로 옮기면 ~18% 픽셀 불일치.
- `POLYFILLV`: skimage `draw.polygon`과 픽셀 포함 규약이 다름(좌하단 셀 vs 중심) → 결과가 정확히 1픽셀 시프트.
- `MEDIAN`: 짝수 N에서 상위 원소 반환(평균 아님), `/EVEN`일 때만 평균.
- `STDDEV`: ddof=1. `ROUND`: half-away. `FIX`: 0방향 절삭. (§4.5, §4.6)

**통제 실험 기법** (가장 빠르고 확실한 규약 확정법):
1. 규약이 의심되는 내장함수 하나만 떼어, **작은 알려진 입력**(예: 20×20 배열에 10×10 블록)에 IDL과 Python 양쪽으로 적용.
2. 출력의 인덱스 범위·개수·값을 직접 비교 → 오프셋/포함규약/반올림 방향을 즉시 특정.
3. 실데이터 추측보다 빠르고(수 분), 재현 가능하며, 수정의 근거가 됨.
   - 예: `a[5:14]=1` 블록 → IDL POLYFILLV은 `[4..13]`, draw.polygon은 `[5..14]` → "정확히 −1" 확정.

**규칙**: 새 IDL 내장함수를 매핑할 때는 (a) 오라클 probe가 그 함수 직후를 지나도록 probe를 배치하거나, (b) 통제 실험으로 규약을 확정한 뒤 변환한다. "문서에 이렇게 써 있으니 맞겠지"는 금지.

### 4.1 ◆ FITS/WCS 원점
- FITS `CRPIX`는 **1-based**, 픽셀 중심이 정수 좌표.
- IDL 배열은 0-based → SSW 코드가 `crpix-1`을 이미 적용했는지 원본에서 확인.
- astropy `wcs_pix2world(..., origin)`의 `origin` 인자(0 또는 1) 선택 실수가 정확히 1픽셀 오프셋을 만든다.
- sunpy `Map.reference_pixel`은 이미 0-based(CRPIX−1)다.

### 4.2 ◆ 리샘플 격자 정렬 (0.5픽셀 함정)
- IDL `CONGRID(a, nx2, ny2)`: 기본은 최근접, `/INTERP` 시 x축만 선형이 아니라 전체 규약이 바뀜. `/CENTER` 여부에 따라 샘플 격자가 0.5픽셀 이동. `MINUS_ONE` 키워드는 끝점 포함 방식 변경.
- `REBIN`: 정수배만, 축소는 이웃 평균, 확대는 선형 — scipy `zoom`과 커널이 다르다.
- scipy `ndimage.zoom`, skimage `resize`, cv2 `resize`는 각각 격자 정렬 규약이 다르다.
- **대응**: 리샘플은 blind 매핑하지 말고, 축별 소스 좌표식을 원본과 대조해 명시적으로 재현한다. 발산 시 진단 시그니처는 "가장자리 dipole" (5장).

### 4.3 ◆ 회전/시프트
- IDL `ROT(a, ang, mag, x0, y0)`: 회전 중심 지정 규약 + `cubic=-0.5`는 **cubic convolution** (scipy `order=3` B-spline과 다른 커널!).
- scipy `ndimage.rotate/shift`: spline 기반, `mode`(경계 외삽)도 IDL `missing`과 다름.
- **대응**: bilinear(`order=1`)로 통일 가능한지 원본 키워드 확인. cubic이 필수면 cubic convolution을 직접 구현하거나 waiver.

### 4.4 ◆ 보간 함수
- IDL `INTERPOLATE(a, x, y)`: 기본은 격자 밖 **클램프**(가장자리 값), `missing=` 지정 시 대체값.
- scipy `map_coordinates`: `mode='nearest'`가 클램프 근사, 기본 `mode='constant'(0)`은 다르다. `order=1`이 bilinear.

### 4.5 ◆ 반올림/절삭
- IDL `ROUND`: half-away-from-zero (2.5→3, −2.5→−3).
- `np.round`/Python `round`: **half-even** (2.5→2). → 인덱스 계산에 쓰이면 off-by-one 픽셀 발생.
  등가 구현: `np.floor(x + 0.5)` (음수는 `np.trunc(x + np.copysign(0.5, x))`).
- IDL `FIX`: 0 방향 절삭 = `np.trunc` (`np.floor` 아님 — 음수에서 다름).
- 정수 나눗셈: IDL `5/2=2`, Python `5/2=2.5` → `//` 필요. 단 IDL 음수 정수 나눗셈은 0 방향(−5/2=−2), Python `//`은 −∞ 방향(−3)이라 **음수에서 다르다**.

### 4.6 통계 함수
- `STDDEV`/`VARIANCE`: IDL은 N−1 → `np.std(a, ddof=1)` 명시.
- `MEDIAN`: **IDL 기본은 짝수 N에서 상위 원소** (평균 아님!). `/EVEN`일 때만 평균 = numpy 기본. → `np.median`과 다르면 여기부터 의심.
- `MEAN`/`TOTAL`: float32 입력이면 IDL은 float32 누적(`/DOUBLE` 없으면). numpy는 pairwise 합산 → 큰 배열에서 수 ULP 차이. rtol로 흡수하되, `np.sum(a, dtype=np.float32)`로 좁힐 수 있다.

### 4.7 SMOOTH/CONVOL/HISTOGRAM
- `SMOOTH`: 기본은 **가장자리 미처리**(원값 유지), `/EDGE_TRUNCATE`일 때만 경계 처리 — scipy `uniform_filter`와 경계 규약 다름.
- `CONVOL`: 기본 경계 0-패딩 아님(가장자리 스킵), `/EDGE_*` 키워드 확인. scipy `convolve`와 커널 뒤집힘/정규화(`/NORMALIZE`) 차이.
- `HISTOGRAM`: `binsize/min/max` 규약, 마지막 bin 포함 규칙, `REVERSE_INDICES` 구조 → `np.histogram` bin 경계와 다름. 임계 근처 픽셀이 옆 bin으로 가면 마스크가 달라진다.

### 4.8 BYTSCL/스케일링
- `BYTSCL(a, min=, max=, top=)`: `byte(top * (a-min)/(max-min))`의 내부 반올림 규약 + NaN 처리. 시각화용이면 parity 범위에서 제외 권장, 알고리즘에 쓰이면 (예: 다채널 임계 마스크) 정확 재현 필수: `np.clip` + 절삭 방식 확인.

### 4.9 WHERE / 1D 첨자
- `WHERE`→ 결과 없음 −1 vs 빈 배열. `count` 동시 반환 패턴 확인.
- IDL 1D 첨자 `a[idx]`는 다차원 배열에도 평탄(flat) 인덱스로 동작 → numpy `a.flat[idx]` 또는 `np.unravel_index`. **orientation 정책에 따라 flat 순서가 다르다** — logical 정책이면 IDL flat 순서는 Fortran order: `np.ravel(a, order='F')` 기준으로 환산.

### 4.10 dtype/오버플로
- IDL 기본 정수는 16-bit! (`COMPILE_OPT IDL2` 없으면). `FIX(70000)`은 오버플로된다 — 원본이 이 동작에 의존하는지 확인.
- BYTE 연산은 mod 256 랩어라운드 → numpy uint8 동일하지만 중간 승격 규칙이 다르다.
- parity 단계에서는 **IDL과 같은 dtype**(float32/int16/uint8)을 유지한다. float64 승격은 통과 후.

### 4.11 난수/시간 의존
- `RANDOMU/RANDOMN` 시드는 numpy로 재현 불가 → IDL에서 난수 배열을 probe로 덤프하고 Python에 **주입**한다.
- `SYSTIME` 등 시간 의존 분기는 입력으로 고정한다.

### 4.12 천문 역서/상수 (태양물리)
- `pb0r`, `get_sun` (SSW) vs `sunpy.coordinates.sun.*`: B0/P각/반지름이 arcsec 수준에서 다를 수 있다 → 림 근처 마스크 픽셀이 달라진다.
- **대응**: 오라클 IDL이 계산한 역서 값을 probe로 덤프하고 Python에 그대로 주입하는 것이 정석 (parity 목적). sunpy 값 사용은 통과 후 옵션 + waiver.
- `anytim` vs astropy Time: 기준계(UTC/TAI), 윤초 확인.

### 4.13 문자열/포맷 출력
- 수치를 담은 .txt 출력은 문자열 비교하지 말고 **파싱 후 수치 비교**한다 (`1.00000e+00` vs `1.0`).

## 5. 발산 시그니처 진단표

compare_probes.py가 실패 배열에 자동 진단을 시도한다. 수동 분석 시에도 이 표를 쓴다:

| 시그니처 (diff 이미지/통계) | 유력 원인 | 우선 확인 |
|---|---|---|
| 전치하면 일치 (`transpose_match=true`) | 축 순서/orientation 위반 | 3장 정책, REFORM/TOTAL axis |
| 정수 시프트로 일치 (`shift_match: {axis0, axis1}` — 비교 orientation 기준 축) | 원점/CRPIX/서브어레이 off-by-one | 4.1, hextract/서브어레이 경계 |
| 가장자리 dipole (경계에서만 큰 diff) | 리샘플/보간 격자 0.5px 불일치 | 4.2, 4.3, 4.4 |
| 선형 스케일 `py ≈ a·idl + b` | 정규화/단위/노출 보정 차이 | BYTSCL, 노출시간, DN/s |
| 임계값 경계에서만 점점이 다름 | 반올림/median/histogram 규약 | 4.5, 4.6, 4.7 |
| 한쪽만 NaN | NaN 전파/`/NAN` 키워드 | MIN/MAX/TOTAL의 /NAN |
| 라벨 수 같고 번호만 다름 | 라벨 순서 (스캔 순서 차이) | metric을 `labels`로 |
| 완전 무관 (상관 없음) | 잘못된 변수 대응/probe 위치 불일치 | probe 계획 재확인 |
| 미세 ULP 수준 (rtol 살짝 초과) | 누적 순서/dtype 승격 | 4.6 TOTAL, rtol 재검토 |

## 6. 비교기 실행

```bash
# 서버, torchV2 환경에서
python tools/compare_probes.py \
    --oracle {작업경로}/probes/idl \
    --py     {작업경로}/probes/py/run_01 \
    --policy {작업경로}/policy.yaml \
    --out    {작업경로}/reports/parity/run_01 \
    --png
# exit 0 = ALL PASS / 1 = 발산 있음 / 2 = 실행 오류
```

산출:
- `report.json` — 기계용 (루프 제어)
- `report.md` — probe×변수 표, 최초 발산 강조, 통계(max_abs/rel, mismatch_frac, argmax 위치), 자동 진단
- `diff_{probe}_{var}.png` — 실패한 2D 배열의 [oracle | python | diff] 패널

## 7. 오라클 실행·캐시 규칙

1. 실행 전 점검: 라이선스 (`idl -e 'print,!version'`), 입력 파일 존재, `CHK_DIR` 생성.
2. 배치는 `tools/idl/batch_template.pro`에서 생성 — 반드시 `exit`로 끝나고, 런처 호출은 `< /dev/null` + timeout.
3. 실행 로그(`logs/idl_run_*.log`)에서 `>>> BATCH done` 확인 + 기대 산출물 존재 확인. 없으면 실패로 처리 (로그 첨부).
4. 캐시 키: `sha256(계측 .pro) + sha256(입력 파일 목록·내용) + sha256(probe 계획)` 요약 → `_cache/oracle/{key}/`에 probes와 최종 산출물, `meta.json`(IDL 버전, SSW 경로, 실행 시각, 입력 manifest) 저장.
5. 같은 키가 캐시에 있으면 재실행하지 않는다. Python 수정 루프는 **절대 IDL을 다시 돌리지 않는다**.
6. 캐시·probe 삭제는 하네스가 하지 않는다 (사용자 안내만).

## 8. parity certificate (최종 보고 필수 항목)

- 환경 provenance: IDL 버전/SSW 경로/라이선스 서버, Python/패키지 버전, 실행 호스트
- 입력 manifest: 파일, sha256, 출처(루트 A/B/C), 날짜
- probe 계획 버전 + 오라클 캐시 키
- probe×변수 전체 판정표 + 사용한 정책(policy.yaml 사본 첨부)
- waiver 목록 (원인·완화 기준·승인 일자)
- 루프 이력: 회차별 발산 → 수정 요약
- 한계 명시: "이 parity는 입력 N세트, 이 SSW 버전, 이 정책 하에서 성립"
