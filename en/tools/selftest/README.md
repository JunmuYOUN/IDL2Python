# tools/selftest — harness self-test (probe → compare round-trip)

A minimal test that confirms within 5 minutes that the core mechanism (chk_dump on both sides + compare_probes)
is alive after a harness deployment/environment change.

```bash
# From any work directory on the server (e.g., <harness>/_selftest_run) — re-runnable without any delete command
mkdir -p work/probes_idl && cd work
cp <harness>/tools/idl/chk_dump.pro <harness>/tools/chk_dump.py <harness>/tools/compare_probes.py .
cp <harness>/tools/selftest/smoke_idl.txt <harness>/tools/selftest/smoke_py.py .

# 1) Generate the IDL oracle probe (SSW not required — pure IDL)
CHK_DIR=$PWD/probes_idl /usr/local/bin/idl < smoke_idl.txt

# 2) Generate the Python twin (normal + 2 deliberate mismatches)
source ~/anaconda3/etc/profile.d/conda.sh && conda activate idl2py
python smoke_py.py

# 3) Compare — expected results:
python compare_probes.py --oracle probes_idl --py probes_py     --out report_ok   # ALL PASS, exit 0
python compare_probes.py --oracle probes_idl --py probes_py_bad --out report_bad  # DIVERGED, exit 1
#   report_bad: first divergence = b (scalar), m is an iou FAIL + shift_match {axis0:0, axis1:1} hint
```

Verification points:
- IDL `scope_varname` automatic variable naming / struct `.sav` saving / `/COMPRESS`
- readsav axis reversal → orientation=logical normalization (findgen(3,4) ↔ arange.reshape(4,3).T)
- automatic iou metric for byte 0/1 arrays, float32 scalar allclose
- first-divergence identification + automatic integer-shift diagnosis

Caution: the IDL probe id must use single quotes (`'01_test'`) — `"01..."` is parsed as octal.
