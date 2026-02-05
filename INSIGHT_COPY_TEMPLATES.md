# Insight Copy Templates (Synthesis-Aligned, Imperial Units)

This document provides a full rewrite of insight copy so it is actionable, non-conflicting, and consistent with synthesis logic. All distance/speed references are in feet and mph.

---

## Template Table (Insight ID -> Title/Detail/Actions + Variants)

| Insight ID | Title | Detail (1?2 sentences) | Actions (max 3, include how) | Variants (conditional copy) |
|---|---|---|---|---|
| early_braking / entry_speed | Keep Entry Speed Up | Entry speed is down and the speed trace shows an early slow-down before the apex. Focus on keeping entry speed without upsetting the line. | 1. Shift your brake marker about 10?15 ft later **or** reduce initial brake to keep entry speed. 2. Trail off smoothly to the apex to avoid a second slow-down. 3. Recheck entry speed delta next lap to confirm improvement. | Lean high: ?Entry is slow at high lean; prioritize smooth release and line stability before moving the brake marker.? Line variance high: ?Line is inconsistent; stabilize turn-in and apex marks before adjusting braking.? Entry speed normal: suppress. Apex delta large: ?Apex location moved; fix line first, then revisit entry speed.? |
| line_inconsistency | Make the Line Repeatable | Your path varies more than the reference, which makes speed and throttle timing inconsistent. Fixing line consistency is the safest first gain. | 1. Pick one turn-in point and hit it every lap (use a fixed trackside marker). 2. Aim for a single apex marker and avoid mid-corner corrections. 3. Re-run the segment and compare line variance. | Lean high: add ?Hold a stable lean angle; avoid mid-corner steering changes.? Line variance low: suppress. Entry speed low: keep line priority, do not mention braking. Apex delta large: ?Apex shifted; lock in apex marker before chasing speed.? |
| corner_speed_loss (min speed) | Hold More Mid-Corner Speed | Minimum speed at the apex is lower than the reference with a stable line. Focus on reducing scrub mid-corner. | 1. Release brake a touch earlier to keep speed through the apex. 2. Hold a steady line and avoid extra steering input at peak lean. 3. Compare min-speed delta after each change. | Lean high: ?At high lean, prioritize a smooth release and holding line over speed gains.? Line variance high: suppress and point to line consistency instead. Entry speed low: ?Entry speed may be the root; fix entry first if it?s down.? Apex delta large: ?Apex moved; fix line before pushing mid-corner speed.? |
| late_throttle_pickup | Start Drive Sooner | The speed trace suggests throttle pickup is later than the reference after the apex. Earlier drive should improve exit speed if the line is stable. | 1. Begin a gentle roll-on closer to the apex (about 10?15 ft earlier). 2. Increase throttle smoothly while keeping the bike on the same line. 3. Check exit speed delta to confirm. | Lean high: ?At high lean, focus on a smooth, earlier roll-on rather than a big pickup.? Line variance high: ?Delay is likely line-related; stabilize line before earlier pickup.? Entry speed low: no change. Apex delta large: ?Apex moved; fix apex location before changing pickup timing.? |
| exit_speed | Improve Exit Drive | Exit speed and acceleration after the apex are down compared to reference. The line looks stable, so earlier drive is the likely gain. | 1. Start roll-on at or just after apex and add throttle progressively. 2. Keep the bike tracking to the same exit point to avoid hesitation. 3. Compare exit speed delta after each adjustment. | Lean high: ?Use a smooth, progressive roll-on at high lean.? Line variance high: suppress and emphasize line consistency. Entry speed low: no change. Apex delta large: ?Apex moved; correct apex location before pushing exit drive.? |
| neutral_throttle (coasting) | Reduce Coasting | The speed trace shows a long neutral zone with flat speed. Decide earlier between braking and drive. | 1. If before apex: choose a clearer brake-to-release plan so you aren?t coasting. 2. At apex: hold a light maintenance throttle instead of neutral. 3. After apex: transition to a smooth roll-on earlier. | Lean high: add ?Keep inputs smooth; avoid abrupt changes.? Line variance high: ?Neutral zone may be from line corrections; stabilize line first.? Entry speed low: emphasize entry decision. Apex delta large: emphasize apex stability. |
| steering_smoothness (IMU only) | Smooth Steering Through Apex | Yaw activity is higher while minimum speed is lower, suggesting extra steering input mid-corner. Smoother steering should help carry speed. | 1. Reduce mid-corner corrections by fixing a single apex marker. 2. Make one clean steering input and hold it longer. 3. Recheck yaw and min-speed deltas. | Lean high: add ?Hold steady lean; avoid additional steering at peak lean.? Line variance high: prioritize line consistency. Entry speed low: no change. Apex delta large: ?Apex moved; fix apex point before fine-tuning steering.? |
| light_brake (new) | Shorten the Light-Brake Zone | The decel zone is long and shallow before the apex, which costs entry speed. Tighten the braking phase without upsetting the line. | 1. Use a slightly firmer initial brake, then release earlier to hit apex speed. 2. Shorten the brake zone by 10?15 ft while keeping the same turn-in. 3. Recheck decel duration and entry speed delta. | Lean high: ?Avoid ?brake later?; focus on smoother release and stability.? Line variance high: suppress and focus on line consistency. Entry speed normal: suppress. Apex delta large: fix line first. |
| light_throttle (new) | Increase Roll-On After Apex | The speed trace shows a long neutral/soft-drive zone after the apex. Earlier, smoother roll-on should improve exit speed. | 1. Start a gentle roll-on 10?15 ft earlier. 2. Keep throttle increase smooth while holding the same exit line. 3. Recheck exit speed delta and neutral-zone duration. | Lean high: ?Use a gradual roll-on to stay stable at lean.? Line variance high: suppress and focus on line stability. Entry speed low: no change. Apex delta large: fix apex location first. |

