# 📚 Documentation Index

Complete documentation for the DJI Drone Control Python SDK project.

## 🚀 Quick Start

### Control System
- **[Control Module Guide](CONTROL_MODULE_GUIDE.md)** - Complete guide to the control system
  - Plane position control (X, Y)
  - Yaw angle control
  - PID tuning and visualization
  - Data logging and analysis

### Core Components
- **[PID Tuning Guide](PID_TUNING_GUIDE.md)** - How to tune PID parameters for optimal performance
- **[Data Logging](DATA_LOGGING_README.md)** - Data logging and visualization tools

### Development Tools
- **[Mock Simulator](MOCK_SIMULATOR_GUIDE.md)** - Test control algorithms without real hardware
- **[MQTT Sniffer](mqtt_sniffer_refactor.md)** - Monitor MQTT traffic for debugging
- **[Python Import Guide](PYTHON_IMPORT_GUIDE.md)** - Module import structure and best practices

### UI & Interaction
- **[Joystick UI Design](JOYSTICK_UI_DESIGN.md)** - Web-based joystick control interface
- **[Live Tool Guide](live_tool_guide.md)** - Real-time monitoring and control tools

---

## 📂 Directory Structure

```
pythonSDK/
├── control/              # PID control system (NEW!)
│   ├── main.py          # Plane + Yaw control
│   ├── yaw_main.py      # Yaw-only control
│   ├── pid.py           # PID controller base class
│   ├── controller.py    # Control strategies
│   ├── logger.py        # Data logging
│   └── visualize.py     # Data visualization
├── djisdk/              # DJI Cloud API SDK
├── vrpn/                # VRPN motion capture client
├── utils/               # Utility scripts
└── docs/                # Documentation (you are here)
```

---

## 🎯 Common Tasks

### 1. Run Position Control Test
```bash
# Plane position + yaw angle control
python control/main.py

# Plot results
python control/visualize.py data/latest
```

### 2. Run Yaw Control Test
```bash
# Yaw angle only control
python control/yaw_main.py

# Plot results
python control/visualize.py data/yaw/latest
```

### 3. Monitor MQTT Traffic
```bash
python utils/mqtt_sniffer.py
```

### 4. Test Without Hardware
```bash
# Use mock simulator
USE_MOCK_DRONE=1 python control/main.py
```

---

## 📊 Control System Overview

### Control Modes

1. **Plane + Yaw Control** (`control/main.py`)
   - Flies through waypoints in XY plane
   - Maintains target yaw angle
   - Full 3-axis control (roll, pitch, yaw)
   - Data logged to `data/<timestamp>/`

2. **Yaw-Only Control** (`control/yaw_main.py`)
   - Rotates to target angles
   - No position control
   - Useful for PID tuning
   - Data logged to `data/yaw/<timestamp>/`

### PID Parameters

Located in `control/config.py`:

```python
# Position control (X, Y)
KP_XY = 150.0
KI_XY = 0.0
KD_XY = 200.0

# Yaw control
KP_YAW = 3.0
KI_YAW = 0.0
KD_YAW = 50.0
```

### Data Visualization

All logged data includes:
- Position/angle tracking
- Control outputs (stick values)
- **PID components** (P, I, D terms) ← NEW!
- Error metrics

Visualization features:
- Interactive Plotly charts
- Multiple synchronized subplots
- PID component analysis
- Statistical summaries

---

## 🔧 Configuration Files

### `control/config.py`
- PID parameters
- Control frequency
- Arrival thresholds
- MQTT connection settings
- VRPN device name

### `CLAUDE.md` (root)
- Development guidelines
- Architecture principles
- Code style rules

---

## 🧪 Testing & Debugging

### Logging System
- Automatic timestamped directories
- CSV format data files
- `latest/` always points to most recent log
- Full PID component logging

### Visualization
```bash
# Auto-detect data type and visualize
python control/visualize.py data/20241030_103045

# Or use latest
python control/visualize.py data/latest          # Plane control
python control/visualize.py data/yaw/latest      # Yaw control
```

### Debug Output
- Rich-formatted console output
- Real-time status updates
- Color-coded messages
- Detailed error reporting

---

## 📖 Related Documentation

### External Modules
- **djisdk**: See `djisdk/README.md` for SDK architecture
- **vrpn**: See `vrpn/README.md` for VRPN client usage

### Parent Project
- Main project CLAUDE.md: `/Users/groovewjh/Project/work/SYSU/Volition-DJI/CLAUDE.md`

---

## 🆘 Troubleshooting

### Common Issues

1. **VRPN connection fails**
   - Check device name in `control/config.py`
   - Verify VRPN server is running
   - Test with `python vrpn_test.py`

2. **MQTT connection fails**
   - Verify network connectivity
   - Check MQTT broker address/port
   - Use `utils/mqtt_sniffer.py` to test

3. **Control oscillation**
   - Reduce Kp (proportional gain)
   - Increase Kd (derivative gain)
   - Disable Ki if oscillating
   - See [PID Tuning Guide](PID_TUNING_GUIDE.md)

4. **Drone drifts away**
   - Check coordinate system mapping
   - Verify VRPN position data
   - Inspect PID component plots

---

## 📝 Documentation Style

All documentation follows these principles:
- **Simple and direct** - no unnecessary complexity
- **Code examples** - show, don't just tell
- **Practical focus** - how to use, not just what it is
- **Up-to-date** - reflects current codebase

---

## 🔄 Recent Updates

### 2024-10-30: PID Component Logging
- Enhanced PID controller to return P, I, D terms
- Updated logger to record all PID components
- Added PID visualization subplots
- Implemented "latest" directory mechanism

### 2024-10-29: Control Module Refactor
- Unified control package structure
- Separated plane and yaw control modes
- Modular PID controllers
- Unified visualization tool

---

## 📬 Contributing

When adding new features or documentation:
1. Keep it simple - follow CLAUDE.md principles
2. Add examples and usage instructions
3. Update this index
4. Test with real hardware when possible

---

**Last Updated**: 2024-10-30
**Maintainer**: System integration team
