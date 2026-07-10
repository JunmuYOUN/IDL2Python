#!/usr/bin/env python
"""
fetch_data.py — acquire parity verification inputs with a manifest trail.

Every downloaded file is appended to <out>/manifest.jsonl:
  {ts, route, query, file, sha256, bytes}
Existing files are never deleted; name collisions get a .dupN suffix.

Subcommands
  vso   — public VSO search via sunpy Fido (no auth)
  jsoc  — JSOC export via drms (registered email REQUIRED — ask the user;
          never hardcode an address in code or config)
  url   — direct HTTP(S) download

Examples (run on the server, conda env torchV2):
  python fetch_data.py vso  --time 2017-01-01T00:00:00 --window 60 \
      --instrument aia --wavelength 193 --out {work}/data
  python fetch_data.py jsoc --series hmi.M_720s --time 2017-01-01T00:00:00/1m \
      --email USER_PROVIDED --out {work}/data
  python fetch_data.py url  --url https://.../file.fits --out {work}/data
"""
import argparse
import datetime
import hashlib
import json
import os
import sys


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def unique_path(path):
    """Never overwrite pre-existing data: append .dupN instead."""
    if not os.path.exists(path):
        return path
    n = 1
    while os.path.exists("%s.dup%d" % (path, n)):
        n += 1
    return "%s.dup%d" % (path, n)


def record(outdir, route, query, files):
    os.makedirs(outdir, exist_ok=True)
    manifest = os.path.join(outdir, "manifest.jsonl")
    with open(manifest, "a", encoding="utf-8") as f:
        for fp in files:
            entry = {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "route": route,
                "query": query,
                "file": os.path.basename(fp),
                "sha256": sha256_of(fp),
                "bytes": os.path.getsize(fp),
            }
            f.write(json.dumps(entry) + "\n")
            print("manifest +", entry["file"], entry["bytes"], "bytes")
    print("manifest ->", manifest)


def cmd_vso(args):
    import astropy.units as u
    from sunpy.net import Fido
    from sunpy.net import attrs as a

    t0 = datetime.datetime.fromisoformat(args.time)
    t1 = t0 + datetime.timedelta(seconds=args.window)
    query = [a.Time(t0.isoformat(), t1.isoformat()),
             a.Instrument(args.instrument)]
    if args.wavelength is not None:
        query.append(a.Wavelength(args.wavelength * u.angstrom))
    if args.sample:
        query.append(a.Sample(args.sample * u.second))
    res = Fido.search(*query)
    print(res)
    n = sum(len(block) for block in res)
    if n == 0:
        print("no results", file=sys.stderr)
        return 1
    take = res[0, : args.max] if args.max else res
    os.makedirs(args.out, exist_ok=True)
    files = Fido.fetch(take, path=os.path.join(args.out, "{file}"), progress=False)
    if files.errors:
        print("fetch errors:", files.errors, file=sys.stderr)
    record(args.out, "C:vso",
           {"time": args.time, "window": args.window,
            "instrument": args.instrument, "wavelength": args.wavelength},
           list(files))
    return 0 if files else 1


def cmd_jsoc(args):
    import drms

    if not args.email:
        print("JSOC requires a registered email (--email). Ask the user; "
              "never hardcode.", file=sys.stderr)
        return 2
    client = drms.Client()
    qstr = "%s[%s]" % (args.series, args.time)
    if args.segments:
        qstr += "{%s}" % args.segments
    print("jsoc export:", qstr)
    exp = client.export(qstr, method="url", protocol="fits", email=args.email)
    exp.wait()
    os.makedirs(args.out, exist_ok=True)
    dl = exp.download(args.out)
    files = [str(p) for p in dl.download]
    record(args.out, "C:jsoc", {"series": args.series, "time": args.time,
                                "segments": args.segments}, files)
    return 0 if files else 1


def cmd_url(args):
    import urllib.request

    os.makedirs(args.out, exist_ok=True)
    name = args.name or args.url.rstrip("/").split("/")[-1] or "download.bin"
    dest = unique_path(os.path.join(args.out, name))
    print("GET", args.url, "->", dest)
    with urllib.request.urlopen(args.url, timeout=120) as r, open(dest, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    record(args.out, "C:url", {"url": args.url}, [dest])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("vso", help="public VSO search/fetch (sunpy Fido)")
    p.add_argument("--time", required=True, help="ISO start time")
    p.add_argument("--window", type=int, default=60, help="seconds after start")
    p.add_argument("--instrument", required=True)
    p.add_argument("--wavelength", type=int, default=None, help="angstrom")
    p.add_argument("--sample", type=int, default=None, help="cadence seconds")
    p.add_argument("--max", type=int, default=4, help="max files (0=all)")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_vso)

    p = sub.add_parser("jsoc", help="JSOC export (email required)")
    p.add_argument("--series", required=True)
    p.add_argument("--time", required=True, help="JSOC time spec, e.g. 2017-01-01T00:00:00/1m")
    p.add_argument("--segments", default="")
    p.add_argument("--email", required=True, help="user-provided registered email")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_jsoc)

    p = sub.add_parser("url", help="direct download")
    p.add_argument("--url", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_url)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print("ERROR: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        sys.exit(2)
