# Advanced Insights R&D Design Doc (Virtual Faster Reference)

Date: 2026-02-05

**Context and Constraints**
- Data channels include GPS speed, distance, heading, lat/lon, slope, accuracy metrics, and IMU-derived accelerations and rates.
- No throttle, brake, or RPM are guaranteed.
- Analyses must be per track and direction (CW/CCW).
- Deliver both trackside quick insights and deeper at-home analysis.

**1) Taxonomy of Advanced Insights (Predictive, Theoretical, Model-Based)**
- Limit-based physics insights: Grip envelope utilization, maximum feasible speed vs curvature, braking distance feasibility, line feasibility under slope and camber assumptions.
- Counterfactual and what-if insights: "If entry speed drops by X km/h, exit speed gain of Y km/h is feasible"; "Apex shift of Z m yields earlier throttle proxy release."
- Skill-transfer insights: Pro-derived corner archetype targets (entry, apex, exit) mapped onto local corners; predicted delta if riding style matches an archetype.
- Predictive improvement estimates: Forecasted time gain per corner and per segment, with uncertainty.
- Consistency and stability insights: Variance in braking points, turn-in points, and apex timing across laps.
- Risk and robustness insights: Sections where predicted gains are low-confidence due to GPS quality or dynamics outside envelope.
- Trackside quick vs deep analysis split: Quick uses light geometry and speed profiles; deep uses physics/ML fusion and uncertainty-aware ranking.

**2) Virtual Faster Rider Baselines (3 Options)**

**Option A: Physics-Based Minimum-Lap-Time / Optimal Control (GGV or GGG constraints)**
- Data requirements: Track map, curvature profile, elevation/slope, approximate vehicle parameters or fitted envelopes from data.
- Math/algorithms: Minimum-time optimal control with path constraints; use g-g or g-g-v (and optionally g-g-g) envelopes as constraints; solve via direct transcription or collocation with NLP solvers. [R1][R2][R3][R4][R5][R7][R8]
- Expected runtime: Minutes to hours per track direction depending on discretization, solver, and model fidelity; faster for quasi-steady-state envelopes than full dynamic models. [R4][R5]
- Risks: Envelope mis-calibration, nonstationary track grip, unknown power limits, under-modeled rider behavior; solver sensitivity to track map quality.
- Calibration steps: Fit g-g envelope to observed lateral/longitudinal acceleration; adjust for slope and speed effects; validate against best recorded laps and check physical feasibility. [R4][R6][R7]
- Output baseline: A physically feasible speed profile and line with theoretical minimum time and per-point slack to rider laps.

**Option B: Skill-Transfer Model Using Pro Data from Other Tracks**
- Data requirements: Pro or expert laps across multiple tracks; normalized corner features (curvature, entry radius, slope, speed bands); current rider laps for target track.
- Math/algorithms: Learn mapping from corner archetype features to target speed/accel profiles; domain adaptation by corner normalization (curvature-radius, speed-normalized accel); optionally use metric learning or conditional sequence models.
- Expected runtime: Training hours offline; inference seconds per lap; clustering/archetype mapping minutes per track.
- Risks: Domain shift (bike/vehicle differences), overfitting to pro style, insufficient coverage of corner types; bias if pro data is not comparable.
- Calibration steps: Align speed scales using straight-line acceleration limits; normalize by local curvature and slope; apply safety cap using observed g-g envelope.
- Output baseline: "Virtual pro" speed profile and target micro-trajectory per corner type with uncertainty bands.

**Option C: Hybrid Best-of-Sectors + Physics Constraints**
- Data requirements: Multiple laps per rider; track segmentation; curvature profile; approximate g-g envelope from data.
- Math/algorithms: Construct best-of-sectors or best-of-corner fragments; fuse them using dynamic feasibility checks and smoothing; enforce g-g/ggv limits to avoid infeasible transitions. [R4][R5][R6][R8]
- Expected runtime: Minutes per session; can be near real time for trackside use.
- Risks: Fragment stitching may introduce unrealizable transitions; fragments may be biased by GPS noise.
- Calibration steps: Use acceleration bounds from data; re-optimize transitions with short-horizon optimal control; validate against time-sum consistency.
- Output baseline: A "fastest-feasible" composite lap that is more aggressive than best lap but still physically plausible.

**3) ML Ideas Specific to Our Data**
- Supervised improvement prediction: Predict delta-speed profile or time gain per segment using sequence models (TCN, GRU, transformer) trained on historical improvements; targets can be future best laps or synthetic improvements.
- Self-supervised representation learning: Contrastive learning on lap segments (positive pairs: same corner across laps; negatives: different corner types) to build corner embeddings and skill metrics.
- Unsupervised corner clustering: Cluster segments using curvature, slope, speed, lateral accel, and entry/exit speeds to discover corner archetypes and typical errors.
- Bayesian/GP models: Gaussian process for speed vs curvature with uncertainty; use to estimate safe upper bounds for speed targets and rank actionable vs risky insights. [R6][R8]
- Learning-to-rank: Rank candidate insights by expected time gain, confidence, and similarity to historically successful changes; labels from past improvement success.

