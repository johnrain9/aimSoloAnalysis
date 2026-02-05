# Segmentation Defaults and Validation Checklist (v0)

Date: 2026-02-05

Defaults (GPS-only)
- Distance grid: ds = 1.0 m
- Heading smoothing window: 5–7 points (5–7 m)
- Curvature smoothing: median(5) then low-pass (alpha 0.2–0.3)

Thresholds
- k_straight = 0.0008 1/m
- k_corner = 0.0025 1/m
- L_corner_min = 25 m
- L_straight_min = 50 m
- L_exit_min = 15 m
- L_gap_merge = 15 m
- overlap_min = 0.50
- L_apex_tolerance = 10 m

Quality gates
- Ignore points where speed < 5 m/s for segmentation (pit lane, in/out)
- Reject corner candidate if max speed drop within segment < 5% of lap median speed and |k| barely above k_corner
- If GPS quality seems poor (large jitter), increase smoothing window to 9–11 m and raise k_corner to 0.0030 1/m

Optional IMU fusion (if yaw_rate or lat_acc exists)
- k_imu = yaw_rate / max(speed, 2 m/s)
- Fused curvature: k = 0.7 * k_gps + 0.3 * k_imu
- If lat_acc is present, require |lat_acc| > 0.2 g inside a corner candidate to confirm

Validation checklist (per track, per direction)
1. Segment count stability
   - Turns per lap should be identical across laps (±0).
   - If it varies, check thresholds or smoothing.
2. Start/end stability
   - Start and end distances should vary by < 10 m across laps.
   - If larger, raise smoothing or increase L_corner_min.
3. Apex stability
   - Apex distances should vary by < 10 m across laps.
   - If larger, bias apex to min speed within segment.
4. False positives
   - No corners on straights: verify segments with low speed drop (<5%) are not labeled as corners.
5. Chicane handling
   - Adjacent corners separated by short straights should either remain split (if > L_gap_merge) or be merged consistently.
   - If chicanes merge incorrectly, reduce L_gap_merge to 10 m.
6. Direction consistency
   - Confirm CW/CCW signed curvature is consistent by checking first non-straight segment sign.
7. Pit lane / in-out laps
   - Ensure lap validity rules exclude out-laps and in-laps from reference segmentation.
