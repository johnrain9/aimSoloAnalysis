# Insight Design — AiM Solo Analysis

## Goal

Replace jargon-heavy statistical insights with coach-style advice a rider can act on.

**Bad:** "Line spread is about 9.2 ft wider than reference; repeat one turn-in and apex marker to cut spread by about 3.0 ft."

**Good:** "T7: You coasted for 1.85s mid-corner at 79mph. You were pulling 1.15 latG (your peak this lap is 1.29g in T11) — you had grip to spare. Get on the gas earlier."

## Data Foundation

### AiM Solo 2 Available Channels

GPS-only device — no throttle position or brake pressure sensors.

| Channel | What it tells us |
|---------|-----------------|
| GPS Speed | Ground speed (stored in m/s in RunData — multiply by 2.237 for mph) |
| GPS LonAcc | Longitudinal acceleration — negative = braking, positive = accelerating |
| GPS LatAcc | Lateral acceleration — cornering G-force |
| GPS Heading | Compass direction — heading rate = turn-in/turn-out |
| GPS Lat/Lon | Position — line comparison, apex proximity |
| RollRate, PitchRate, YawRate | Rotational rates — potential grip/stability indicators |

### Key Unit Bug

RunData `speed` field is in **meters per second**, not km/h. Use `MPS_TO_MPH = 2.23694`. The existing analytics pipeline may also have this wrong.

### Corner Identification

The existing `analytics/segments.py` auto-detection is broken (curvature thresholds miscalibrated, returns 1 segment for entire lap).

**Solution:** Track reference templates in `tools/track_references.py`. Define corners once per track by distance-from-start/finish, match all laps by distance. HPR Full CCW 15-turn template confirmed correct.

### Derivable Signals (no throttle/brake sensor needed)

| Signal | How to detect | Threshold |
|--------|--------------|-----------|
| Braking | LonAcc < -0.1g | |
| Accelerating | LonAcc > +0.1g | |
| Neutral throttle | -0.1g ≤ LonAcc ≤ +0.1g | Duration is key metric |
| Trail braking | LonAcc < -0.1g AND \|LatAcc\| > 0.3g | Braking while cornering |
| Turn-in point | Heading rate spike | |
| Corner speed | Min speed within corner bounds | |
| Drive-off timing | When LonAcc goes positive after apex | |

## P0 Insight: Neutral Throttle Duration

### Why this is #1

- Clearly detectable from GPS-only data (no sensor ambiguity)
- Universally actionable — every rider can "get on the gas earlier"
- Validated against real data: Paul confirmed T7 (1.85s), T11 (1.3s), T2 (0.95s) are all real issues

### Validated Examples (Session 87, Lap 2)

| Corner | Neutral Time | What's happening |
|--------|-------------|-----------------|
| T7 (fast R sweeper) | 1.85s | Coasting at 79mph mid-corner. LatG shows grip available. |
| T11 (long R turn) | 1.30s | Coasting at apex (48mph) with 1.29 latG. Has traction. |
| T3 (R sweeper to straight) | 1.05s | Transition from turning to full throttle. Possibly less actionable. |
| T2 (R hairpin) | 0.95s | Coasting at 45mph with 1.12 latG. May be grip-limited — needs nuance. |
| T7 (fast R sweeper) | 1.85s | Worst offender. Clear coaching target. |

### Insight Template

**High confidence (grip headroom visible):**
> T7: You coasted for 1.85s mid-corner at 79mph. You were pulling 1.15 latG (your peak this lap is 1.29g in T11) — you had grip to spare. Get on the gas earlier.

**Lower confidence (at/near grip limit):**
> T2: You had 0.95s of neutral throttle at 45mph. You were at 1.12 latG though (close to your 1.29g peak) — are you grip-limited here, or is there room to roll on earlier?

## Grip Context (Research Pending)

Raw G-force numbers need a reference to be meaningful. Current approach:
- Compare to rider's own peak latG from the same lap
- Phrasing: "your peak this lap is X in TY" (concrete corner reference > percentage)

### Open Questions (CENTRAL-OPS-94 dispatched)

1. Is latG alone sufficient, or need combined G (friction circle: √(latG² + lonG²))?
2. Theoretical max latG for R6 on race tires?
3. Should braking-phase grip vs acceleration-phase grip be distinguished?
4. Do roll rate / yaw rate add useful grip information?

## Insight Design Principles

1. **Singular** — One observation, one fix per insight.
2. **Observable** — Something the rider can feel on the bike.
3. **Concrete** — Visual/physical language, not telemetry jargon.
4. **Actionable** — Says what to DO differently.
5. **Nuanced** — Present uncertainty when confidence is lower. Ask the rider a question rather than giving bad advice.

## Tools Built

| Tool | Purpose | Usage |
|------|---------|-------|
| `tools/track_references.py` | Track corner templates by distance | `detect_track(rd_lap)` returns `TrackReference` |
| `tools/lap_telemetry.py` | Per-lap trace + corner summary | `PYTHONPATH=. python3 tools/lap_telemetry.py test_data/87.csv --lap 2 --summary` |
| `tools/lap_compare.py` | Lap-vs-lap corner deltas | `PYTHONPATH=. python3 tools/lap_compare.py test_data/87.csv --target 2 --ref 3` |

## HPR Full CCW — 15 Turn Reference

Source: Session 87 lap 2 (1:55.37), confirmed by Paul.

| Turn | Dir | Entry m | Apex m | Exit m | Character |
|------|-----|---------|--------|--------|-----------|
| T1 | L | 100 | 200 | 290 | Brake 116→61mph |
| T2 | R | 325 | 405 | 530 | Hairpin, min 45mph |
| T3 | R | 560 | 660 | 830 | Sweeper, accel 71→108mph |
| — | — | 830 | — | 1300 | BACK STRAIGHT 112→140mph |
| T4 | R | 1325 | 1490 | 1570 | Brake 140→80mph |
| T5 | L | 1590 | 1680 | 1740 | Brake to 51mph |
| T6 | R | 1845 | 1950 | 2035 | Hairpin, hard brake to 37mph |
| T7 | R | 2200 | 2315 | 2440 | Fast sweeper, 78mph min |
| T8 | L | 2460 | 2600 | 2680 | Hairpin, min 32mph (slowest) |
| T9 | R | 2680 | 2755 | 2870 | Fast kinks 9a(R)+9b(L) |
| T10 | R | 2910 | 2985 | 3080 | Brake to 70mph |
| T11 | R | 3120 | 3230 | 3325 | Long turn, brake to 48mph |
| T12 | L | 3395 | 3450 | 3520 | Fast kink, no brake |
| T13 | L | 3560 | 3640 | 3665 | Hard brake to 47mph |
| T14 | R | 3680 | 3715 | 3745 | Quick right, 59→66mph |
| T15 | L | 3755 | 3820 | 3900 | Left, then gas to front straight |

Total lap distance: ~4023m (~2.50mi)
