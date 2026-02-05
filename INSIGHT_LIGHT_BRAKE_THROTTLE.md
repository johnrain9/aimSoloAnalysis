# Light Braking + Light Throttle Heuristics (Speed-Only)

This document proposes speed-only heuristics to detect ?light braking? and ?light throttle? for synthesis, using metrics currently available in `analytics/segment_metrics.py`.

## Available Inputs
- Speed: `entry_speed_kmh`, `apex_speed_kmh`, `exit_speed_30m_kmh`, `min_speed_kmh`
- Timing/markers: `brake_point_dist_m`, `throttle_pickup_dist_m`, `throttle_pickup_time_s`
- Derived accel: `inline_acc_g`, `inline_acc_rise_g`
- Line stability: `line_stddev_m`, `yaw_rms`
- Quality: `using_speed_proxy`, `gps_accuracy_m`, `satellites`, `speed_noise_sigma_kmh`

---

## Light Braking (Entry Phase)

### Intuition
Long, shallow decel into the apex: early braking with low decel magnitude, causing time loss before apex.

### Derived Metrics (per segment)
Let `start_m = seg_start`, `apex_m = apex_dist_m`, `entry_m = max(start_m, apex_m - 25m)`.

- `v_entry = speed(entry_m)`
- `v_apex = speed(apex_m)`
- `dv = v_apex - v_entry` (negative for decel)
- `dt = time(apex_m) - time(entry_m)`
- `decel_avg_g = (dv / dt) / g` (negative)
- `decel_dist_m = apex_m - entry_m`
- `decel_time_s = dt`
- `decel_g_per_10m = |decel_avg_g| * (10 / max(1, decel_dist_m))`

### Trigger (ALL must be true)
- `brake_point_delta_m <= -10` OR `entry_speed_delta_kmh <= -3`
- `decel_time_s >= 0.9` OR `decel_dist_m >= 22`
- `|decel_avg_g| <= 0.08`
- `segment_time_delta_s >= 0.06`

**Normalization by entry speed**
Allow slightly higher decel threshold at higher speed:

```
|decel_avg_g| <= 0.08 + 0.02 * clamp((v_entry_kmh - 100) / 50, 0, 1)
```

### False Positive Guards
- Suppress if `line_stddev_m > 1.5` or `yaw_rms` high (line instability).
- Suppress if `speed_noise_sigma_kmh >= 0.7`.
- Suppress if `using_speed_proxy` and `gps_accuracy_m > 2.0`.

### Evidence Fields
- `decel_avg_g`, `decel_time_s`, `decel_dist_m`, `decel_g_per_10m`
- `entry_speed_kmh`, `apex_speed_kmh`
- `brake_point_delta_m`, `segment_time_delta_s`
- `line_stddev_m`, `yaw_rms`
- `speed_noise_sigma_kmh`, `using_speed_proxy`

---

## Light Throttle (Exit Phase)

### Intuition
Long neutral/maintenance acceleration after apex, with slow acceleration rise and delayed pickup.

### Trigger (ALL must be true)
- `neutral_throttle_s >= 1.0` OR `neutral_throttle_dist_m >= 15`
- `neutral_speed_delta_kmh <= 1.0` (flat speed)
- `inline_acc_rise_g <= 0.05` (slow accel rise)
- `segment_time_delta_s >= 0.06`
- `throttle_pickup_dist_m` later than reference by `>= 12m` OR `throttle_pickup_time_s >= 0.12s`

**Normalization by exit speed**
If `exit_speed_delta_kmh <= -3`, allow `inline_acc_rise_g <= 0.07` to catch weak roll-on.

### False Positive Guards
- Suppress if `line_stddev_m > 1.5` or `apex_delta_m` large (late throttle may be line symptom).
- Suppress if `speed_noise_sigma_kmh >= 0.7`.
- Suppress if `using_speed_proxy` and `gps_accuracy_m > 2.0`.

### Evidence Fields
- `neutral_throttle_s`, `neutral_throttle_dist_m`, `neutral_speed_delta_kmh`
- `inline_acc_rise_g`
- `throttle_pickup_dist_m`, `throttle_pickup_time_s`
- `exit_speed_30m_kmh`, `exit_speed_delta_kmh`
- `segment_time_delta_s`
- `line_stddev_m`, `apex_delta_m`
- `speed_noise_sigma_kmh`, `using_speed_proxy`

---

## Synthesis Integration
- Treat ?light braking? as an **entry-phase** issue.
- Treat ?light throttle? as an **exit-phase** issue.
- Apply conflict resolver: if line instability is primary, suppress these as recommendations and record as symptoms in evidence.
