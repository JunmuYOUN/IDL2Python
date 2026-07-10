# IDL2Python — Execution-Verification (Parity) Based IDL→Python Conversion Harness

> **English summary** — An agent-CLI harness that converts
> legacy IDL (`.pro`) code to Python and **verifies the conversion by actually running both sides**:
> the original IDL produces *oracle* checkpoints, the converted Python produces *twin* checkpoints,
> and a policy-driven comparator localizes the first divergence and drives a fix loop until
> numerical parity. Built with solar & space-weather research code in mind (SunPy/Astropy ecosystem).

This is an automated pipeline that converts IDL (`.pro`) code to Python, then **actually runs both the
original IDL and the converted Python to compare numerical values checkpoint by checkpoint (parity check)**,
cycling through a fix loop until the discrepancies disappear.

Core principle: **do not estimate expected values.** The ground truth is always the output (oracle) obtained by
actually running the original IDL, and the determination that conversion is complete is made solely by numerical
agreement with that oracle.

## How It Verifies

At semantically identical points in both codebases, plant a dump call with the same name (twin probe):

```idl
; IDL (instrumented copy)                  # Python (converted code)
chk_dump, '05_masks', mas, msk             chk_dump('05_masks', mas=mas, msk=msk)
```

- If the environment variable `CHK_DIR` is absent, both sides are no-ops — harmless even if left in production code
- IDL → `probe_05_masks.sav`, Python → `probe_05_masks.npz`
- `tools/compare_probes.py` judges according to `policy.yaml` (array axis orientation · tolerance · IoU · label matching) and
  reports the **first divergence point** and automatic diagnostics (suspected transpose/pixel shift/scale)
- In the fix loop, **only Python is re-run** — the IDL oracle is cached

```
Source collection → Analysis (+probe plan +policy draft) → [Approval G1]
→ Validation data acquisition → IDL oracle run (instrumentation · integrity · cache) ∥ Python conversion (twin probe)
→ Parity loop [run → compare → divergence localization → fix, default max 5 times]
→ Regression tests (pytest) → Quality review → parity certificate
```

## Requirements

| Requirement | Notes |
|---|---|
| **IDL 8.x** | For oracle execution. Both full and 90-day trial licenses work. If the target code uses SolarSoft, SSW installation is required (pure IDL code does not need SSW) |
| **Python 3.10+** | See the environment setup below |
| **Agent CLI** | Any coding-agent CLI — CLIs that load `.claude/` natively (e.g., Claude Code) work as-is; any other CLI (e.g., OpenAI Codex CLI, or anything that reads `AGENTS.md`) enters through `AGENTS.md`. Same pipeline either way |
| csh | For the headless IDL launcher (Linux standard) |
| ssh (optional) | When IDL is on a remote server |
| GPU | **Not needed** — all CPU |

## Installation

### 1. Clone

```bash
git clone https://github.com/JunmuYOUN/IDL2Python.git
cd IDL2Python
```

### 2. Python Environment (conda recommended)

```bash
conda create -n idl2py python=3.10 -y
conda activate idl2py

# Harness tool required packages (probe comparator · data acquisition · regression tests)
pip install numpy scipy astropy pyyaml matplotlib pytest

# For solar & space-weather research — SSW routine mapping targets + observation data acquisition
pip install sunpy aiapy drms scikit-image
```

| Package | Role in the harness |
|---|---|
| numpy / scipy | Numerical comparison, `scipy.io.readsav` (reading IDL .sav), Hungarian label matching |
| astropy | FITS I/O, WCS, time systems — the counterpart to the IDL `FITS_READ`/`anytim` family |
| sunpy | `sunpy.map`, ephemeris (`sunpy.coordinates.sun`), VSO/Fido data download — the main mapping target for SSW routines |
| aiapy / drms | SDO/AIA calibration (`aia_prep` counterpart), JSOC queries |
| pyyaml | Parsing `policy.yaml` (comparison policy) |
| matplotlib | Divergence diff PNG generation |
| scikit-image | Mapping target for IDL image-processing routines such as morphological operations |
| pytest | Oracle-pinned regression tests |

