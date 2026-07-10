---
name: data-acquisition
description: >
  parity 검증용 입력 데이터 확보 프로토콜.
  사용자 제공(루트A) / 사용자에게 요청(루트B) / 자동 다운로드(루트C)의
  결정 트리, 서버 내 기존 데이터 재사용, fetch_data.py 사용법,
  manifest 기록 규칙, JSOC 이메일 규칙을 정의한다.
  키워드: 데이터 확보, 다운로드, VSO, Fido, JSOC, drms, FITS,
  테스트 데이터, manifest, sha256, 데이터 요청, staging
---

# Data-Acquisition — 검증 데이터 확보 프로토콜

## 0. 원칙

1. **재사용 우선**: 다운로드 전에 서버에 이미 있는 데이터를 먼저 찾는다.
2. **다운로드는 승인 후** (게이트 G2): 출처·용량·저장 위치를 고지하고 승인받는다.
3. **모든 입력은 manifest에 기록**: 무엇으로 검증했는지 재현 가능해야 parity certificate가 성립한다.
4. **원본 데이터 불변**: staging은 복사/링크로만. 삭제하지 않는다.

## 1. 결정 트리

```
데이터 요구 명세 (analysis/05_data_requirements.md) 확정
    │
    ├─ 사용자가 경로를 줬다 ──────────────▶ 루트 A: staging + manifest
    │
    ├─ 서버 내 검색 (find /userhome/... )
    │    적합 파일 발견 ──────────────────▶ 루트 A': 재사용 (사용자에게 고지)
    │
    ├─ 공개 아카이브로 충분 (VSO/Fido) ───▶ 루트 C: fetch_data.py vso (승인 후)
    │
    ├─ JSOC 필요 (특정 시리즈/레벨) ───────▶ 루트 C: fetch_data.py jsoc
    │                                        (이메일 필요 — 사용자에게 질문)
    │
    └─ 자동 확보 불가/모호 ────────────────▶ 루트 B: 요구 스펙 표를 제시하고
                                             사용자에게 제공/선택 요청
```

## 2. 데이터 요구 명세 형식 (idl-analyzer 산출, 루트 B 제시용)

```markdown
# 검증 데이터 요구 명세

| # | 항목 | 요구 | 근거 (원본 코드) |
|---|---|---|---|
| 1 | 계기/파장 | SDO/AIA 171, 193, 211 Å | solar_seg.pro L39-41 파일 패턴 |
| 2 | 자기장 | SDO/HMI LOS magnetogram | L42 `*hmi*` |
| 3 | 레벨 | level 1 또는 1.5 (코드가 자체 판별) | L68 |
| 4 | 시각 동시성 | 4장 모두 ±수 분 이내 | 알고리즘 가정 |
| 5 | 파일명 규약 | `*00171*.f*`, `*hmi*.f*` | findfile 패턴 |
| 6 | 포맷 | FITS full-disk 4096² | |

권장 세트 수: 2 이상 (다른 날짜, 가능하면 CH 많은 날 + 적은 날)
```

## 3. fetch_data.py 사용법 (루트 C)

서버 torchV2 환경에서 실행:

```bash
# VSO (인증 불필요)
python tools/fetch_data.py vso \
    --time "2017-01-01T00:00:00" --instrument aia --wavelength 193 \
    --out {작업경로}/data

# JSOC (이메일 필수 — 사용자에게 받은 값만 사용)
python tools/fetch_data.py jsoc \
    --series "aia.lev1_euv_12s" --time "2017-01-01T00:00:00/1m" \
    --segments image --email {사용자제공} --out {작업경로}/data

# 직접 URL
python tools/fetch_data.py url --url "https://..." --out {작업경로}/data
```

- 모든 서브커맨드는 `{out}/manifest.jsonl`에 한 줄씩 기록한다: 시각, 루트, 쿼리, 파일, sha256, 크기.
- 실패 시 1회 재시도 후 루트 B로 전환한다 (사용자에게 보고).

## 4. JSOC 이메일 규칙

- **하드코딩 절대 금지.** 설정 파일에도 저장하지 않는다.
- 첫 사용 전에 사용자에게 질문: "JSOC 다운로드에 등록된 이메일이 필요합니다. 사용할 이메일을 알려주세요 (export.jsoc.stanford.edu에 등록되어 있어야 합니다)."
- 세션 내 재사용은 가능하되 conversion-note.md에는 "사용자 제공 이메일 사용"이라고만 기록한다 (주소 자체는 기록하지 않음).

## 5. staging 규칙

- 원본 코드의 **파일명 규약**(예: findfile 패턴 `*00171*`, `*hmi*`)에 맞춰 `data/` 하위에 복사 또는 심볼릭 링크로 배치한다.
- 파일명 변경이 필요하면 복사본에만 적용하고 manifest에 원본→staging 대응을 기록한다.
- 입력 세트가 여러 개면 `data/set_01/`, `data/set_02/`… 로 구분한다.
- staging 직후 `01_input` probe 대조로 **양쪽이 같은 입력을 읽었는지**부터 확인한다 (데이터 문제 vs 코드 문제 분리).

## 6. 합성 데이터의 위치

- 개별 함수 단위 parity(서브루틴 하네스)에는 합성 입력이 유용하다 — IDL 쪽도 같은 합성 입력을 읽게 하면 오라클 원칙이 유지된다.
- 단, **최종 판정은 실데이터로** 한다. 합성만으로 PASS를 선언하지 않는다 (실데이터의 NaN, 노출 변화, 헤더 다양성이 함정을 드러낸다).

## 7. 디스크 사용 보고

- 다운로드/probe 산출물이 5 GB를 넘길 것으로 예상되면 사전에 사용자에게 알린다.
- 정리(삭제)는 사용자 몫 — 하네스는 삭제하지 않고, 정리 후보 목록만 제안할 수 있다.
