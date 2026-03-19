# Grip Metrics for Motorcycle Coaching Insights

## Executive Summary

This research analyzes the best metrics to quantify grip usage from AiM Solo 2 GPS-only data for rider coaching. The primary recommendation is **Combined G-Force (friction circle) analysis** supplemented by **grip budget utilization** and **roll angle estimation** for comprehensive coaching insights.

## Available Data Channels

From AiM Solo 2 GPS-only configuration:
- **GPS LatAcc** (g): Lateral acceleration
- **GPS LonAcc** (g): Longitudinal acceleration
- **GPS Speed** (km/h): Vehicle speed
- **GPS Heading** (deg): Direction heading
- **RollRate** (deg/s): Roll rate around longitudinal axis
- **PitchRate** (deg/s): Pitch rate around lateral axis
- **YawRate** (deg/s): Yaw rate around vertical axis

## 1. Lateral G vs Combined G Analysis

### Lateral G Only (Traditional Approach)
- **Pros**: Simple to understand and visualize
- **Cons**: Ignores braking/acceleration forces, incomplete picture
- **Use Case**: Basic cornering speed analysis

### Combined G Force (Recommended)
The **friction circle** approach provides complete grip utilization:

```python
combined_g = sqrt(lat_acc² + lon_acc²)
grip_utilization = combined_g / max_available_grip
```

**Why Combined G is Superior:**
- Represents total tire friction demand
- Accounts for trail braking and drive-out scenarios
- Shows true grip budget utilization
- Enables friction circle visualization
- Better identifies grip limit approaches

## 2. Maximum Lateral G for R6 on Race Tires

### Expected Performance Ranges

**R6 on DOT Race Tires (Dunlop Q4, Pirelli SC, etc.):**
- **Peak Lateral G**: 1.4-1.6g
- **Sustainable Cornering**: 1.2-1.4g
- **Trail Braking Combined**: 1.3-1.5g

**R6 on Slicks (Pirelli SC1/SC2):**
- **Peak Lateral G**: 1.6-1.8g
- **Sustainable Cornering**: 1.4-1.6g
- **Combined Braking+Turning**: 1.5-1.7g

**Factors Affecting Limits:**
- Track temperature (optimal 80-120°F surface)
- Tire warming and pressure
- Track surface quality
- Rider skill level
- Bike setup (suspension, geometry)

### Practical Thresholds
```python
# Conservative coaching thresholds for R6 on race tires
AMATEUR_LIMIT = 1.2  # 85% of ultimate grip
INTERMEDIATE_LIMIT = 1.3  # 90% of ultimate grip
ADVANCED_LIMIT = 1.4  # 95% of ultimate grip
ABSOLUTE_LIMIT = 1.5  # 100% theoretical maximum
```

## 3. Braking vs Acceleration vs Cornering Grip Distribution

### Grip Budget Allocation (Typical Race Pace)

**Corner Entry (Trail Braking Phase):**
- Longitudinal: 0.8-1.2g braking
- Lateral: 0.4-0.8g turning
- Combined: 1.0-1.4g

**Mid-Corner (Pure Cornering):**
- Longitudinal: 0.0-0.2g (maintenance throttle)
- Lateral: 1.2-1.5g turning
- Combined: 1.2-1.5g

**Corner Exit (Acceleration Phase):**
- Longitudinal: 0.4-0.8g acceleration
- Lateral: 0.6-1.0g turning
- Combined: 0.8-1.3g

### Phase Detection Algorithm
```python
def detect_corner_phase(lon_acc, lat_acc, speed_delta):
    combined_g = sqrt(lon_acc**2 + lat_acc**2)

    if lon_acc < -0.3 and abs(lat_acc) > 0.4:
        return "trail_braking", combined_g
    elif abs(lon_acc) < 0.2 and abs(lat_acc) > 0.8:
        return "pure_cornering", combined_g
    elif lon_acc > 0.2 and abs(lat_acc) > 0.4:
        return "drive_out", combined_g
    else:
        return "straight", combined_g
```

## 4. AiM and Telemetry Analysis Frameworks

### Industry Standard Metrics