### 3. Create Environment Profile

```bash
cp config/env.template.yaml config/env.yaml   # env.yaml is gitignored (host/account go here only)
```

Items to fill in `config/env.yaml`:

| Key | Description |
|---|---|
| `exec.mode` | `local` (session runs on the IDL host) / `ssh` (drive a remote IDL host via ssh) |
| `idl.bin`, `idl.idl_dir` | IDL executable/installation path |
| `idl.ssw` | SolarSoft root (only when the target code uses SSW; if empty, runs as pure IDL) |
| `python.conda_sh`, `python.conda_env` | conda initialization script and the environment name created above (`idl2py`) |
| `paths.harness_root` | Absolute path of this repository checkout |
| `limits.*` | Fix-loop limits, etc. (defaults are usable) |

### 4. Self-test (~5 min, recommended)

Verify that the probe generation → comparison round-trip works in your environment. Following the procedure in `tools/selftest/README.md`:

```bash
# Summary: generate probe .sav with IDL → generate Python twin .npz → run the comparator
# Expected result: a correct twin gives ALL PASS (exit 0), an intentional mismatch gives DIVERGED (exit 1) + shift diagnostic
```

## Usage

This repository is an **agent-CLI harness**. The pipeline (analysis → oracle → conversion → parity loop → certification) is
carried out by the agent team defined in `.claude/`, and the user intervenes at approval gates.
The pipeline definition is plain markdown, so it is not tied to any particular CLI.

1. Open a coding-agent CLI session at the repository root:
   ```bash
   cd IDL2Python
   # Start the agent CLI session
   ```
   - CLIs that auto-load `.claude/` (e.g., Claude Code): just start it.
   - Any other CLI (e.g., OpenAI Codex CLI): `AGENTS.md` is the entry point — if your tool
     does not read it automatically, make your first message "Read AGENTS.md and follow it."
2. Enter a conversion request (template):
   ```
   Convert [target.pro] to Python and verify it against the IDL execution results.

   File: /path/to/your_routine.pro        (local path · Git URL · web URL all supported)
   Purpose: SunPy pipeline integration
   Work path: /path/to/work/your_routine_parity
   Validation data: [provide directly /path/to/fits | request required spec | auto-download (VSO/JSOC)]
   ```
   Actual usage example:
   ```
   Convert chimera.pro to Python and verify it against the IDL execution results.

   File: /path/to/CHIMERA/repo/chimera.pro
   Purpose: Python integration of the coronal hole detection pipeline
   Work path: /path/to/work/chimera_parity
   Validation data: search existing data on the server (or auto-download)
   ```
3. During the process, you are asked to confirm three times:
   - **G1** — conversion plan + checkpoint (probe) plan + comparison policy (`policy.yaml`) draft.
     The harness **proposes** the acceptance criteria for the final output (IoU, etc.), and the user **finalizes** the numbers.
   - **G2** — just before external data download (source/size notice)
   - **G3** — final result
4. Deliverables upon completion:
   - `{work_path}/converted/` — converted Python (+ `requirements.txt`, conversion log)
   - `{work_path}/reports/09_parity_certificate.md` — full record of environment · input · policy · determination
   - `{work_path}/tests/` — oracle-pinned regression tests (`pytest tests/ -v`)
   - `{work_path}/reports/parity/` — per-probe comparison reports + divergence diff PNGs

### Three Acquisition Routes for Validation Data

| Route | Method |
|---|---|
| Provide directly | Tell it the path of a FITS file you have |
| Request spec | The harness presents the required data spec (instrument/wavelength/time/level) as a table and the user prepares it |
| Auto-download | VSO (no authentication needed) or JSOC (registration email required — asked at run time) — all inputs are recorded with manifest+sha256 |

### IDL source examples (SolarSoft)

The harness can pull `.pro` files directly from an HTML/FTP directory index (see the `web-source-collector` skill). Canonical SolarSoft trees to browse for conversion targets:

