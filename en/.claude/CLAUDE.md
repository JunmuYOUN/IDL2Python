# IDL2Python-Parity — Execution-based IDL→Python conversion & verification harness

A pipeline that converts IDL (`.pro`) files to Python, **runs the original IDL and the converted Python in a real environment and compares numerical values checkpoint by checkpoint (parity check)**, and iterates a fix loop until the mismatches are gone.

Core principle: **it does not estimate expected values. The expected value is always the output (the oracle) obtained by actually running the original IDL.**

## Core design

| Item | Approach |
|---|---|
| Ground-truth basis | **Actual execution output of the original IDL (oracle)** |
| Verification unit | **All intermediate values at checkpoint (probe) granularity** |
| On mismatch | **Auto-localize the bug to the first divergence point → fix → re-run Python only** |
| Data | Real data via 3 routes (user-provided / requested / auto-download) + synthetic |
| Coordinate/numeric conventions | **Explicit declaration in policy.yaml + mechanically enforced by the comparator** |

## Agent team roster

| Agent | Role | Key functions |
|---|---|---|
| **idl-analyzer** | IDL code analysis | .pro parsing, dependencies, conversion plan, **probe (checkpoint) plan, data requirement spec** |
| **python-translator** | Python conversion | syntax conversion, library mapping, **twin probe insertion, dtype-faithful conversion, fixes from divergence reports** |
| **parity-runner** | Execution & comparison | environment check, data staging, **IDL oracle execution (instrumentation/integrity/cache), Python execution, compare_probes comparison, divergence report** |
| **test-engineer** | Regression testing | **oracle-pinned pytest generation**, edge cases, parallel execution |
| **conversion-reviewer** | Quality review | code review + **PASS/REVISE from parity report**, waiver adjudication |

## Pipeline

```
Phase 0  Source collection (local/Git/URL → inbox/)
    ▼
Phase 1  Analysis (idl-analyzer)
         conversion plan + probe plan + data requirement spec
    ▼
       ★ User approval ★  (plan/probe/data method)
    ▼
Phase 2  Verification data acquisition (parity-runner)
         Route A user-provided / Route B request from user / Route C auto-download
    ▼
Phase 3  IDL oracle execution (parity-runner)                                   ┐
         create instrumented copy → integrity check → probes/idl/*.sav → cache │ 3 & 4 can run in parallel
Phase 4  Python conversion (python-translator, incl. twin probe)               ┘
    ▼
Phase 5  ★ Parity loop ★
         ┌────────────────────────────────────────────┐
         │ 5a Run Python → probes/py/run_NN/*.npz     │
         │ 5b compare_probes.py → parity_report       │
         │ 5c ALL PASS → Phase 6                      │
         │    DIVERGE  → divergence report (first     │
         │               divergence point, signature  │
         │               hint) → translator fix →     │
         │               5a (no IDL re-run)           │
         └────────────────────────────────────────────┘
         Limits: fix_loop_max (default 5), probe refinement refine_max (default 2, requires IDL re-instrumentation)
    ▼
Phase 6  Pin regression tests (test-engineer — pytest using oracle probes as golden)
    ▼
Phase 7  Quality review (conversion-reviewer) → PASS / REVISE (→Phase 5)
    ▼
Phase 8  Final report — parity certificate (environment provenance + input manifest + metrics + waiver)
```

## Probe (checkpoint) protocol — summary

Details in the `parity-protocol` skill. Essentials only:

1. Use **an identically-shaped dump function on both sides**.
   - IDL: `chk_dump, '03_masks', mas, msk, mak` (`tools/idl/chk_dump.pro`)
   - Python: `chk_dump('03_masks', mas=mas, msk=msk, mak=mak)` (`tools/chk_dump.py`)
   - If the environment variable `CHK_DIR` is empty, both sides become a **no-op** → can be disabled without removing the instrumentation code
