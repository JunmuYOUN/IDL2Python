# IDL2Python — Execution-Verified IDL→Python Conversion Harness

An agent-CLI harness that converts legacy IDL (`.pro`) code to Python and **verifies the
conversion by actually running both sides**: the original IDL produces *oracle* checkpoints,
the converted Python produces *twin* checkpoints, and a policy-driven comparator localizes the
first divergence and drives a fix loop until numerical parity. Built for solar & space-weather
research code (SunPy/Astropy ecosystem).

## Two language editions

The harness is identical in both editions — only the documentation language differs.

| Edition | Path | Docs |
|---|---|---|
| 🇬🇧 **English** | [`en/`](en/) | [`en/README.md`](en/README.md) |
| 🇰🇷 **한국어 (Korean)** | [`ko/`](ko/) | [`ko/README.md`](ko/README.md) |

Each edition is a self-contained agent-CLI harness. Open the edition folder as your working
directory so the CLI loads its `.claude/` agents and skills.

## What's inside each edition

```
en/  (or  ko/)
├── .claude/          agents + skills (the pipeline)
├── tools/            comparator, probe dumpers, IDL launcher, data fetch
├── config/           env / policy templates
├── README.md, INTRO.md, harness.json
└── _workspace/       workspace scaffold
```

## Requirements

IDL 8.x (license incl. 90-day trial; SSW only if the target code uses SolarSoft),
Python 3.10+ (numpy/scipy/astropy/pyyaml/matplotlib/pytest + sunpy/aiapy/drms/scikit-image),
an agent CLI that loads `.claude/`. GPU not required. See the per-edition README for setup.

## IDL source examples (SolarSoft)

The harness can fetch `.pro` files straight from a web directory index. Canonical SolarSoft trees to browse for conversion targets:

- Instrument & analysis packages: <https://sohoftp.nascom.nasa.gov/solarsoft/packages/>
- General SSW utilities (`gen`): <https://sohoftp.nascom.nasa.gov/solarsoft/gen/>
