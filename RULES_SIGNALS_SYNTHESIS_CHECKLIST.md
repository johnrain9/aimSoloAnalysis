# Rules -> Signals -> Synthesis Migration Checklist

This checklist covers API payload changes, UI changes, and risks/mitigations for moving to a rules ? signals ? synthesis pipeline.

---

## API Payload Changes
1. Add `signals` to `/insights/{session_id}` response.
   - Include per-segment signal scores (entry/mid/exit), detected proxy flags (line unstable, light brake, light throttle), and confidence.
2. Add `synthesis` to `/insights/{session_id}` response.
   - Include primary insight per segment, suppressed insights, and ?why? fields (phase chosen, conflicts resolved).
3. Preserve current `items` schema for backward compatibility.
   - Map synthesized primary insights into `items` so UI continues to render.
4. Add `units` to `/summary`, `/insights`, `/compare`, `/map`.
   - Required for imperial conversions and UI labels.
5. Add `insights_version` or `synthesis_version`.
   - Ensures UI and API agree on schema and copy style.
6. Update `track_map` payload if segment filtering needs signals/synthesis context.
   - Keep map geometry stable (do not change distances unless points are converted too).

---

## UI Changes (`ui/app.js`)
1. Support `insights.signals` and `insights.synthesis` if present.
   - Keep `items` as primary list until UI is updated to show synthesis reasons.
2. Update `formatEvidence()` to handle new signal evidence fields.
   - Include decel zone, neutral zone, line stability flags, etc.
3. Add ?Why this matters? details from synthesis reasoning (optional).
4. Respect `units` flag for labels (mph/ft).
5. Handle suppressed insights display (e.g., ?Not shown: line consistency takes priority?).

---

## Pipeline Changes (Rules -> Signals -> Synthesis)
1. Split current `rules.py` into:
   - `signals.py`: computes raw signal flags + strengths.
   - `synthesis.py`: resolves conflicts + chooses primary insight.
2. Update `analytics/trackside/pipeline.py` to return signals + synthesis.
3. Keep `rules.py` as a compatibility layer that builds `items` from synthesis.

---

## Risks + Mitigation
1. **Risk: UI breaks due to schema changes**
   - Mitigation: keep `items` intact; add new fields as additive.
2. **Risk: Mixed unit display (mph/ft vs km/h/m)**
   - Mitigation: add `units` flag and convert at API boundary; UI only formats.
3. **Risk: Duplicate/conflicting insights**
   - Mitigation: synthesis must output max one primary per segment; include `suppressed` list for transparency.
4. **Risk: Signal noise from GPS**
   - Mitigation: include quality flags in signals and downgrade confidence.
5. **Risk: Users can?t understand why an insight won**
   - Mitigation: include `reason` and `evidence` fields in synthesis output.
6. **Risk: Track map filtering breaks if units change**
   - Mitigation: keep map geometry in metric unless all point distances are converted together.
7. **Risk: Backfill bugs in historical sessions**
   - Mitigation: add `insights_version` and only enable synthesis for versioned responses.