2. probe id is `NN_name` (execution order = lexicographic order). Record the location, variables, and rationale in the probe plan (`analysis/04_probe_plan.md`).
3. **Original is immutable**: probes are inserted only into the instrumented copy in `staging/`. The inbox/ original is never modified.
4. **Instrumentation integrity check**: the instrumented copy is accepted as the oracle only after confirming once that its final output is identical to an uninstrumented run (baseline).
5. **Insertion rules**: only at statement boundaries, only variables defined at that point, no side effects (no value changes / no control-flow changes).
6. Do not lay probes down densely from the start — begin coarse (~10 at block boundaries) and re-instrument at finer granularity only around the divergence region.

## Numeric & coordinate policy (policy.yaml)

Comparison criteria are not at the agent's discretion — they are **declared in `{work_path}/policy.yaml`** and mechanically enforced by `tools/compare_probes.py`.
Template: `config/policy.template.yaml`. Copy it at project start and finalize it in Phase 1 (subject to user approval).

- **orientation** (array-axis policy): `logical` (default) = Python preserves IDL's logical index `a[i,j]` → the comparator flips the axes of the readsav array to align them. `memory` = Python uses numpy's natural axes (the flipped shape) → compared as-is. This policy is grounded in the fact that **readsav returns the dimensions of an IDL array in reverse order**.
- **dtype fidelity**: during the parity stage, follow IDL's precision (`FLTARR`→`np.float32`). Promotion to float64 only as a separate refactor after parity passes.
- **Tolerances**: float32 default rtol=1e-5/atol=1e-6, masks use IoU, label maps use label-permutation-tolerant matching (IoU matrix + Hungarian).
- **Metrics and thresholds for the final output are not fixed values**: idl-analyzer **proposes** them based on code characteristics (threshold-branch sensitivity, label structure, etc.), and the user **finalizes** the numbers at G1 (human-in-the-loop). Intermediate probes use strict criteria by default.
- **NaN**: if both sides are NaN, they match (default).
- The catalog of pitfalls in pixel-coordinate conventions (FITS CRPIX 1-based, resample grid alignment, rounding mode, interpolation kernel differences, etc.) and the divergence-signature diagnostic table are in the `parity-protocol` skill. **Read it before converting, comparing, or reviewing.**

## Verification data acquisition — 3 routes

Details in the `data-acquisition` skill.

| Route | Method | Handling |
|---|---|---|
| **A. User-provided** | User supplies a path | staging into `data/` + manifest recorded |
| **B. Request** | The harness presents the required data spec (instrument/wavelength/time/level/format) as a table | User provides it or approves a download |
| **C. Auto-acquire** | `tools/fetch_data.py` (VSO/Fido need no auth, JSOC requires email) | User approval before download, manifest+sha256 recorded |

- Before downloading, **first search for data already on the server** (find). Reuse it if present.
- **Do not hardcode the JSOC email; ask the user before first use.**
- parity starts with one input set, but before the final PASS, verify with **two or more sets if possible** (different dates / edge cases).
- Synthetic data is useful for unit parity (individual functions), but the final decision is made with real data.

## Execution environment — deployment premise

This harness **assumes GitHub distribution**. It is not tied to a specific server; the user runs the oracle in their own environment with their own IDL license (full / **including the 90-day trial**).

- **`config/env.yaml` is the single source**. It is not committed (.gitignore) — host/account/site paths live only here. In a new environment, copy `config/env.template.yaml` and fill it in.
- **IDL**: the `idl.bin` executable + (only for solar-physics code) the `idl.ssw` SolarSoft root. If SSW is empty, the launcher runs pure IDL. Headless execution uses `tools/run_idl_headless.csh` + a batch `.pro` (the `IDL_STARTUP` approach, must terminate with `exit`, stdin `</dev/null`, timeout applied). Check license reachability before running the oracle (`license_check`).
- **Python**: a conda environment or python on PATH. Required packages: numpy/scipy/astropy/pyyaml (+ sunpy/aiapy/drms/skimage/matplotlib depending on the target code), pytest for Phase 6.
- **exec.mode**: `local` (the session runs on the IDL host, default) or `ssh` (wrapped as `ssh {host} "..."` from another host). Wherever the session runs, **all execution happens on the host that has IDL**.
- **No GPU needed** — both IDL and the comparator use CPU only.
- Deployment verification: after installing in a new environment, first run `tools/selftest/` (probe→compare round-trip, ~5 min) to confirm.