**4) MVP Plan (GPS Speed + Distance + Heading + Lat/Lon)**
- Build a clean track map: Smooth lat/lon; compute heading vs distance; derive curvature and direction (CW/CCW) from sign of curvature.
- Estimate kinematics: Derive speed vs distance; estimate lateral acceleration as v^2 * curvature; estimate longitudinal accel from dv/dt.
- Proxies for brake/throttle: Brake proxy = sustained negative longitudinal accel above a threshold; throttle proxy = positive longitudinal accel when curvature is stable.
- Construct baseline: Use best-of-laps per segment; apply g-g envelope derived from observed accel scatter to cap aggressive sections.
- Produce quick insights: Identify top 5 segments with biggest feasible speed deltas; output entry/apex/exit adjustments with estimated time gain.

**5) Phase-2 Plan (Additional Channels: Acc, Rates, GPS Radius, Accuracy)**
- Improve dynamics: Use Inline/Lateral/Vertical Acc for better g-g envelope; use Roll/Pitch/Yaw and GPS Gyro/Radius to refine curvature and local attitude.
- Slope and camber effects: Use GPS slope and vertical accel to adjust effective normal load and speed targets.
- Confidence weighting tied to GPS quality: Down-weight segments with low Nsat, high PosAccuracy, or high SpdAccuracy. Example: weight = w_sat * w_pos * w_spd, with w_sat increasing with Nsat and w_pos/w_spd decreasing with their error magnitude.
- Error-aware smoothing: Apply sensor-fusion filters (e.g., complementary/UKF) to reduce GPS noise and stabilize derived curvature.
- Model calibration: Fit envelope per speed bin and per slope bin; update limits with rolling window to track grip changes.

**6) Evaluation Plan**
- Prediction validity: Compare predicted time gains against actual improvements on later laps or subsequent sessions; compute correlation and calibration error.
- Consistency checks: Verify that predicted gains are stable across multiple laps and not driven by GPS noise.
- Ablations: Compare physics-only vs skill-transfer vs hybrid; measure lap time error vs best-lap baseline.
- Practical usefulness: Trackside quick insights should be computable within minutes and show measurable improvements within a session.

**7) Integration Points with Existing Pipeline**
- Track + direction normalization: Persist track ID and CW/CCW label; maintain separate baselines per direction.
- Segment-level outputs: Add columns for predicted delta time, confidence, and recommended speed change at entry/apex/exit.
- Insights ranking: Rank by expected time gain * confidence; include caution flags for low GPS quality.
- Data products: Store virtual baseline lap, per-point deltas, and per-segment summaries for UI.

**8) References (Minimum-Lap-Time / GGV / Optimal Control)**
- [R1] "Near time-optimal control of racing vehicles" (Automatica, 1989). DOI: 10.1016/0005-1098(89)90052-6. Minimum-time racing framed as constrained optimal control.
- [R2] "Optimal control for a Formula One car with variable parameters" (Vehicle System Dynamics, 2014). DOI: 10.1080/00423114.2014.889315. Direct transcription and NLP for minimum-lap-time with set-up optimization.
- [R3] "Minimum time optimal control simulation of a GP2 race car" (Proc IMechE Part D, 2017). DOI: 10.1177/0954407017728158. Minimum-lap-time with a multibody model and validation vs real data.
- [R4] "Curved-ribbon-based track modelling for minimum lap-time optimisation" (Meccanica, 2021). DOI: 10.1007/s11012-021-01387-3. Track modeling, g-g maps, and 3D effects.
- [R5] "A free-trajectory quasi-steady-state optimal-control method for minimum lap-time of race vehicles" (Vehicle System Dynamics, 2019). DOI: 10.1080/00423114.2019.1608364. Uses g-g maps to solve minimum-lap-time with free trajectory.
- [R6] "The Tire-Force Ellipse (Friction Ellipse) and Tire Characteristics" (SAE, 2011). DOI: 10.4271/2011-01-0094. Combined braking/cornering force limits underpin g-g envelopes.
- [R7] "A Quasi-Steady-State Black Box Simulation Approach for the Generation of g-g-g-v Diagrams" (IEEE IV, 2025). DOI: 10.1109/IV64158.2025.11097491. Extends g-g to g-g-g-v and provides a generation method.
- [R8] "Impacts of g-g-v Constraints Formulations on Online Minimum-Time Vehicle Trajectory Planning" (IFAC-PapersOnLine, 2024). DOI: 10.1016/j.ifacol.2024.07.323. Discusses g-g-v constraints in minimum-time planning.

**9) Minimal User Questions (If Needed)**
- Do we have any pro or expert laps to use for skill-transfer, and are they the same vehicle class?
- Should the MVP prioritize on-track speed targets (quick) or a deeper optimal-control baseline (slow but rigorous)?
- Do we have a preferred segment schema (existing beacon markers vs auto-segmentation)?