**AiM Race Studio Analysis:**
1. **G-G Diagram**: Friction circle plotting
2. **Grip Utilization**: Combined G vs theoretical maximum
3. **Corner Analysis**: Entry/apex/exit grip usage
4. **Lap Overlays**: Compare grip traces between laps

**MoTeC i2 Pro Approach:**
1. **Combined Lateral Forces**: Vector sum analysis
2. **Grip Histogram**: Distribution of grip usage levels
3. **Phase Analysis**: Corner entry/mid/exit grip allocation

**Telemetry Analysis Best Practices:**
- Always normalize to vehicle-specific grip limits
- Account for environmental factors (temperature, surface)
- Use rolling averages to smooth GPS noise
- Validate against known performance benchmarks

### Professional Frameworks

**Claude Smith (Going Faster! methodology):**
- Focus on minimum cornering radius for given speed
- Analyze grip margin at corner exit
- Emphasize consistent grip utilization patterns

**Skip Barber Racing School:**
- Emphasize smooth application progression
- Avoid abrupt grip demand changes
- Maximize grip usage without exceeding limits

## 5. Roll Rate and Yaw Rate Analysis

### Roll Angle Estimation
Since AiM Solo 2 doesn't provide direct roll angle, estimate from roll rate:

```python
def estimate_roll_angle(roll_rate, dt=0.05):
    """Integrate roll rate to estimate lean angle"""
    roll_angle = 0
    angles = []

    for rate in roll_rate:
        roll_angle += rate * dt
        angles.append(roll_angle)

    # Apply drift correction using straight-line sections
    return drift_correct(angles)

def theoretical_lean_angle(speed_ms, lat_acc_g):
    """Physics-based lean angle calculation"""
    return atan2(lat_acc_g * 9.81, speed_ms**2 / radius)
```

### Yaw Rate Analysis
Yaw rate indicates rotation rate and path curvature:

```python
def corner_rotation_rate(yaw_rate, speed_ms):
    """Convert yaw rate to path curvature"""
    radius = speed_ms / abs(yaw_rate) if yaw_rate != 0 else float('inf')
    return radius

def smooth_cornering_metric(yaw_rate, roll_rate):
    """Analyze coordination between yaw and roll"""
    return abs(yaw_rate) / (abs(roll_rate) + 0.1)  # Avoid division by zero
```

### Body Motion Insights

**Roll Rate Applications:**
- Estimate lean angle for visual coaching feedback
- Detect aggressive vs smooth direction changes
- Identify setup issues (slow steering response)

**Yaw Rate Applications:**
- Calculate cornering radius and path efficiency
- Detect over/under-steering tendencies
- Analyze turn-in rate and corner entry technique

## 6. Recommended Grip Metrics for Coaching

### Primary Metrics (Core KPIs)

**1. Combined G-Force Utilization**
```python
def combined_grip_usage(lat_acc, lon_acc, max_grip=1.4):
    combined_g = sqrt(lat_acc**2 + lon_acc**2)
    utilization = combined_g / max_grip * 100
    return min(utilization, 100)  # Cap at 100%
```

**2. Corner Phase Grip Distribution**
```python
def corner_grip_analysis(lap_data):
    phases = ['entry', 'mid', 'exit']
    grip_by_phase = {}

    for phase in phases:
        phase_data = extract_phase_data(lap_data, phase)
        grip_by_phase[phase] = {
            'avg_combined_g': mean(phase_data['combined_g']),
            'max_combined_g': max(phase_data['combined_g']),
            'grip_utilization': mean(phase_data['utilization']),
            'consistency': std(phase_data['combined_g'])
        }

    return grip_by_phase
```

**3. Grip Margin Safety Factor**
```python
def grip_margin(combined_g, max_available=1.4):
    margin = max_available - combined_g
    safety_factor = margin / max_available * 100
    return safety_factor
```

### Secondary Metrics (Detailed Analysis)

**4. Smoothness Index**
```python
def grip_smoothness(combined_g_trace):
    """Lower values indicate smoother grip application"""
    grip_delta = diff(combined_g_trace)
    return std(grip_delta) * 1000  # Scale for readability
```

