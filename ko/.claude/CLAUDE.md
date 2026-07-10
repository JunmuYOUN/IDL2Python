# 08-IDL2Python-Parity — 실행 기반 IDL→Python 변환·검증 하네스

IDL(`.pro`) 파일을 Python으로 변환하고, **원본 IDL과 변환된 Python을 실제 환경에서 실행하여
체크포인트 단위로 수치를 대조(parity check)**하고, 불일치가 사라질 때까지 수정 루프를 도는 파이프라인.

07-idl2python(구문 변환 + 자체 테스트)의 확장판이다.
07과의 결정적 차이: **기대값을 추정하지 않는다. 기대값은 항상 원본 IDL을 실제로 실행해 얻은 산출물(오라클)이다.**

## 07 대비 무엇이 다른가

| 항목 | 07 (구문 변환) | 08 (실행 검증) |
|---|---|---|
| 정답 기준 | 에이전트가 추정한 기대값 / 물리적 타당성 | **원본 IDL 실제 실행 산출물 (오라클)** |
| 검증 단위 | 최종 출력 위주 | **체크포인트(probe) 단위 중간값 전부** |
| 불일치 시 | REVISE 피드백 (정적 리뷰) | **최초 발산 지점(first divergence)으로 버그 위치 자동 국소화 → 수정 → Python만 재실행** |
| 데이터 | 합성 우선 | 실데이터 3루트 (사용자 제공 / 요청 / 자동 다운로드) + 합성 |
| 좌표/수치 규약 | 매핑 표 | **policy.yaml로 명시적 선언 + 비교기가 기계적으로 집행** |

## 에이전트 팀 구성표

| 에이전트 | 역할 | 핵심 기능 |
|---|---|---|
| **idl-analyzer** | IDL 코드 분석 | .pro 파싱, 의존성, 변환 계획, **probe(체크포인트) 계획, 데이터 요구 명세** |
| **python-translator** | Python 변환 | 구문 변환, 라이브러리 매핑, **twin probe 삽입, dtype 충실 변환, 발산 보고 기반 수정** |
| **parity-runner** | 실행·대조 | 환경 점검, 데이터 staging, **IDL 오라클 실행(계측/무결성/캐시), Python 실행, compare_probes 비교, 발산 보고** |
| **test-engineer** | 회귀 테스트 | **오라클 고정(oracle-pinned) pytest 생성**, 엣지 케이스, 병렬 실행 |
| **conversion-reviewer** | 품질 검토 | 코드 리뷰 + **parity 보고 기반 PASS/REVISE**, waiver 심사 |

## 파이프라인

```
Phase 0  소스 수집 (로컬/Git/URL → inbox/)
    ▼
Phase 1  분석 (idl-analyzer)
         변환 계획 + probe 계획 + 데이터 요구 명세
    ▼
       ★ 사용자 승인 ★  (계획/probe/데이터 방식)
    ▼
Phase 2  검증 데이터 확보 (parity-runner)
         루트A 사용자 제공 / 루트B 사용자에게 요청 / 루트C 자동 다운로드
    ▼
Phase 3  IDL 오라클 실행 (parity-runner)        ┐
         계측 사본 생성 → 무결성 확인 → probes/idl/*.sav → 캐시     │ 3·4는 병렬 가능
Phase 4  Python 변환 (python-translator, twin probe 포함)          ┘
    ▼
Phase 5  ★ 패리티 루프 ★
         ┌────────────────────────────────────────────┐
         │ 5a Python 실행 → probes/py/run_NN/*.npz     │
         │ 5b compare_probes.py → parity_report        │
         │ 5c ALL PASS → Phase 6                       │
         │    DIVERGE  → 발산 보고(최초 발산 지점,      │
         │               시그니처 힌트) → translator    │
         │               수정 → 5a (IDL 재실행 없음)    │
         └────────────────────────────────────────────┘
         한도: fix_loop_max(기본 5), probe 세분화 refine_max(기본 2, IDL 재계측 필요)
    ▼
Phase 6  회귀 테스트 고정 (test-engineer — 오라클 probe를 golden으로 하는 pytest)
    ▼
Phase 7  품질 검토 (conversion-reviewer) → PASS / REVISE(→Phase 5)
    ▼
Phase 8  최종 보고 — parity certificate (환경 provenance + 입력 manifest + 지표 + waiver)
```