- Instrument & analysis packages: <https://sohoftp.nascom.nasa.gov/solarsoft/packages/>
- General SSW utilities (`gen`): <https://sohoftp.nascom.nasa.gov/solarsoft/gen/>

## Folder Structure

```
IDL2Python/
├── README.md / INTRO.md / harness.json
├── AGENTS.md                     # entry point for agent CLIs that don't auto-load .claude/
├── .claude/
│   ├── CLAUDE.md                 # pipeline operations contract
│   ├── agents/                   # idl-analyzer, python-translator, parity-runner,
│   │                             # test-engineer, conversion-reviewer
│   └── skills/                   # orchestrator, parity protocol, data acquisition,
│                                 # IDL↔Python mapping reference, etc.
├── config/
│   ├── env.template.yaml         # → copy to config/env.yaml to use (gitignored)
│   └── policy.template.yaml      # numerical/coordinate comparison policy template
├── tools/
│   ├── idl/chk_dump.pro          # IDL probe dump (.sav)
│   ├── idl/batch_template.pro    # headless oracle batch template
│   ├── run_idl_headless.csh      # IDL/SSW-IDL launcher (auto-branches if no SSW)
│   ├── chk_dump.py               # Python probe dump (.npz, twin)
│   ├── compare_probes.py         # comparator — policy enforcement · first divergence · auto diagnostics · report
│   ├── fetch_data.py             # VSO/JSOC/URL data acquisition + manifest
│   └── selftest/                 # self-test for installation verification
└── _workspace/                   # workspace structure guide (actual work is created at the specified path)
```

## Parts Specialized for Solar & Space-Weather Code

- **Built-in SSW → SunPy/Astropy mapping reference** (`anytim`→`parse_time`, `read_sdo`→`sunpy.map.Map`,
  `aia_prep`→`aiapy.calibrate`, etc.) — `.claude/skills/idl-python-mapping/`
- **Pixel-coordinate & numerical pitfall catalog**: FITS `CRPIX` 1-based, resample grid 0.5px alignment,
  `ROUND` (half-away) vs `np.round` (half-even), `MEDIAN /EVEN`, `SMOOTH` boundaries, cubic kernel differences,
  `STDDEV` ddof, IDL 16-bit default integer, etc. — `.claude/skills/parity-protocol/`
- **Ephemeris/random-number handling**: arcsec-level differences between SSW ephemeris such as `pb0r` and sunpy values, and
  the `RANDOMU` seed-irreproducibility problem, handled via oracle value injection
- **Automatic observation data acquisition**: `sunpy.net.Fido` (VSO), `drms` (JSOC) based download + reproducibility manifest

## Safety Rules (summary)

- The original `.pro` is never modified (instrumentation goes only into the staging copy)
- Oracle outputs and cache are append-only — the harness never deletes any file
- External downloads, package installation, and the final determination criteria all proceed only after user approval
- Personal information such as the JSOC email is never hardcoded (`config/env.yaml` is gitignored)

## FAQ

**Q. Can I use it without IDL?**
No. The very reason this harness exists is "comparison against the outputs of actually running the original IDL," so an
IDL execution environment (trial license works) to create the oracle is absolutely required.

**Q. What if IDL is only on a remote server?**
If you set `exec.mode: ssh` + `exec.host` in `config/env.yaml`, all IDL/Python execution is performed on that host
(ssh key authentication recommended).

**Q. Can I just convert and skip verification?**
It's possible but not recommended. If conversion without verification is the goal, the syntax-conversion pipeline that is
this harness's predecessor is sufficient on its own — this harness's determination always presupposes execution comparison.

**Q. Who sets the tolerance?**
Intermediate checkpoints start with strict defaults (float32 rtol 1e-5, mask IoU 0.999), and the criteria for the final
output are proposed by the harness based on the code's characteristics, then **finalized by the user at G1**. Unavoidable
discrepancies such as library kernel differences are permitted only via a waiver equipped with cause · mitigated criteria · approval.
