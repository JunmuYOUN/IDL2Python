---
name: idl2python-orchestrator
description: >
  Overall pipeline orchestrator that converts IDL .pro files to Python and completes
  execution-based numerical comparison (parity).
  Must use this skill whenever the request is: convert this IDL, convert a .pro file,
  IDL to Python, convert IDL code, .pro file to py, IDL migration, convert SSW code,
  convert SolarSoft, IDL verification, parity, execution verification, oracle comparison,
  conversion check.
---

# IDL2Python-Orchestrator — Orchestration of the Conversion + Execution-Verification Pipeline

## Overview

When the user presents an IDL .pro, this coordinates the whole process: analysis → data acquisition → **IDL oracle execution** → conversion → **parity loop (run · compare · fix)** → regression pinning → review.
Unlike the 07 harness, completion is judged not by "tests pass" but by **"passing comparison against the original IDL's execution output (parity PASS)"**.

## Required-Input Check

| # | Item | Question if missing |
|---|---|---|
| 1 | IDL source | "What is the path/URL of the .pro to convert? (local, Git, or web all work)" |
| 2 | Conversion purpose | "What is the purpose of the conversion? (migration/integration, etc.)" |
| 3 | Working path | "What working path should the outputs be saved to?" |
| 4 | **Validation-data method** | "How should we obtain the validation inputs? ① provide them directly ② I compile the required spec and request it ③ automatic download (after approval) ④ search for existing data on the server" |
| 5 | **Oracle scope** | "Scope of the IDL execution comparison: based on one run of the whole program, or per specific function/subroutine?" |

Automatic source-type detection (local/Git/web) and Phase 0 collection are the same as 07 (`web-source-collector`).

## Pipeline

```
Phase 0  Source collection → inbox/
    ▼
Phase 1  Analysis (idl-analyzer)
         ├ 00~03: inventory/dependencies/syntax/conversion plan (same as 07)
         ├ 04_probe_plan.md: checkpoint plan (location · variable · rationale, 8-15 items)
         ├ 05_data_requirements.md: validation-data requirement spec
         └ policy.yaml draft (based on config/policy.template.yaml)
    ▼
★ G1 user approval ★  conversion plan + probe plan + policy + data method
    ▼
Phase 2  Data acquisition (parity-runner, data-acquisition skill)
         reuse within server → routes A/B/C. Download needs ★G2 approval★
    ▼
Phase 3  IDL oracle (parity-runner)              ┐ 3·4 can run in parallel
         instrument→integrity→run→cache          │ (oracle is unrelated to conversion)
Phase 4  Python conversion (python-translator)   ┘
         includes twin probe, dtype-faithful
    ▼
Phase 5  Parity loop
         ┌────────────────────────────────────────────────────────┐
         │ 5a parity-runner: run Python (probes/py/run_NN)        │
         │ 5b parity-runner: compare_probes → report              │
         │ 5c branch:                                             │
         │    ALL PASS ────────────────────▶ Phase 6              │
         │    DIVERGE → divergence brief →                        │
         │        python-translator fix → 5a                      │
         │        (fix_loop_max=5, no IDL rerun)                  │
         │    can't localize the interval → refine probes         │
         │        (analyzer updates plan → Phase 3 re-instrument, │
         │         refine_max=2)                                  │
         │    waiver candidate (library kernel diff, etc.)        │
         │        → request user approval → record in policy.yaml │
         └────────────────────────────────────────────────────────┘
    ▼
Phase 6  Regression pinning (test-engineer)
         generate & run a pytest suite using the oracle probes as golden
    ▼
Phase 7  Quality review (conversion-reviewer)
         parity report + waiver + code review → PASS / REVISE(→Phase 5)
    ▼
★ G3 final approval ★
Phase 8  Final report — reports/09_parity_certificate.md
```

**Multi-file (batch) mode**: convert dependency groups in parallel just as in 07, but set the oracle **per entry point of the call graph** (rather than running IDL separately for each file, embed the probes of multiple files together in a single run of the entry point).

## Approval Gates

| Gate | When | What is presented |
|---|---|---|
| G1 | After Phase 1 | conversion plan, probe plan (count · location), policy draft (orientation/tolerance), data-acquisition method, estimated IDL run time · disk |
| G2 | Just before download | source, query, estimated size, storage location |
| G3 | After Phase 7 | parity certificate summary, waiver list, usage |

**Example G1 question format:**
```
The conversion & verification plan is ready.

Conversion: solar_seg.pro → solar_seg.py (high difficulty, visualization excluded)
probe: 12 items (01_input ~ 99_final), estimated oracle run ~N min, probe size ~M GB
policy: orientation=memory, float32 rtol 1e-5,
        proposing labels IoU≥0.99 for the final seg_map — rationale: allow only rounding-level differences at threshold-branch boundary pixels
data: reuse existing data (AIA 3 wavelengths + HMI, 4 FITS)

Shall we proceed as-is? (you can adjust the probe count / tolerance criteria / data)
```

**Final metrics & thresholds are finalized human-in-the-loop**: the harness (analyzer) **proposes**
the metrics (iou/labels/allclose) and values based on code characteristics, and the user adjusts and finalizes them at G1.
Do not declare PASS with arbitrary values before finalization.

## Loop Limits (config/env.yaml)

| Loop | Limit | On exceeding |
|---|---|---|
| Parity fix (5a↔5c) | fix_loop_max = 5 | report the remaining divergence list + cause hypotheses + next options (refine/waiver/manual) |
| Probe refinement (re-instrument) | probe_refine_max = 2 | same |
| Same probe, same divergence repeats | 3 times | escalate immediately (fixes are spinning in place) |
| Data re-acquisition | 1 time | propose a route switch |
| Review REVISE | 2 times | escalate to user |

## Error Handling

| Phase | Error | Response |
|---|---|---|
| Prep | IDL license unreachable | report status + ask about retry (pipeline on hold) |
| 2 | Download failure | retry once → switch to route B |
| 3 | IDL runtime error | report log tail, distinguish original-code vs instrumentation problem |
| 3 | Instrumentation integrity failure | redesign probe locations (oracle approval on hold) |
| 5 | Python traceback | fix translator via divergence brief |
| 5 | Limit exceeded | the table above |
| 6 | pytest not installed | ask the user to approve installation (`pip install pytest`); if refused, substitute a plain assert runner |

## conversion-note.md Logging Rules (same as 07 + additions)

- Each agent appends to its own Phase section (no editing).
- **Additional logging obligation**: oracle cache key, per-round divergence→fix summary, waiver approval history, environment snapshot.

## Final Deliverable Notice Format

```
Conversion & verification complete.

parity: probe 12/12 PASS (2 input sets), waiver 1 (07_rot — kernel diff, approved)
loops: 3 (1 transpose, 1 off-by-one, 1 median /EVEN fix)

- Converted code: {work_path}/converted/
- parity certificate: {work_path}/reports/09_parity_certificate.md
- Regression tests: pytest {work_path}/tests/ -v
- Oracle cache: _cache/oracle/{key}/ (reused on re-verification)
```