---

## Phrases To Avoid And Replacements
Avoid: ?Carry more speed.?
Replace: ?Reduce mid-corner scrub by releasing brake a touch earlier while holding the same line.?

Avoid: ?Brake later.?
Replace: ?Shift your brake marker about 10?15 ft later **or** reduce initial brake to keep entry speed.?

Avoid: ?Get on the gas sooner.?
Replace: ?Start a gentle roll-on 10?15 ft earlier while keeping the bike on the same exit line.?

Avoid: ?Increase trail braking.?
Replace: ?Hold a light, smooth release to the apex without a second slow-down.?

Avoid: ?Fix your line.?
Replace: ?Use a fixed turn-in and apex marker and repeat the same path each lap.?

Avoid: ?You?re coasting.?
Replace: ?The speed trace shows a long neutral zone; decide earlier between braking and drive.?

Avoid: ?Steer less.?
Replace: ?Make one clean steering input and hold it longer through the apex.?

---

## Required Evidence Per Insight

early_braking / entry_speed
- `entry_speed_delta` (mph)
- `brake_point_delta` (ft)
- `segment_time_delta` (s)
- Optional: `line_stddev` (ft) for suppression context

line_inconsistency
- `line_stddev` (ft) and/or `line_stddev_delta` (ft)
- Optional: `segment_time_delta` (s)

corner_speed_loss (min speed)
- `min_speed_delta` (mph)
- `line_stddev` (ft) to confirm stability
- Optional: `apex_delta` (ft)

late_throttle_pickup
- `throttle_pickup_delta` (ft or s)
- `exit_speed_delta` (mph) if available
- `line_stddev` (ft) or `apex_delta` (ft) for suppression context

exit_speed
- `exit_speed_delta` (mph)
- `inline_acc_rise_delta` (g) if available
- Optional: `line_stddev` (ft)

neutral_throttle (coasting)
- `neutral_throttle_s` (s)
- `neutral_throttle_dist` (ft)
- `neutral_speed_delta` (mph)
- Optional: `segment_time_delta` (s)

steering_smoothness (IMU only)
- `yaw_rms_ratio` (unitless)
- `min_speed_delta` (mph)

light_brake (new)
- `decel_time_s` (s)
- `decel_dist` (ft)
- `decel_avg_g` (g)
- `entry_speed_delta` (mph)
- `segment_time_delta` (s)

light_throttle (new)
- `neutral_throttle_s` (s)
- `neutral_throttle_dist` (ft)
- `inline_acc_rise_g` (g)
- `throttle_pickup_delta` (ft or s)
- `exit_speed_delta` (mph)

---

## Proxy-Safe Language Constraints
Avoid implying brake/throttle sensors exist. Use speed-based wording:
- ?The speed trace shows a long, shallow decel zone before the apex.?
- ?Speed rise after apex starts later than reference.?
- ?A long neutral zone with flat speed suggests a delayed transition to drive.?

Use ?suggests? or ?indicates? for proxy-driven advice.