## Probe(체크포인트) 프로토콜 — 요약

상세는 `parity-protocol` 스킬. 핵심만:

1. **양쪽 동일 형태의 덤프 함수**를 쓴다.
   - IDL: `chk_dump, '03_masks', mas, msk, mak` (`tools/idl/chk_dump.pro`)
   - Python: `chk_dump('03_masks', mas=mas, msk=msk, mak=mak)` (`tools/chk_dump.py`)
   - 환경변수 `CHK_DIR`가 비어 있으면 양쪽 모두 **no-op** → 계측 코드를 지우지 않고도 비활성화 가능
2. probe id는 `NN_이름` (실행 순서 = 사전순). probe 계획(`analysis/04_probe_plan.md`)에 위치·변수·근거를 기록한다.
3. **원본 불변**: probe는 `staging/`의 계측 사본에만 삽입한다. inbox/ 원본은 절대 수정하지 않는다.
4. **계측 무결성 확인**: 계측 사본의 최종 산출물이 무계측 실행(기준선)과 동일함을 1회 확인 후에만 오라클로 인정한다.
5. **삽입 규칙**: 문장 경계에만, 그 시점에 정의된 변수만, 부작용(값 변경/흐름 변경) 금지.
6. probe는 처음부터 촘촘히 깔지 않는다 — 굵게(블록 경계 ~10개) 시작하고, 발산 구간만 세분화 재계측한다.

## 수치·좌표 정책 (policy.yaml)

비교 기준은 에이전트의 재량이 아니라 **`{작업경로}/policy.yaml`에 선언**하고 `tools/compare_probes.py`가 기계적으로 집행한다.
템플릿: `config/policy.template.yaml`. 프로젝트 시작 시 복사 후 Phase 1에서 확정한다(사용자 승인 대상).

- **orientation** (배열 축 정책): `logical`(기본) = Python이 IDL의 논리 인덱스 `a[i,j]`를 보존 → 비교기가 readsav 배열의 축을 뒤집어 정렬. `memory` = Python이 numpy 자연 축(뒤집힌 shape)을 사용 → 그대로 비교. **readsav는 IDL 배열의 차원을 역순으로 돌려준다**는 사실이 이 정책의 근거다.
- **dtype 충실**: parity 단계에서는 IDL의 정밀도를 따른다 (`FLTARR`→`np.float32`). float64 승격은 parity 통과 후 별도 리팩터링으로만.
- **허용 오차**: float32 기본 rtol=1e-5/atol=1e-6, 마스크는 IoU, 라벨맵은 라벨 순열 허용 매칭(IoU 행렬 + 헝가리안).
- **최종 산출물의 지표·임계값은 고정값이 아니다**: idl-analyzer가 코드 특성(임계 분기 민감도, 라벨 구조 등)을
  근거로 **제안**하고, G1에서 사용자가 수치를 **확정**한다(human-in-the-loop). 중간 probe는 기본적으로 엄격 기준.
- **NaN**: 양쪽 다 NaN이면 일치(기본).
- 픽셀 좌표 규약(FITS CRPIX 1-based, 리샘플 격자 정렬, 반올림 방식, 보간 커널 차이 등)의 함정 카탈로그와 발산 시그니처 진단표는 `parity-protocol` 스킬에 있다. **변환·비교·리뷰 전에 반드시 읽는다.**

## 검증 데이터 확보 — 3루트

상세는 `data-acquisition` 스킬.

| 루트 | 방식 | 처리 |
|---|---|---|
| **A. 사용자 제공** | 사용자가 경로 제시 | `data/`로 staging + manifest 기록 |
| **B. 요청** | 하네스가 필요한 데이터 스펙(계기/파장/시각/레벨/포맷)을 표로 제시 | 사용자가 주거나 다운로드 승인 |
| **C. 자동 확보** | `tools/fetch_data.py` (VSO/Fido는 무인증, JSOC은 이메일 필요) | 다운로드 전 사용자 승인, manifest+sha256 기록 |

