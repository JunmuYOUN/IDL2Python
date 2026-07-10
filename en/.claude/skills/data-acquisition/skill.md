---
name: data-acquisition
description: >
  Input data acquisition protocol for parity verification.
  Defines the decision tree for user-provided (route A) / request from user (route B) / auto-download (route C),
  reuse of existing data on the server, fetch_data.py usage,
  manifest recording rules, and JSOC email rules.
  Keywords: data acquisition, download, VSO, Fido, JSOC, drms, FITS,
  test data, manifest, sha256, data request, staging
---

# Data-Acquisition — Verification data acquisition protocol

## 0. Principles

1. **Reuse first**: before downloading, first look for data already present on the server.
2. **Download only after approval** (gate G2): disclose the source, size, and storage location and obtain approval.
3. **Record all inputs in the manifest**: what you verified with must be reproducible for a parity certificate to hold.
4. **Original data is immutable**: staging by copy/link only. Do not delete.

## 1. Decision tree

```
Data requirement spec (analysis/05_data_requirements.md) finalized
    │
    ├─ User provided a path ────────────▶ route A: staging + manifest
    │
    ├─ Search on the server (find /userhome/... )
    │    Suitable file found ───────────▶ route A': reuse (notify the user)
    │
    ├─ Public archive is sufficient (VSO/Fido) ─▶ route C: fetch_data.py vso (after approval)
    │
    ├─ JSOC needed (specific series/level) ─▶ route C: fetch_data.py jsoc
    │                                         (email needed — ask the user)
    │
    └─ Auto-acquisition impossible/ambiguous ─▶ route B: present the required-spec table and
                                                ask the user to provide/select
```

## 2. Data requirement spec format (produced by idl-analyzer, for route B presentation)

```markdown
# Verification data requirement spec

| # | Item | Requirement | Rationale (original code) |
|---|---|---|---|
| 1 | Instrument/wavelength | SDO/AIA 171, 193, 211 Å | solar_seg.pro L39-41 file pattern |
| 2 | Magnetic field | SDO/HMI LOS magnetogram | L42 `*hmi*` |
| 3 | Level | level 1 or 1.5 (code determines it itself) | L68 |
| 4 | Time simultaneity | all 4 within ±a few minutes | algorithm assumption |
| 5 | Filename convention | `*00171*.f*`, `*hmi*.f*` | findfile pattern |
| 6 | Format | FITS full-disk 4096² | |

Recommended number of sets: 2 or more (different dates; if possible, a day with many CH + a day with few)
```

## 3. fetch_data.py usage (route C)

Run in the `idl2py` environment:

```bash
# VSO (no authentication needed)
python tools/fetch_data.py vso \
    --time "2017-01-01T00:00:00" --instrument aia --wavelength 193 \
    --out {work_path}/data

# JSOC (email required — use only the value received from the user)
python tools/fetch_data.py jsoc \
    --series "aia.lev1_euv_12s" --time "2017-01-01T00:00:00/1m" \
    --segments image --email {user-provided} --out {work_path}/data

# Direct URL
python tools/fetch_data.py url --url "https://..." --out {work_path}/data
```

- Every subcommand records one line into `{out}/manifest.jsonl`: timestamp, route, query, file, sha256, size.
- On failure, retry once, then switch to route B (report to the user).

## 4. JSOC email rules

- **Never hardcode it.** Do not store it in a config file either.
- Ask the user before first use: "JSOC download requires a registered email. Please tell me which email to use (it must be registered at export.jsoc.stanford.edu)."
- Reuse within a session is allowed, but record only "used user-provided email" in conversion-note.md (do not record the address itself).

## 5. staging rules

- Place files under `data/` by copy or symbolic link, matching the original code's **filename convention** (e.g., findfile patterns `*00171*`, `*hmi*`).
- If a filename change is needed, apply it only to the copy and record the original→staging mapping in the manifest.
- If there are multiple input sets, separate them as `data/set_01/`, `data/set_02/`….
- Right after staging, first confirm **whether both sides read the same input** via the `01_input` probe comparison (separating a data problem from a code problem).

## 6. The place of synthetic data

- Synthetic input is useful for per-function parity (subroutine harness) — having the IDL side read the same synthetic input preserves the oracle principle.
- However, **the final decision is made with real data**. Do not declare PASS on synthetic data alone (real data's NaN, exposure changes, and header diversity expose the pitfalls).

## 7. Disk usage reporting

- If the download/probe outputs are expected to exceed 5 GB, notify the user in advance.
- Cleanup (deletion) is the user's job — the harness does not delete; it may only propose a list of cleanup candidates.