**5. Trail Braking Efficiency**
```python
def trail_braking_score(corner_data):
    """Analyze how well combined braking+turning is executed"""
    entry_phase = corner_data['entry']

    ideal_curve = friction_circle_ideal(entry_phase['speed'])
    actual_trace = zip(entry_phase['lon_acc'], entry_phase['lat_acc'])

    efficiency = 0
    for lon_g, lat_g in actual_trace:
        actual_combined = sqrt(lon_g**2 + lat_g**2)
        max_possible = interpolate_friction_circle(abs(lat_g), ideal_curve)
        efficiency += actual_combined / max_possible

    return efficiency / len(actual_trace) * 100
```

**6. Roll Angle Utilization**
```python
def lean_angle_usage(estimated_roll, max_lean=50):
    """Analyze lean angle relative to bike limits"""
    peak_lean = max(abs(estimated_roll))
    utilization = peak_lean / max_lean * 100
    return min(utilization, 100)
```

### Visualization Recommendations

**Grip Circle Plot:**
```python
def plot_friction_circle(lat_acc, lon_acc, max_grip=1.4):
    # Plot actual grip usage points
    # Overlay theoretical maximum circle
    # Color-code by corner phase or speed
    # Show grip utilization percentage
```

**Grip Utilization Heatmap:**
```python
def plot_track_grip_heatmap(track_position, grip_utilization):
    # Map grip usage to track position
    # Color intensity represents grip level
    # Identify high/low grip sections
    # Compare multiple laps
```

## 7. Implementation Priority

### Phase 1: Core Metrics (Immediate)
1. **Combined G-Force calculation** (`sqrt(lat_acc² + lon_acc²)`)
2. **Grip utilization percentage** (combined_g / max_grip * 100)
3. **Basic friction circle plotting**

### Phase 2: Enhanced Analysis (2-4 weeks)
1. **Corner phase detection and analysis**
2. **Roll angle estimation from roll rate**
3. **Grip margin and safety factor calculations**

### Phase 3: Advanced Coaching (1-2 months)
1. **Trail braking efficiency scoring**
2. **Grip smoothness and consistency metrics**
3. **Comparative lap analysis with grip overlays**

## 8. Validation and Calibration

### Data Quality Checks
```python
def validate_grip_data(lat_acc, lon_acc, speed):
    # Check for GPS accuracy issues
    if any(abs(g) > 2.0 for g in lat_acc + lon_acc):
        warn("Unrealistic G-force readings detected")

    # Validate physics consistency
    for i, (la, lo, v) in enumerate(zip(lat_acc, lon_acc, speed)):
        centripetal_check = v**2 / (abs(la) * 9.81) if la != 0 else float('inf')
        if centripetal_check < 10:  # Unrealistically tight radius
            warn(f"Physics inconsistency at sample {i}")
```

### Benchmark Validation
- Compare calculated grip levels against known rider capabilities
- Validate maximum G-force readings against bike/tire specifications
- Cross-check roll angle estimates with video analysis when available

## 9. Final Recommendations

### Primary Coaching Metric: Combined G-Force Analysis
**Use combined G-force (friction circle) as the primary metric because:**
- Represents complete tire grip utilization
- Enables proper trail braking analysis
- Shows true performance potential
- Industry standard for professional analysis
- Directly applicable to rider coaching

### Implementation Formula
```python
# Primary coaching metric
def primary_grip_metric(lat_acc, lon_acc, bike_limit=1.4):
    combined_g = sqrt(lat_acc**2 + lon_acc**2)
    utilization_percent = (combined_g / bike_limit) * 100

    # Coaching zones
    if utilization_percent < 70:
        zone = "conservative"
    elif utilization_percent < 85:
        zone = "building"
    elif utilization_percent < 95:
        zone = "pushing"
    else:
        zone = "limit"

    return {
        'combined_g': combined_g,
        'utilization_percent': min(utilization_percent, 100),
        'coaching_zone': zone,
        'margin_g': max(0, bike_limit - combined_g)
    }
```

### Supporting Metrics
1. **Corner phase grip distribution** (entry/mid/exit analysis)
2. **Grip consistency** (smoothness of application)
3. **Roll angle estimation** (visual feedback for riders)
4. **Safety margin** (distance from grip limit)

This comprehensive approach provides actionable coaching insights while remaining practical for implementation with GPS-only data from the AiM Solo 2 system.