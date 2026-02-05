# Lean Proxy + Quality Gate (Speed + GPS Only)

This document defines a conservative lean proxy, quality gate, and how it should influence coaching advice when no explicit lean angle is available.

## Data Availability (CSV)
Example headers:
- `GPS Speed`, `GPS Radius`, `LateralAcc`, `InlineAcc`, `RollRate`, `GPS PosAccuracy`, `GPS SpdAccuracy`

All non-core columns are passed through into `RunData.channels` by header name in `ingest/csv/importer.py`, so these channels are available when present.

## Lean Proxy Equations
Let `g = 9.80665 m/s^2`, `v = speed_mps`, `a_lat = LateralAcc` (m/s^2), `r = GPS Radius` (m).

1) IMU-based (preferred when stable)

```
lean_deg_imu = atan(|a_lat| / g) * 180/pi
```

2) GPS-geometry fallback

```
lean_deg_gps = atan((v^2 / max(r, r_min)) / g) * 180/pi
```

Use `r_min = 15 m` to avoid blow-ups.

3) Blended (when both available and consistent)

If both valid and within 20%:

```
lean_deg = 0.6 * lean_deg_imu + 0.4 * lean_deg_gps
```

Otherwise prefer IMU if quality is good; else GPS.

## Quality Gate (Conservative)
Define `lean_quality` as `good`, `warn`, or `bad`.

Minimum validity checks:
- `v >= 8 m/s` (? 18 mph)
- `a_lat` present OR `GPS Radius` present
- If using GPS radius: `r >= 15 m` and `GPS PosAccuracy <= 2.0 m`
- If using IMU: `|roll_rate| <= 150 deg/s` (filter transition spikes)

Quality scoring:
- `good` when:
  - IMU present (`LateralAcc`) and stable; AND
  - `GPS PosAccuracy <= 1.5 m`; AND
  - `GPS SpdAccuracy <= 0.7 m/s` (? 1.6 mph), if available; AND
  - IMU vs GPS lean (when both available) within 20%.
- `warn` when:
  - Only one source available but passes validity; OR
  - GPS accuracy between 1.5?2.5 m; OR
  - IMU vs GPS lean disagree 20?35%.
- `bad` when:
  - Speed < 8 m/s, or
  - GPS accuracy > 2.5 m, or
  - IMU vs GPS lean disagree > 35%, or
  - Roll rate spikes during the segment.

## When to Ignore the Proxy
- `lean_quality = bad`
- Speed below threshold
- Straight segments with near-zero lateral acceleration
- High roll-rate transitions (mid-flip to opposite lean)

## Coaching Integration (Suppression Rules)
Lean thresholds (conservative):
- `lean_deg >= 42?`: suppress ?brake later / trail brake deeper.?
- `30? <= lean_deg < 42?`: allow entry brake advice only when line variance is low and apex stable.
- `lean_deg < 30?`: no lean-based suppression.

Guidance by phase:
- Entry: If lean is high, prefer ?smooth release, maintain line? over ?brake later.?
- Mid: If lean is high, avoid ?carry more speed?; use ?hold line, reduce mid-corner scrub.?
- Exit: Lean proxy does not block throttle-timing advice, but if lean is high and line unstable, treat late throttle as symptom.

## Known Failure Modes
- GPS Radius noise (poor GPS accuracy, low speed) can inflate lean.
- IMU bias / mounting errors can over-report lean.
- Banking/camber changes gravity components and inflates lean proxy.
- Roll rate transitions make instantaneous lean unreliable.
- GPS speed smoothing can misalign with lateral accel peaks.
