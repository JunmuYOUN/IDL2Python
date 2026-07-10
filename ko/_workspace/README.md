# _workspace — 작업 공간 스캐폴드

이 디렉토리는 **구조 템플릿**이다. 실제 작업 산출물은 사용자가 지정한 `{작업경로}`에
아래 구조로 생성된다 (orchestrator가 생성).

```
{작업경로}/
├── inbox/            # 원본 .pro (읽기 전용 — 절대 수정 금지)
├── analysis/         # 00 인벤토리, 01 의존성, 02 구문, 03 변환계획,
│                     # 04 probe 계획, 05 데이터 요구 명세
├── policy.yaml       # 수치·좌표 정책 (config/policy.template.yaml 복사)
├── staging/          # 계측된 IDL 사본(_probed.pro) + 배치(batch_oracle.pro)
├── data/             # 검증 입력 (staged) + manifest.jsonl  [set_01/, set_02/ ...]
├── converted/        # 변환 Python + requirements.txt + conversion_log.md
├── tests/            # oracle-pinned pytest (Phase 6)
├── probes/
│   ├── idl/          # 오라클 probe (*.sav) — 불변
│   └── py/run_NN/    # 후보 probe (*.npz) — 루프 회차별 누적
├── reports/
│   ├── parity/run_NN/    # report.md/json + diff PNG
│   ├── parity/divergence_NN.md
│   ├── 00_review_report.md
│   └── 09_parity_certificate.md
└── logs/             # conversion-note.md, idl_run_*.log, py_run_*.log
```

규칙: 어떤 산출물도 삭제하지 않는다 (회차는 run_NN으로 누적).
오라클 캐시는 하네스 루트의 `_cache/oracle/{key}/`에 별도 보존된다.
