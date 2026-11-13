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
