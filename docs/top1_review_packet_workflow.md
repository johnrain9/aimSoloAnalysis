# Top-1 Review Packet Workflow

Command:

```powershell
$env:PYTHONPATH='.'; python tools/build_top1_review_packet.py --sample-size 25 --seed 11
```

Outputs:

- `artifacts/top1_review_packet.md`
- `artifacts/top1_review_packet.csv`

Purpose:

- Produce a deterministic coach-review packet for qualitative top-1 recommendation quality checks.
- Bias sampled cases toward failures/outliers while preserving some passing examples.
- Explicitly declare human-reviewed vs auto-scored requirement modes.

Cadence and traceability (RQ-NFR-007):

- Run at least once per evaluation cycle (weekly or release-candidate gate).
- Each review log must capture: `date`, `reviewer`, `scenario_set`, and `disposition`.
- Review verdicts and notes are captured per sampled case in the CSV (`reviewer_verdict`, `reviewer_notes`).

Error handling:

- Missing inputs emit clear actionable errors and still write minimal packet artifacts.
- Non-pass packet generation exits non-zero to support automation gates.