- 다운로드 전에 **서버에 이미 있는 데이터부터 검색**한다 (find). 있으면 재사용.
- **JSOC 이메일은 하드코딩 금지, 첫 사용 전에 사용자에게 질문.**
- parity는 입력 1세트로 시작하되, 최종 PASS 전 **가능하면 2세트 이상**(다른 날짜/엣지 케이스)으로 확인한다.
- 합성 데이터는 단위 parity(개별 함수)에는 유용하지만, 최종 판정은 실데이터로 한다.

## 실행 환경 — 배포 전제

이 하네스는 **GitHub 배포를 전제**로 한다. 특정 서버에 묶이지 않으며, 사용자가 자신의 환경에서
자신의 IDL 라이선스(정식/**90일 트라이얼 포함**)로 오라클을 실행한다.

- **`config/env.yaml`이 단일 소스**다. 커밋되지 않는다(.gitignore) — 호스트/계정/사이트 경로는
  여기에만 둔다. 신규 환경에서는 `config/env.template.yaml`을 복사해 채운다.
- **IDL**: `idl.bin` 실행 파일 + (태양물리 코드일 때만) `idl.ssw` SolarSoft 루트.
  SSW가 비어 있으면 런처가 순수 IDL로 실행한다. 헤드리스 실행은
  `tools/run_idl_headless.csh` + 배치 `.pro` (`IDL_STARTUP` 방식, 반드시 `exit` 종료,
  stdin `</dev/null`, timeout 적용). 오라클 실행 전 라이선스 도달을 점검한다 (`license_check`).
- **Python**: conda 환경 또는 PATH의 python. 필요 패키지: numpy/scipy/astropy/pyyaml
  (+ 대상 코드에 따라 sunpy/aiapy/drms/skimage/matplotlib), Phase 6에 pytest.
- **exec.mode**: `local`(세션이 IDL 호스트에서 구동, 기본) 또는 `ssh`(다른 호스트에서
  `ssh {host} "..."`로 감싸 실행). 세션이 어디서 돌든 **모든 실행은 IDL이 있는 호스트에서** 일어난다.
- **GPU 불필요** — IDL도 비교기도 CPU만 쓴다.
- 배치 검증: 새 환경에 설치하면 먼저 `tools/selftest/`(probe→비교 왕복, ~5분)를 돌려 확인한다.

## 오라클 캐시

- IDL 실행은 느리다. 오라클 산출물은 `_cache/oracle/{key}/`에 보존한다.
  `key = sha256(계측 .pro) × sha256(입력 파일들) × probe 계획 해시` (요약 12자).
- 패리티 루프에서 Python 수정 후에는 **IDL을 재실행하지 않는다** (캐시 재사용). IDL 재실행이 필요한 경우는 probe 계획 변경(세분화)뿐이다.
- probe 저장은 압축(`SAVE, /COMPRESS`, `np.savez_compressed`)을 쓴다. 대형 배열(4096² 등)이 다수면 디스크 사용량을 사용자에게 보고한다.
- 캐시는 **append-only**. 정리(삭제)는 사용자만 한다 — 하네스는 삭제 명령을 실행하지 않는다.

## 절대 규칙 (상위 서버 규칙 편입)

- **서버에서 `rm` 등 삭제 명령 금지.** 어떤 형태로도 실행하지 않는다.
- **생성하는 모든 코드/도구에 `os.remove`, `shutil.rmtree`, `os.unlink`, `pathlib.Path.unlink` 등 삭제 계열 사용 금지.** (tools/*는 이 규칙을 준수하도록 작성되어 있다 — 덮어쓰기만 한다)
- 삭제가 필요하면 실행하지 말고 사용자에게 명령어만 안내한다.
- 원본 .pro와 오라클 산출물은 불변 취급한다.

## 승인 게이트 · 루프 한도 · waiver

| 게이트 | 시점 | 내용 |
|---|---|---|
| G1 | Phase 1 후 | 변환 계획 + probe 계획 + policy.yaml + 데이터 확보 방식 |
| G2 | Phase 2 중 | 외부 다운로드 실행 (용량/출처 고지) |
| G3 | Phase 7 후 | 최종 결과 + parity certificate |

| 루프 | 한도 (env.yaml) | 초과 시 |
|---|---|---|
| 패리티 수정 루프 (5a-5c) | fix_loop_max = 5 | 현 상태 + 남은 발산 목록 보고, 사용자 에스컬레이션 |
| probe 세분화 (IDL 재계측) | probe_refine_max = 2 | 동일 |
| 데이터 재확보 | 1회 | 대체 루트 제안 |

**waiver(허용된 불일치)**: 원본 IDL 쪽 버그, 라이브러리 커널 차이(예: IDL cubic 컨볼루션 vs scipy spline), 천문 상수/역서 차이 등 **의도적으로 남기는 차이**는 반드시 (1) 원인 분석, (2) 완화된 기준, (3) 사용자 승인을 갖춰 `policy.yaml`의 `waivers:`에 기록한다. waiver 없는 발산이 남아 있으면 PASS는 없다.

## 데이터 전달 규칙

| 에이전트 | 출력 디렉토리 |
|---|---|
| idl-analyzer | `{작업경로}/analysis/` |
| python-translator | `{작업경로}/converted/` |
| parity-runner | `{작업경로}/staging/`, `data/`, `probes/`, `reports/parity/`, `logs/run_*` |
| test-engineer | `{작업경로}/tests/` |
| conversion-reviewer | `{작업경로}/reports/` |
| 공통 | `{작업경로}/logs/conversion-note.md` (누적 기록, 수정 금지) |

1. 각 에이전트는 자신의 디렉토리에만 쓴다. 남의 출력은 읽기 전용.
2. 중간 산출물은 삭제하지 않고 보존한다. 루프 회차는 `run_01/`, `run_02/`…로 구분한다.
3. 원본 .pro는 `inbox/`에 복사 후 읽기 전용으로만 접근한다.

## 작업 공간 구조

```
{작업경로}/
├── inbox/            원본 .pro (읽기 전용)
├── analysis/         00 인벤토리, 01 의존성, 02 구문 보고, 03 변환 계획,
│                     04 probe 계획, 05 데이터 요구 명세
├── policy.yaml       수치·좌표 정책 (config/policy.template.yaml에서 복사)
├── staging/          계측된 IDL 사본 + 배치 .pro (원본과 분리)
├── data/             검증 입력 데이터 + manifest.jsonl
├── converted/        변환된 Python (+ requirements.txt, conversion_log.md)
├── tests/            oracle-pinned pytest
├── probes/
│   ├── idl/          오라클 probe (*.sav) — 캐시에서 복사/링크
│   └── py/run_NN/    후보 probe (*.npz), 루프 회차별
├── reports/
│   ├── parity/       parity_report.md/json, divergence_*.md, diff PNG
│   ├── 00_review_report.md
│   └── 09_parity_certificate.md
└── logs/             conversion-note.md, idl_run_*.log, py_run_*.log
```

## 스킬 구성

| 스킬 | 역할 |
|---|---|
| **idl2python-orchestrator** | 파이프라인 총괄 (phase 순서, 게이트, 루프, 병렬) |
| **parity-protocol** | probe 규약, policy.yaml 스키마, 좌표·수치 함정 카탈로그, 발산 시그니처 진단표, 캐시 규칙 |
| **data-acquisition** | 3루트 데이터 확보 결정 트리, fetch_data.py 사용법, manifest 규칙 |
| **idl-python-mapping** | IDL↔Python 구문 매핑 레퍼런스 (07 이관) |
| **test-protocol** | pytest 방법론 (07 이관 — 기대값은 오라클 probe로 대체) |
| **web-source-collector** | 웹 URL에서 .pro 수집 (07 이관) |

## 도구 (tools/) — 결정론적 스크립트

에이전트 재량이 아니라 스크립트가 집행하는 부분:

| 도구 | 역할 |
|---|---|
| `tools/idl/chk_dump.pro` | IDL probe 덤프 (struct → .sav, CHK_DIR 없으면 no-op) |
| `tools/idl/batch_template.pro` | 헤드리스 오라클 배치 템플릿 |
| `tools/run_idl_headless.csh` | SSW-IDL 헤드리스 런처 |
| `tools/chk_dump.py` | Python probe 덤프 (.npz) |
| `tools/compare_probes.py` | **비교기** — 정책 적용, 축 정규화, 지표 산출, 최초 발산, 시그니처 진단, 보고서/PNG |
| `tools/fetch_data.py` | VSO/JSOC/URL 데이터 확보 + manifest |

## 필수 입력 정책

시작 전 확보 (누락 시 질문):

| 항목 | 내용 |
|---|---|
| IDL 소스 | 로컬/디렉토리/Git/웹 URL |
| 변환 목적 | 마이그레이션/통합/학습 등 |
| 작업 경로 | 산출물 저장 위치 |
| **검증 데이터 방식** | 루트 A(제공)/B(요청)/C(자동) 또는 "서버 내 기존 데이터 탐색" |
| **오라클 실행 범위** | 전체 프로그램 1회인지, 특정 서브루틴 단위인지 |

## 사용 언어

- 사용자 대면: 한국어 / 코드·설정·변수명: 영어 / 보고서: 한국어

## 핵심 원칙

1. **오라클이 정답이다**: 기대값을 추정하거나 손으로 만들지 않는다. 반드시 IDL 실행 산출물과 대조한다.
2. **원본 불변**: inbox/ 원본과 오라클 산출물은 수정·삭제하지 않는다.
3. **정책은 선언, 집행은 스크립트**: 허용 오차·축 정책을 policy.yaml에 선언하고 compare_probes.py가 판정한다. 에이전트가 "대충 비슷하다"고 판단하지 않는다.
4. **발산은 국소화한다 (probe 단위 비교)**: 최종 출력만 비교하지 않는다. 최초 발산 체크포인트를 찾아 해당 블록만 수정한다. probe는 하나의 발산이 하나의 연산으로 좁혀지게, 비자명한 변환·의심스러운 내장함수 직후에 배치한다 (parity-protocol §1.4).
5. **IDL 내장함수 문서 불신**: 내장함수는 문서와 다르게 동작할 수 있다(BYTSCL, POLYFILLV, MEDIAN 등). 문서 수식을 맹신하지 말고 오라클 probe 실측 또는 통제 실험으로 규약을 확정한 뒤 변환한다 (parity-protocol §4.0).
6. **IDL 재실행 최소화**: 오라클은 캐시하고, 수정 루프에서는 Python만 재실행한다.
7. **dtype 충실 → 이후 관용화**: parity 통과 전에는 IDL 정밀도(주로 float32)를 따른다.
8. **waiver는 명시·승인·기록**: 설명 없는 불일치를 남기지 않는다.
9. **판단 과정 기록**: conversion-note.md에 누적. 루프 회차별 산출물 보존.
10. **승인 게이트 준수**: G1(계획), G2(다운로드), G3(최종).
11. **삭제 금지**: 서버에서 rm 계열 금지, 코드에 삭제 API 금지.

## Auto-memory policy (전면 비활성)

이 하네스에서는 에이전트 CLI의 자동 메모리 기능을 사용하지 않는다. 다른 세션의 기록이 무관한 작업에 간섭하는 것을 막기 위함.

- **읽기 금지**: 에이전트 자동 메모리(`MEMORY.md` 포함)를 의사결정 근거로 쓰지 않는다. 컨텍스트에 주입되더라도 무시한다.
- **쓰기 금지**: 자동 메모리를 만들거나 갱신하지 않는다. "기억해줘" 요청에는 메모리 비활성임을 알리고 작업 디렉토리 내 문서를 대안으로 제안한다.
- 일반 사용자 파일(README, 노트 등)은 정상 참조한다.
