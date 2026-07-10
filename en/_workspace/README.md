# _workspace — workspace scaffold

This directory is a **structure template**. The actual work outputs are created under the `{work_path}` the user specifies,
in the structure below (created by the orchestrator).

```
{work_path}/
├── inbox/            # original .pro (read-only — never modify)
├── analysis/         # 00 inventory, 01 dependencies, 02 syntax, 03 conversion plan,
│                     # 04 probe plan, 05 data requirement spec
├── policy.yaml       # numeric/coordinate policy (copy of config/policy.template.yaml)
├── staging/          # instrumented IDL copy (_probed.pro) + batch (batch_oracle.pro)
├── data/             # validation inputs (staged) + manifest.jsonl  [set_01/, set_02/ ...]
├── converted/        # converted Python + requirements.txt + conversion_log.md
├── tests/            # oracle-pinned pytest (Phase 6)
├── probes/
│   ├── idl/          # oracle probe (*.sav) — immutable
│   └── py/run_NN/    # candidate probe (*.npz) — accumulated per loop iteration
├── reports/
│   ├── parity/run_NN/    # report.md/json + diff PNG
│   ├── parity/divergence_NN.md
│   ├── 00_review_report.md
│   └── 09_parity_certificate.md
└── logs/             # conversion-note.md, idl_run_*.log, py_run_*.log
```

Rule: never delete any output (iterations accumulate as run_NN).
The oracle cache is preserved separately under `_cache/oracle/{key}/` in the harness root.
