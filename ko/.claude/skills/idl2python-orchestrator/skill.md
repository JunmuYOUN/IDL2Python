---
name: idl2python-orchestrator
description: >
  IDL .pro 파일을 Python으로 변환하고 실행 기반 수치 대조(parity)까지 완료하는
  파이프라인 총괄 오케스트레이터.
  IDL 변환해줘, .pro 파일 변환, IDL을 Python으로, IDL 코드 변환,
  pro 파일을 py로, IDL 마이그레이션, SSW 코드 변환, SolarSoft 변환,
  IDL 검증, parity, 실행 검증, 오라클 대조, 변환 확인
  요청 시 반드시 이 스킬을 사용할 것.
---

# IDL2Python-Orchestrator — 변환+실행검증 파이프라인 총괄

## 개요

사용자가 IDL .pro를 제시하면 분석 → 데이터 확보 → **IDL 오라클 실행** → 변환 → **패리티 루프(실행·대조·수정)** → 회귀 고정 → 검토의 전 과정을 조율한다.
07 하네스와 달리, 완료 판정은 "테스트 통과"가 아니라 **"원본 IDL 실행 산출물과의 대조 통과(parity PASS)"**다.

## 필수 입력 확인

| # | 항목 | 누락 시 질문 |
|---|---|---|
| 1 | IDL 소스 | "변환할 .pro의 경로/URL은? (로컬·Git·웹 모두 가능)" |
| 2 | 변환 목적 | "변환 목적은? (마이그레이션/통합 등)" |
| 3 | 작업 경로 | "산출물을 저장할 작업 경로는?" |
| 4 | **검증 데이터 방식** | "검증 입력을 어떻게 확보할까요? ① 직접 제공 ② 필요 스펙을 제가 정리해 요청 ③ 자동 다운로드(승인 후) ④ 서버 내 기존 데이터 탐색" |
| 5 | **오라클 범위** | "IDL 실행 대조 범위: 전체 프로그램 1회 실행 기준인가요, 특정 함수/서브루틴 단위인가요?" |

소스 유형 자동 판별(로컬/Git/웹)과 Phase 0 수집은 07과 동일 (`web-source-collector`).

## 파이프라인

```
Phase 0  소스 수집 → inbox/
Phase 1  분석 (idl-analyzer)
         ├ 00~03: 인벤토리/의존성/구문/변환계획 (07 동일)
         ├ 04_probe_plan.md: 체크포인트 계획 (위치·변수·근거, 8~15개)
         ├ 05_data_requirements.md: 검증 데이터 요구 명세
         └ policy.yaml 초안 (config/policy.template.yaml 기반)
    ▼
★ G1 사용자 승인 ★  변환계획 + probe 계획 + policy + 데이터 방식
    ▼
Phase 2  데이터 확보 (parity-runner, data-acquisition 스킬)
         서버 내 재사용 → 루트 A/B/C. 다운로드는 ★G2 승인★
    ▼
Phase 3  IDL 오라클 (parity-runner)        ┐ 3·4 병렬 가능
         계측→무결성→실행→캐시            │ (오라클은 변환과 무관)
Phase 4  Python 변환 (python-translator)   ┘
         twin probe 포함, dtype 충실
    ▼
Phase 5  패리티 루프
         ┌───────────────────────────────────────────────┐
         │ 5a parity-runner: Python 실행 (probes/py/run_NN)│
         │ 5b parity-runner: compare_probes → report       │
         │ 5c 분기:                                        │
         │    ALL PASS ────────────────────▶ Phase 6       │
         │    DIVERGE → divergence brief →                 │
         │        python-translator 수정 → 5a              │
         │        (fix_loop_max=5, IDL 재실행 없음)         │
         │    구간 특정 불가 → probe 세분화                 │
         │        (analyzer 계획 갱신 → Phase 3 재계측,     │
         │         refine_max=2)                           │
         │    waiver 후보(라이브러리 커널 차이 등)           │
         │        → 사용자 승인 요청 → policy.yaml 기록     │
         └───────────────────────────────────────────────┘
    ▼
Phase 6  회귀 고정 (test-engineer)
         오라클 probe를 golden으로 하는 pytest 스위트 생성·실행
    ▼
Phase 7  품질 검토 (conversion-reviewer)
         parity report + waiver + 코드 리뷰 → PASS / REVISE(→Phase 5)
    ▼
★ G3 최종 승인 ★
Phase 8  최종 보고 — reports/09_parity_certificate.md
```

