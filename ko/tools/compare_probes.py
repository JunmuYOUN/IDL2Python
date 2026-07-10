#!/usr/bin/env python
"""
compare_probes.py — parity comparator: IDL oracle probes (.sav) vs converted
Python probes (.npz).

- Enforces the project policy (policy.yaml): array orientation, tolerances,
  per-checkpoint / per-variable metric overrides, waivers.
- Emits per-probe/per-variable verdicts, the FIRST divergence, failure stats,
  and automatic signature diagnostics (transpose / integer shift / linear fit).
- Writes report.json + report.md (+ diff PNGs for failing 2D arrays w/ --png).
- Append/overwrite only: never deletes anything.

Exit codes: 0 = all pass, 1 = divergence(s) present, 2 = execution error.

Usage:
  python compare_probes.py --oracle DIR --py DIR --policy policy.yaml \
      --out reports/parity/run_01 [--png] [--diag-max-size 33554432]
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np

try:
    import yaml
except ImportError:  # minimal fallback: policy must then be JSON
    yaml = None

from scipy.io import readsav

DEFAULT_POLICY = {
    "orientation": "logical",
    "nan_equal": True,
    "dtype_strict": False,
    "defaults": {
        "float": {"metric": "allclose", "rtol": 1e-5, "atol": 1e-6},
        "double": {"metric": "allclose", "rtol": 1e-10, "atol": 1e-12},
        "int": {"metric": "exact"},
        "byte_mask": {"metric": "iou", "min_iou": 0.999},
    },
    "checkpoints": {},
    "waivers": [],
}


# ---------------------------------------------------------------- loading

def load_policy(path):
    policy = json.loads(json.dumps(DEFAULT_POLICY))  # deep copy
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        user = yaml.safe_load(text) if yaml else json.loads(text)
        if user:
            for k, v in user.items():
                if k == "defaults" and isinstance(v, dict):
                    policy["defaults"].update(v)
                else:
                    policy[k] = v
    return policy


def _from_idl(v):
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


def load_oracle_probe(path):
    """Read one probe .sav -> {lowername: value}. Expects struct CHK."""
    sav = readsav(path, verbose=False)
    out = {}
    if "chk" in sav:
        rec = np.atleast_1d(sav["chk"])[0]
        for name in rec.dtype.names:
            if name.lower() in ("probe_id",):
                continue
            out[name.lower()] = _from_idl(rec[name])
    else:  # fallback: plain variables in the sav file
        for k, v in sav.items():
            out[k.lower()] = _from_idl(v)
    return out


def load_py_probe(path):
    out = {}
    with np.load(path, allow_pickle=False) as z:
        for k in z.files:
            out[k.lower()] = z[k]
    return out


def probe_id_of(path):
    m = re.match(r"probe_(.+)\.(sav|npz)$", os.path.basename(path))
    return m.group(1) if m else os.path.basename(path)


# ------------------------------------------------------------ orientation

def orient_oracle(arr, orientation):
    """readsav reverses IDL dims; 'logical' policy restores IDL index order."""
    a = np.asarray(arr)
    if orientation == "logical" and a.ndim >= 2:
        return np.transpose(a)  # reverse ALL axes
    return a


# ------------------------------------------------------------ spec lookup

def resolve_spec(policy, pid, var, oracle_val):
    cps = policy.get("checkpoints") or {}
    cp = cps.get(pid) or {}
    spec = dict(cp.get(var) or cp.get("*") or {})

    waived = False
    reason = ""
    for w in policy.get("waivers") or []:
        if str(w.get("checkpoint")) == pid and w.get("var") in (var, "*"):
            spec = dict(w.get("relaxed") or spec)
            waived = True
            reason = w.get("reason", "")

    if not spec.get("metric"):
        a = np.asarray(oracle_val)
        d = policy["defaults"]
        if a.dtype.kind == "f":
            spec = dict(d["double"] if a.dtype.itemsize >= 8 else d["float"], **spec)
        elif a.dtype.kind in "ui":
            vals = np.unique(a) if a.size < 64_000_000 else np.unique(a.ravel()[:1_000_000])
            if a.ndim >= 2 and vals.size <= 2 and set(vals.tolist()) <= {0, 1}:
                spec = dict(d["byte_mask"], **spec)
            else:
                spec = dict(d["int"], **spec)
        elif a.dtype.kind in "SU" or isinstance(oracle_val, str):
            spec = dict({"metric": "exact"}, **spec)
        else:
            spec = dict({"metric": "exact"}, **spec)
    spec["waived"] = waived
    if reason:
        spec["waiver_reason"] = reason
    return spec


# ------------------------------------------------------------- metrics

def _iou(a, b):
    inter = np.count_nonzero(a & b)
    union = np.count_nonzero(a | b)
    return 1.0 if union == 0 else inter / union


def label_match(o, p):
    """Permutation-tolerant label-map comparison via confusion matrix + Hungarian."""
    o = np.asarray(o).astype(np.int64).ravel()
    p = np.asarray(p).astype(np.int64).ravel()
    no, np_ = int(o.max()), int(p.max())
    if no == 0 and np_ == 0:
        return {"mean_iou": 1.0, "n_oracle": 0, "n_py": 0, "pairs": []}
    conf = np.bincount(o * (np_ + 1) + p, minlength=(no + 1) * (np_ + 1)).reshape(no + 1, np_ + 1)
    row = conf.sum(axis=1)
    col = conf.sum(axis=0)
    iou = np.zeros((no, np_), dtype=np.float64)
    for i in range(1, no + 1):
        for j in range(1, np_ + 1):
            inter = conf[i, j]
            if inter:
                iou[i - 1, j - 1] = inter / float(row[i] + col[j] - inter)
    from scipy.optimize import linear_sum_assignment
    ri, ci = linear_sum_assignment(-iou)
    pairs = [(int(ri[k]) + 1, int(ci[k]) + 1, float(iou[ri[k], ci[k]])) for k in range(len(ri))]
    pairs = [p_ for p_ in pairs if p_[2] > 0]
    matched = [p_[2] for p_ in pairs]
    n_match = min(no, np_)
    mean_iou = (sum(matched) / n_match) if n_match else 0.0
    return {"mean_iou": mean_iou, "n_oracle": no, "n_py": np_, "pairs": pairs}


def fail_stats(o, p, rtol, atol, nan_equal):
    of = np.asarray(o, dtype=np.float64)
    pf = np.asarray(p, dtype=np.float64)
    diff = pf - of
    both_nan = np.isnan(of) & np.isnan(pf)
    bad = ~np.isclose(pf, of, rtol=rtol, atol=atol, equal_nan=nan_equal)
    stats = {
        "max_abs_err": float(np.nanmax(np.abs(np.where(both_nan, 0, diff)))) if diff.size else 0.0,
        "mismatch_frac": float(np.count_nonzero(bad)) / max(bad.size, 1),
        "n_mismatch": int(np.count_nonzero(bad)),
        "oracle_nan": int(np.count_nonzero(np.isnan(of))),
        "py_nan": int(np.count_nonzero(np.isnan(pf))),
    }
    denom = np.abs(of)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(diff) / np.where(denom > 0, denom, np.nan)
    stats["max_rel_err"] = float(np.nanmax(rel)) if np.isfinite(rel).any() else None
    if bad.any() and of.ndim:
        try:
            worst = int(np.nanargmax(np.abs(np.where(bad, diff, 0))))
            stats["argmax_loc"] = [int(x) for x in np.unravel_index(worst, of.shape)]
        except ValueError:
            pass  # all-NaN slice etc.
    return stats


# ---------------------------------------------------------- diagnostics

def diagnose(o, p, rtol, atol, nan_equal, max_size):
    """Cheap signature checks on failing arrays (see parity-protocol skill §5)."""
    hints = {}
    of = np.asarray(o)
    pf = np.asarray(p)
    if of.size == 0 or of.size > max_size:
        return hints

    def mism(a, b):
        return float(np.count_nonzero(~np.isclose(
            np.asarray(b, dtype=np.float64), np.asarray(a, dtype=np.float64),
            rtol=rtol, atol=atol, equal_nan=nan_equal))) / a.size

    # transpose signature
    if of.ndim == 2 and of.T.shape == pf.shape:
        if mism(of.T, pf) < 0.001:
            hints["transpose_match"] = True

    # integer shift signature (axis0/axis1 follow the compared orientation)
    if of.ndim == 2 and of.shape == pf.shape:
        base = mism(of, pf)
        if base > 0:
            best = (0, 0, base)
            for d0 in range(-3, 4):
                for d1 in range(-3, 4):
                    if d0 == 0 and d1 == 0:
                        continue
                    m = mism(of, np.roll(pf, (-d0, -d1), axis=(0, 1)))
                    if m < best[2]:
                        best = (d0, d1, m)
            if best[2] < base * 0.2:
                hints["shift_match"] = {"axis0": best[0], "axis1": best[1],
                                        "mismatch_after": best[2], "mismatch_before": base}

    # linear scale/offset signature
    if of.dtype.kind in "fiu" and pf.dtype.kind in "fiu" and of.shape == pf.shape:
        x = np.asarray(of, dtype=np.float64).ravel()
        y = np.asarray(pf, dtype=np.float64).ravel()
        good = np.isfinite(x) & np.isfinite(y)
        if good.sum() > 16:
            xs, ys = x[good], y[good]
            if xs.size > 200_000:
                idx = np.linspace(0, xs.size - 1, 200_000).astype(np.int64)
                xs, ys = xs[idx], ys[idx]
            if float(np.std(xs)) > 0:
                a, b = np.polyfit(xs, ys, 1)
                resid = float(np.std(ys - (a * xs + b)))
                scale = float(np.std(ys)) if float(np.std(ys)) > 0 else 1.0
                if resid / scale < 0.01 and (abs(a - 1) > 1e-3 or abs(b) > atol * 10):
                    hints["linear_fit"] = {"a": float(a), "b": float(b), "resid_frac": resid / scale}
    return hints


# ------------------------------------------------------------- compare

def compare_var(pid, var, oracle_val, py_val, spec, policy, diag_max):
    row = {"probe": pid, "var": var, "metric": spec.get("metric"),
           "waived": bool(spec.get("waived"))}
    if spec.get("waiver_reason"):
        row["waiver_reason"] = spec["waiver_reason"]
    nan_equal = bool(policy.get("nan_equal", True))

    o = oracle_val
    p = py_val
    if isinstance(o, str) or isinstance(p, str):
        row["verdict"] = "PASS" if str(o).strip() == str(p).strip() else "FAIL"
        row["detail"] = "string compare"
        return row

    o = orient_oracle(o, policy.get("orientation", "logical"))
    p = np.asarray(p)
    row["oracle_shape"] = list(np.shape(o))
    row["py_shape"] = list(np.shape(p))
    row["oracle_dtype"] = str(np.asarray(o).dtype)
    row["py_dtype"] = str(p.dtype)

    if np.shape(o) != np.shape(p):
        row["verdict"] = "FAIL"
        row["detail"] = "SHAPE_MISMATCH"
        if np.asarray(o).ndim >= 2 and tuple(np.shape(o))[::-1] == tuple(np.shape(p)):
            row["hints"] = {"shape_is_reversed": True,
                            "note": "orientation policy violation? see parity-protocol §3"}
        return row

    if policy.get("dtype_strict") and str(np.asarray(o).dtype) != str(p.dtype):
        row["verdict"] = "FAIL"
        row["detail"] = "DTYPE_MISMATCH (dtype_strict=true)"
        return row

    metric = spec.get("metric", "allclose")
    rtol = float(spec.get("rtol", 1e-5))
    atol = float(spec.get("atol", 1e-6))

    if metric == "exact":
        ok = np.array_equal(np.asarray(o), p)
        if not ok:
            row["stats"] = fail_stats(o, p, 0.0, 0.0, nan_equal)
    elif metric == "allclose":
        ok = bool(np.allclose(np.asarray(p, dtype=np.float64),
                              np.asarray(o, dtype=np.float64),
                              rtol=rtol, atol=atol, equal_nan=nan_equal))
        if not ok:
            row["stats"] = fail_stats(o, p, rtol, atol, nan_equal)
    elif metric == "iou":
        ob = np.asarray(o) != 0
        pb = p != 0
        iou = _iou(ob, pb)
        row["iou"] = iou
        ok = iou >= float(spec.get("min_iou", 0.999))
        if not ok:
            row["stats"] = {"n_only_oracle": int(np.count_nonzero(ob & ~pb)),
                            "n_only_py": int(np.count_nonzero(pb & ~ob)),
                            "n_oracle": int(np.count_nonzero(ob)),
                            "n_py": int(np.count_nonzero(pb))}
    elif metric == "labels":
        lm = label_match(o, p)
        row["labels"] = lm
        ok = (lm["mean_iou"] >= float(spec.get("min_iou", 0.99))
              and lm["n_oracle"] == lm["n_py"])
    else:
        row["verdict"] = "FAIL"
        row["detail"] = "unknown metric: %s" % metric
        return row

    if not ok and np.asarray(o).ndim >= 1 and np.asarray(o).dtype.kind in "fiub":
        h = diagnose(np.asarray(o), p, rtol, atol, nan_equal, diag_max)
        if h:
            row["hints"] = h

    if ok:
        row["verdict"] = "WAIVED_PASS" if spec.get("waived") else "PASS"
    else:
        row["verdict"] = "FAIL"
    return row


def render_png(outdir, pid, var, oracle_val, py_val, policy):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    o = np.asarray(orient_oracle(oracle_val, policy.get("orientation", "logical")), dtype=np.float64)
    p = np.asarray(py_val, dtype=np.float64)
    if o.ndim != 2 or o.shape != p.shape:
        return None
    d = p - o
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, img, title, cmap in ((axes[0], o, "oracle (IDL)", "viridis"),
                                 (axes[1], p, "python", "viridis"),
                                 (axes[2], d, "py - oracle", "RdBu_r")):
        vmax = np.nanpercentile(np.abs(d), 99.9) if title.startswith("py -") else None
        im = ax.imshow(img, origin="lower", cmap=cmap,
                       vmin=(-vmax if vmax else None), vmax=vmax)
        ax.set_title("%s %s/%s" % (title, pid, var))
        fig.colorbar(im, ax=ax, shrink=0.8)
    fname = os.path.join(outdir, "diff_%s_%s.png" % (pid, var))
    fig.tight_layout()
    fig.savefig(fname, dpi=110)
    plt.close(fig)
    return fname


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--oracle", required=True, help="dir with probe_*.sav")
    ap.add_argument("--py", required=True, help="dir with probe_*.npz")
    ap.add_argument("--policy", default="", help="policy.yaml path")
    ap.add_argument("--out", required=True, help="report output dir")
    ap.add_argument("--png", action="store_true", help="write diff PNGs for failing 2D arrays")
    ap.add_argument("--diag-max-size", type=int, default=33_554_432,
                    help="max elements for signature diagnostics")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    policy = load_policy(args.policy)

    sav = {probe_id_of(f): f for f in glob.glob(os.path.join(args.oracle, "probe_*.sav"))}
    npz = {probe_id_of(f): f for f in glob.glob(os.path.join(args.py, "probe_*.npz"))}
    pids = sorted(set(sav) | set(npz))
    if not pids:
        print("ERROR: no probes found", file=sys.stderr)
        return 2

    rows = []
    for pid in pids:
        if pid not in sav:
            rows.append({"probe": pid, "var": "*", "verdict": "FAIL",
                         "detail": "MISSING_ORACLE_PROBE"})
            continue
        if pid not in npz:
            rows.append({"probe": pid, "var": "*", "verdict": "FAIL",
                         "detail": "MISSING_PY_PROBE"})
            continue
        ovars = load_oracle_probe(sav[pid])
        pvars = load_py_probe(npz[pid])
        for var in sorted(set(ovars) | set(pvars)):
            if var not in ovars:
                rows.append({"probe": pid, "var": var, "verdict": "FAIL",
                             "detail": "VAR_ONLY_IN_PY"})
                continue
            if var not in pvars:
                rows.append({"probe": pid, "var": var, "verdict": "FAIL",
                             "detail": "VAR_ONLY_IN_ORACLE"})
                continue
            spec = resolve_spec(policy, pid, var, ovars[var])
            row = compare_var(pid, var, ovars[var], pvars[var], spec, policy,
                              args.diag_max_size)
            if row["verdict"] == "FAIL" and args.png:
                png = render_png(args.out, pid, var, ovars[var], pvars[var], policy)
                if png:
                    row["png"] = os.path.basename(png)
            rows.append(row)

    fails = [r for r in rows if r["verdict"] == "FAIL"]
    first = fails[0] if fails else None
    summary = {
        "n_probes": len(pids),
        "n_rows": len(rows),
        "n_pass": sum(r["verdict"] == "PASS" for r in rows),
        "n_waived": sum(r["verdict"] == "WAIVED_PASS" for r in rows),
        "n_fail": len(fails),
        "all_pass": not fails,
        "first_divergence": ({"probe": first["probe"], "var": first["var"]}
                             if first else None),
        "orientation": policy.get("orientation"),
    }

    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, default=str)

    lines = ["# Parity Report", "",
             "- oracle: `%s`" % args.oracle,
             "- python: `%s`" % args.py,
             "- orientation: `%s` / nan_equal: %s" % (policy.get("orientation"), policy.get("nan_equal")),
             "- verdict: **%s** (pass %d, waived %d, fail %d / %d rows, %d probes)" % (
                 "ALL PASS" if summary["all_pass"] else "DIVERGED",
                 summary["n_pass"], summary["n_waived"], summary["n_fail"],
                 summary["n_rows"], summary["n_probes"]), ""]
    if first:
        lines += ["## ⚠ First divergence: `%s` / `%s`" % (first["probe"], first["var"]),
                  "```json", json.dumps(first, indent=2, default=str), "```", ""]
    lines += ["## All rows", "",
              "| probe | var | metric | verdict | detail |",
              "|---|---|---|---|---|"]
    for r in rows:
        detail = r.get("detail", "")
        if "iou" in r:
            detail += " iou=%.5f" % r["iou"]
        if "labels" in r:
            detail += " mean_iou=%.4f n=%d/%d" % (r["labels"]["mean_iou"],
                                                  r["labels"]["n_oracle"], r["labels"]["n_py"])
        if "stats" in r:
            s = r["stats"]
            if "max_abs_err" in s:
                detail += " max_abs=%.3g mism=%.4f%%" % (s.get("max_abs_err", 0),
                                                         100 * s.get("mismatch_frac", 0))
        if "hints" in r:
            detail += " hints=%s" % json.dumps(r["hints"], default=str)
        if "png" in r:
            detail += " [%s]" % r["png"]
        lines.append("| %s | %s | %s | %s | %s |" % (
            r["probe"], r["var"], r.get("metric", ""), r["verdict"], detail.strip()))
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("parity: %s  (pass %d, waived %d, fail %d)  -> %s" % (
        "ALL PASS" if summary["all_pass"] else "DIVERGED",
        summary["n_pass"], summary["n_waived"], summary["n_fail"], args.out))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print("ERROR: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        sys.exit(2)
