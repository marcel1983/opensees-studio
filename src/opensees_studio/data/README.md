# `aisc_v16.csv` — AISC v16 shape table

Section properties of 1660 standard shapes: W, HP, M, S, C, MC, WT, MT, ST, L,
PIPE, HSS (rectangular and square) and HSS_R (round).

**Units are US customary**, as published: inches, in², in⁴, in⁶ and lb/ft. The
application converts to the project's unit system when a shape is inserted
(length² and length⁴ factors), and shows the converted values in the dialog.

## Where the numbers come from

- **AISC Shapes Database v16.0** / Steel Construction Manual, 16th edition —
  the properties themselves.
- **[steelpy](https://pypi.org/project/steelpy/)** 1.1.1 (Apache-2.0), whose
  shape files state they are consistent with the 16th edition — the machine
  readable form this table is generated from. Its licence text is kept beside
  this file as `LICENSE-steelpy.txt`, as Apache-2.0 requires.

The columns are a subset: geometry (`d`, `bf`, `tw`, `tf`, `od`, `tnom`) and
the properties a frame section needs (`area`, `ix`, `iy`, `j`, `cw`) plus the
ones the picker shows (`weight`, `zx`, `sx`, `rx`, `zy`, `sy`, `ry`). Double
angles are left out: a built-up section has its own axis conventions and the
application has no model for it.

Nobody transcribed these by hand. Regenerate with:

```bash
pip download --no-deps --dest /tmp/steelpy steelpy
python -c "import zipfile; zipfile.ZipFile('/tmp/steelpy/steelpy-1.1.1-py3-none-any.whl').extractall('/tmp/steelpy')"
python tools/build_aisc_data.py --source /tmp/steelpy/steelpy/"shape files"
```

`tests/unit/test_aisc.py` checks the table's internal consistency on every row
(radii of gyration against areas and inertias, section moduli against depth,
plastic against elastic) and recomputes one whole family from first
principles: round HSS, where AISC's design-wall-thickness rule
(`t_des = 0.93 t_nom`) reproduces the published A, I and J to within the
rounding of a three-significant-figure table. A wrong or missing row fails the
suite.

## Cross-check against an independent edition

The values were also compared with `aiscpy` (GPL-3.0), an unrelated package
whose database is the AISC **13th** edition — an older edition, so a handful of
properties legitimately differ:

| Family | Shapes in common | Ix within 1% | A within 0.1 in² |
| --- | --- | --- | --- |
| W, M, S, HP | 303 | **303 / 303** | 248 / 303 |
| C, MC | 28 | 28 / 28 | 27 / 28 |

The area differences are one rounding step at the published 0.1 in²
granularity, not disagreements. No shape in common differed on Ix.

That check is recorded rather than automated: it needs an external database
that the repository does not ship, and pinning a second dataset to make a test
green would prove less than the consistency and closed-form checks do.


## A note on redistribution

The properties are facts published by AISC, and this file is generated from an
Apache-2.0 package that publishes them. If you redistribute this application
commercially, satisfy yourself about AISC's own terms for the Shapes Database;
that review has not been done here.