**다중 파일(배치) 모드**: 07과 동일하게 의존성 그룹 병렬 변환하되, 오라클은 **호출 그래프의 진입점 단위**로 잡는다 (파일마다 IDL을 따로 돌리지 않고, 진입점 1회 실행에 여러 파일의 probe를 함께 심는다).

## 승인 게이트

| 게이트 | 시점 | 제시 내용 |
|---|---|---|
| G1 | Phase 1 후 | 변환 계획, probe 계획(개수·위치), policy 초안(orientation/오차), 데이터 확보 방식, 예상 IDL 실행 시간·디스크 |
| G2 | 다운로드 직전 | 출처, 쿼리, 예상 용량, 저장 위치 |
| G3 | Phase 7 후 | parity certificate 요약, waiver 목록, 사용법 |

**G1 질문 형식 예:**
```
변환·검증 계획이 나왔습니다.

변환: solar_seg.pro → solar_seg.py (난이도 상, 시각화 제외)
probe: 12개 (01_input ~ 99_final), 오라클 예상 실행 ~N분, probe 용량 ~M GB
policy: orientation=memory, float32 rtol 1e-5,
        최종 seg_map은 labels IoU≥0.99 제안 — 근거: 임계 분기 경계픽셀의 반올림급 차이만 허용
데이터: 기존 데이터 재사용 (AIA 3파장 + HMI, 4개 FITS)

이대로 진행할까요? (probe 수/오차 기준/데이터를 조정할 수 있습니다)
```

**최종 지표·임계값은 human-in-the-loop로 확정한다**: 하네스(analyzer)가 코드 특성을 근거로
지표(iou/labels/allclose)와 수치를 **제안**하고, 사용자가 G1에서 조정·확정한다.
확정 전에 임의의 값으로 PASS를 선언하지 않는다.

## 루프 한도 (config/env.yaml)

| 루프 | 한도 | 초과 시 |
|---|---|---|
| 패리티 수정 (5a↔5c) | fix_loop_max = 5 | 남은 발산 목록 + 원인 가설 + 다음 선택지(세분화/waiver/수동) 보고 |
| probe 세분화 (재계측) | probe_refine_max = 2 | 동일 |
| 동일 probe 동일 발산 반복 | 3회 | 즉시 에스컬레이션 (수정이 헛돌고 있음) |
| 데이터 재확보 | 1회 | 루트 전환 제안 |
| 리뷰 REVISE | 2회 | 사용자 에스컬레이션 |

## 에러 핸들링

| Phase | 오류 | 대응 |
|---|---|---|
| 준비 | IDL 라이선스 도달 불가 | 상태 보고 + 재시도 문의 (파이프라인 보류) |
| 2 | 다운로드 실패 | 1회 재시도 → 루트 B 전환 |
| 3 | IDL 런타임 에러 | 로그 tail 보고, 원본 문제/계측 문제 구분 |
| 3 | 계측 무결성 실패 | probe 위치 재설계 (오라클 승인 보류) |
| 5 | Python traceback | divergence brief로 translator 수정 |
| 5 | 한도 초과 | 위 표 |
| 6 | pytest 미설치 | 사용자에게 설치 승인 요청 (`pip install pytest`), 거부 시 plain assert 러너로 대체 |

## conversion-note.md 기록 규칙 (07 동일 + 추가)

- 각 에이전트는 자기 Phase 섹션에 누적 기록 (수정 금지).
- **추가 기록 의무**: 오라클 캐시 키, 회차별 발산→수정 요약, waiver 승인 이력, 환경 스냅샷.

## 최종 산출물 안내 형식

```
변환·검증이 완료되었습니다.

parity: probe 12/12 PASS (입력 2세트), waiver 1건 (07_rot — 커널 차이, 승인됨)
루프: 3회 (전치 1건, off-by-one 1건, median /EVEN 1건 수정)

- 변환 코드: {작업경로}/converted/
- parity 인증: {작업경로}/reports/09_parity_certificate.md
- 회귀 테스트: pytest {작업경로}/tests/ -v
- 오라클 캐시: _cache/oracle/{key}/ (재검증 시 재사용)
```
