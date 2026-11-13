# Results changes

Every change to the numbers OpenSees Studio produces for its own examples, with
the value before and after. `tools/results_snapshot.py` pins a fingerprint of
each example case in `tests/data/results_snapshots.json` (largest displacement
per DOF, reaction sums, largest element force, norms, periods, step counts) and
CI fails when one moves by more than 1e-5 relative. A fix that changes results
on purpose is pinned with

```bash
python tools/results_snapshot.py --write --reason "what changed and why"
```

which appends the table below and is announced under **Results changed** in
`CHANGELOG.md`. An entry here is what to re-check in your own models.

Changes that predate the snapshots (before 0.0.57) are described in the
CHANGELOG only.

## 2026-11-13: SRSS response spectra: repeated modes aligned with the excitation (basis- and platform-independent)

| Example | Case | Quantity | Before | After |
|---|---|---|---|---|
| space_frame_3d | 4 | disp_max | [0.0138292, 0.0023943, 7.65388e-05] | [0.0140349, 1.4791e-15, 6.88994e-05] |
| space_frame_3d | 4 | force_max | 97117.3 | 98558.6 |
| space_frame_3d | 4 | reaction_max | [36784.5, 6345.59, 41512.3, 16794, 97117.3, 1.87229e-09] | [37327.8, 3.51477e-09, 37368.3, 9.0278e-09, 98558.6, 2.14695e-09] |