## Oracle cache

- IDL execution is slow. Oracle outputs are preserved in `_cache/oracle/{key}/`.
  `key = sha256(instrumented .pro) × sha256(input files) × probe plan hash` (12-char digest).
- After a Python fix in the parity loop, **do not re-run IDL** (reuse the cache). The only case requiring an IDL re-run is a change to the probe plan (refinement).
- probe storage uses compression (`SAVE, /COMPRESS`, `np.savez_compressed`). If there are many large arrays (e.g., 4096²), report disk usage to the user.
- The cache is **append-only**. Only the user does cleanup (deletion) — the harness does not run deletion commands.

## Absolute rules (incorporating the parent server rules)

- **No `rm` or other deletion commands on the server.** Do not run them in any form.
- **Do not use deletion-family calls such as `os.remove`, `shutil.rmtree`, `os.unlink`, `pathlib.Path.unlink` in any code/tool you create.** (tools/* are written to comply with this rule — they only overwrite)
- If deletion is needed, do not run it — just tell the user the command.
- Treat the original .pro and the oracle outputs as immutable.

## Approval gates · loop limits · waiver

| Gate | When | Content |
|---|---|---|
| G1 | After Phase 1 | conversion plan + probe plan + policy.yaml + data acquisition method |
| G2 | During Phase 2 | External download execution (size/source disclosed) |
| G3 | After Phase 7 | final result + parity certificate |

| Loop | Limit (env.yaml) | On exceed |
|---|---|---|
| Parity fix loop (5a-5c) | fix_loop_max = 5 | Report current state + remaining divergence list, escalate to user |
| probe refinement (IDL re-instrumentation) | probe_refine_max = 2 | Same |
| Data re-acquisition | 1 time | Propose an alternative route |

**waiver (permitted mismatch)**: **intentionally retained differences** — such as bugs on the original IDL side, library-kernel differences (e.g., IDL cubic convolution vs scipy spline), or astronomical-constant/ephemeris differences — must be recorded in `waivers:` of `policy.yaml` with (1) root-cause analysis, (2) relaxed criteria, and (3) user approval. If any divergence without a waiver remains, there is no PASS.

## Data handoff rules

| Agent | Output directory |
|---|---|
| idl-analyzer | `{work_path}/analysis/` |
| python-translator | `{work_path}/converted/` |
| parity-runner | `{work_path}/staging/`, `data/`, `probes/`, `reports/parity/`, `logs/run_*` |
| test-engineer | `{work_path}/tests/` |
| conversion-reviewer | `{work_path}/reports/` |
| Common | `{work_path}/logs/conversion-note.md` (cumulative log, do not modify) |

1. Each agent writes only to its own directory. Others' output is read-only.
2. Intermediate outputs are preserved, not deleted. Loop iterations are distinguished as `run_01/`, `run_02/`, ….
3. The original .pro is copied into `inbox/` and accessed read-only only.

## Workspace structure

```
{work_path}/
├── inbox/            original .pro (read-only)
├── analysis/         00 inventory, 01 dependencies, 02 syntax report, 03 conversion plan,
│                     04 probe plan, 05 data requirement spec
├── policy.yaml       numeric & coordinate policy (copied from config/policy.template.yaml)
├── staging/          instrumented IDL copy + batch .pro (separated from the original)
├── data/             verification input data + manifest.jsonl
├── converted/        converted Python (+ requirements.txt, conversion_log.md)
├── tests/            oracle-pinned pytest
├── probes/
│   ├── idl/          oracle probe (*.sav) — copied/linked from cache
│   └── py/run_NN/    candidate probe (*.npz), per loop iteration
├── reports/
│   ├── parity/       parity_report.md/json, divergence_*.md, diff PNG
│   ├── 00_review_report.md
│   └── 09_parity_certificate.md
└── logs/             conversion-note.md, idl_run_*.log, py_run_*.log
```

## Skill composition

| Skill | Role |
|---|---|
| **idl2python-orchestrator** | Pipeline coordination (phase order, gates, loops, parallelism) |
| **parity-protocol** | probe conventions, policy.yaml schema, coordinate & numeric pitfall catalog, divergence-signature diagnostic table, cache rules |
| **data-acquisition** | 3-route data acquisition decision tree, fetch_data.py usage, manifest rules |
| **idl-python-mapping** | IDL↔Python syntax mapping reference |
| **test-protocol** | pytest methodology (expected values replaced by oracle probes) |
| **web-source-collector** | Collect .pro from web URLs |

## Tools (tools/) — deterministic scripts

The parts enforced by scripts, not agent discretion:

| Tool | Role |
|---|---|
| `tools/idl/chk_dump.pro` | IDL probe dump (struct → .sav, no-op if CHK_DIR is unset) |
| `tools/idl/batch_template.pro` | Headless oracle batch template |
| `tools/run_idl_headless.csh` | SSW-IDL headless launcher |
| `tools/chk_dump.py` | Python probe dump (.npz) |
| `tools/compare_probes.py` | **Comparator** — applies policy, normalizes axes, computes metrics, first divergence, signature diagnosis, report/PNG |
| `tools/fetch_data.py` | VSO/JSOC/URL data acquisition + manifest |

## Required input policy

Secure before starting (ask if missing):

| Item | Content |
|---|---|
| IDL source | local/directory/Git/web URL |
| Conversion purpose | migration/integration/learning, etc. |
| Work path | where outputs are stored |
| **Verification data method** | Route A (provide) / B (request) / C (auto), or "search existing data on the server" |
| **Oracle execution scope** | whether the whole program once, or per specific subroutine |

## Languages used

- User-facing: Korean / code, config, variable names: English / reports: Korean

## Core principles

1. **The oracle is the ground truth**: do not estimate or hand-craft expected values. Always compare against the IDL execution output.
2. **Original is immutable**: do not modify or delete the inbox/ original or the oracle outputs.
3. **Policy is declared, enforcement is scripted**: declare tolerances and axis policy in policy.yaml, and compare_probes.py makes the judgment. The agent does not decide that things are "roughly similar".
4. **Localize divergence (probe-level comparison)**: do not compare only the final output. Find the first divergence checkpoint and fix only that block. Place probes right after non-trivial conversions and suspicious built-in functions so that one divergence narrows down to one operation (parity-protocol §1.4).
5. **Distrust IDL built-in function docs**: built-in functions may behave differently from their docs (BYTSCL, POLYFILLV, MEDIAN, etc.). Do not blindly trust documented formulas; determine the convention via actual oracle probe measurements or controlled experiments before converting (parity-protocol §4.0).
6. **Minimize IDL re-runs**: cache the oracle and re-run only Python in the fix loop.
7. **dtype fidelity → generalize later**: before parity passes, follow IDL's precision (mainly float32).
8. **waivers are explicit, approved, recorded**: do not leave unexplained mismatches.
9. **Record the reasoning process**: accumulate it in conversion-note.md. Preserve outputs per loop iteration.
10. **Observe approval gates**: G1 (plan), G2 (download), G3 (final).
11. **No deletion**: no rm-family on the server, no deletion APIs in code.

## Auto-memory policy (fully disabled)

This harness does not use the agent CLI's auto-memory feature. This is to prevent records from other sessions from interfering with unrelated work.

- **No reading**: do not use agent auto-memory (including `MEMORY.md`) as a basis for decisions. Ignore it even if injected into context.
- **No writing**: do not create or update auto-memory. For "remember this" requests, state that memory is disabled and propose a document inside the work directory as an alternative.
- Normal user files (README, notes, etc.) are referenced as usual.
