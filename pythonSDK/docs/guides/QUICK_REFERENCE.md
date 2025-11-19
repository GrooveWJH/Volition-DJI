# 🎯 Quick Reference Guide

## What Files to Run?

### 1. Plane Position Control (X, Y plane + Yaw)
```bash
# Run control (from pythonSDK directory)
python control/main.py

# Plot results (latest log)
python control/visualize.py data/latest

# Plot specific log
python control/visualize.py data/20241030_103045
```

**Important**: Always run from the `pythonSDK` directory!

**What it does:**
- Flies through waypoints in XY plane
- Controls yaw angle
- Logs data to `data/<timestamp>/control_data.csv`
- Auto-copies to `data/latest/` when finished

### 2. Yaw-Only Control (Rotation only)
```bash
# Run control (from pythonSDK directory)
python control/yaw_main.py

# Plot results (latest log)
python control/visualize.py data/yaw/latest

# Plot specific log
python control/visualize.py data/yaw/20241030_102030
```

**Important**: Always run from the `pythonSDK` directory!

**What it does:**
- Rotates to target angles
- No position control
- Logs data to `data/yaw/<timestamp>/yaw_control_data.csv`
- Auto-copies to `data/yaw/latest/` when finished

---

## 📊 What Gets Plotted?

### Plane Position Control Plots (4 rows x 2 columns)

**Row 1: Position Tracking**
- Left: X axis tracking (target vs current)
- Right: Y axis tracking (target vs current)

**Row 2: Yaw & Distance**
- Left: Yaw angle tracking (target vs current)
- Right: Distance error over time

**Row 3: Stick Outputs**
- Left: Roll & Pitch stick values
- Right: Yaw stick values

**Row 4: PID Components** ⭐ NEW!
- Left: X-axis PID (P, I, D terms)
- Right: Y-axis PID (P, I, D terms)

### Yaw-Only Control Plots (3 rows x 1 column)

**Row 1: Yaw Tracking**
- Yaw angle tracking (target vs current)

**Row 2: Yaw Stick Output**
- Yaw stick values with neutral line

**Row 3: PID Components** ⭐ NEW!
- Yaw PID (P, I, D terms)

---

## 📂 Data Logging

### What Gets Logged?

#### Plane Control (`control_data.csv`):
```csv
timestamp,target_x,target_y,target_yaw,
current_x,current_y,current_yaw,
error_x,error_y,error_yaw,distance,
roll_offset,pitch_offset,yaw_offset,
roll_absolute,pitch_absolute,yaw_absolute,
waypoint_index,
x_pid_p,x_pid_i,x_pid_d,      ← NEW!
y_pid_p,y_pid_i,y_pid_d,      ← NEW!
yaw_pid_p,yaw_pid_i,yaw_pid_d ← NEW!
```

#### Yaw Control (`yaw_control_data.csv`):
```csv
timestamp,target_yaw,current_yaw,error_yaw,
yaw_offset,yaw_absolute,target_index,
yaw_pid_p,yaw_pid_i,yaw_pid_d  ← NEW!
```

### "Latest" Directory Feature ⭐ NEW!

Every test run automatically:
1. Creates timestamped directory: `data/20241030_103045/`
2. Copies entire directory to: `data/latest/`
3. Overwrites old `latest/` directory

**Why?** Quick access without remembering timestamps!

```bash
# Always plot the most recent test
python control/visualize.py data/latest
python control/visualize.py data/yaw/latest

# No need to remember: data/20241030_103045/
```

---

## 🔧 Configuration

All settings in `control/config.py`:

```python
# PID Parameters
KP_XY = 150.0      # Position control proportional
KI_XY = 0.0        # Position control integral
KD_XY = 200.0      # Position control derivative

KP_YAW = 3.0       # Yaw control proportional
KI_YAW = 0.0       # Yaw control integral
KD_YAW = 50.0      # Yaw control derivative

# Waypoints (for plane control)
WAYPOINTS = [
    (0.0, 0.0),
    (1.0, 0.0),
    (1.0, 1.0),
    (0.0, 1.0)
]

# Target yaws (for yaw-only control)
TARGET_YAWS = [0, 90, 180, -90]

# Control frequency
CONTROL_FREQUENCY = 50  # Hz

# Arrival thresholds
TOLERANCE_XY = 0.05        # meters (5cm)
TOLERANCE_YAW = 3.0        # degrees
ARRIVAL_STABLE_TIME = 1.5  # seconds
```

---

## 📈 Understanding PID Component Plots

### What Each Term Means:

**P (Proportional) - Red Line**
- Responds to current error
- Large when far from target
- Zero when at target

**I (Integral) - Green Line**
- Accumulates error over time
- Eliminates steady-state error
- Can cause overshoot if too high

**D (Derivative) - Blue Line**
- Responds to rate of change
- Provides damping
- Prevents overshoot and oscillation

### Good PID Behavior:

✅ **Well-tuned:**
- P term dominates initially (large error)
- D term provides smooth approach
- I term stays near zero (if no steady-state error)
- All terms converge to zero at target

❌ **Poorly-tuned:**
- P term oscillates back and forth
- I term keeps growing (windup)
- D term spikes frequently (too reactive)

---

## 🎓 Workflow Example

### Tuning Yaw Control

1. **Run test:**
   ```bash
   python control/yaw_main.py
   ```

2. **Let it complete one full rotation**
   - Press Enter at each waypoint
   - Press Ctrl+C when done

3. **Visualize results:**
   ```bash
   python control/visualize.py data/yaw/latest
   ```

4. **Analyze PID components:**
   - Look at Row 3 (PID subplot)
   - Check if P term oscillates → reduce Kp
   - Check if D term too spiky → reduce Kd
   - Check if I term grows → disable Ki or reduce

5. **Adjust parameters in `config.py`:**
   ```python
   KP_YAW = 3.0   # Reduce if oscillating
   KI_YAW = 0.0   # Keep disabled if stable
   KD_YAW = 50.0  # Increase for more damping
   ```

6. **Repeat until satisfied**

---

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| **"No data in latest/"** | Run a control test first |
| **Plot shows no PID components** | Old data format, run new test |
| **Oscillation** | Reduce Kp, increase Kd |
| **Slow response** | Increase Kp, reduce Kd |
| **Overshoot** | Increase Kd, reduce Kp |
| **Steady-state error** | Enable Ki (set to 0.1-0.5) |

---

## 📚 More Information

- **Full documentation:** [`docs/README.md`](docs/README.md)
- **PID tuning guide:** [`docs/PID_TUNING_GUIDE.md`](docs/PID_TUNING_GUIDE.md)
- **Control module details:** [`docs/CONTROL_MODULE_GUIDE.md`](docs/CONTROL_MODULE_GUIDE.md)

---

**Last Updated:** 2024-10-30
