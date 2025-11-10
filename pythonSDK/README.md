# DJI Drone Control - Python SDK

A minimal Python library for DJI drone control via MQTT, with advanced PID-based position and attitude control.

## 🚀 Quick Start

### Run Position Control
```bash
# 1. Start the plane + yaw control
python control/main.py

# 2. Visualize the results
python control/visualize.py data/latest
```

### Run Yaw Control
```bash
# 1. Start yaw-only control
python control/yaw_main.py

# 2. Visualize the results
python control/visualize.py data/yaw/latest
```

## 📚 Documentation

**Complete documentation:** [`docs/README.md`](docs/README.md)

- **[Control Module Guide](docs/CONTROL_MODULE_GUIDE.md)** - Position & yaw control system
- **[Data Source Configuration](control/DATASOURCE_GUIDE.md)** - Configure VRPN/UWB/Drone data sources
- **[PID Tuning Guide](docs/PID_TUNING_GUIDE.md)** - How to tune PID parameters
- **[Data Logging](docs/DATA_LOGGING_README.md)** - Logging and visualization
- **[Mock Simulator](docs/MOCK_SIMULATOR_GUIDE.md)** - Test without hardware

## 🏗️ Project Structure

```
pythonSDK/
├── control/              # PID control system
│   ├── main.py          # Plane + Yaw control (disabled)
│   ├── plane_main.py    # Position control only
│   ├── yaw_main.py      # Yaw-only control
│   ├── datasource.py    # Data source abstraction (VRPN/UWB)
│   ├── visualize.py     # Data visualization (with PID components!)
│   ├── pid.py           # PID controller
│   ├── controller.py    # Control strategies
│   ├── logger.py        # Data logging
│   ├── config.py        # Configuration (incl. data sources)
│   └── DATASOURCE_GUIDE.md  # Data source configuration guide
├── djisdk/              # DJI Cloud API SDK
├── vrpn/                # VRPN motion capture client
├── uwb.py               # UWB positioning client (template)
├── utils/               # Utility scripts
└── docs/                # Documentation
```

## ⚙️ Features

### Control System
- ✅ XY plane position control
- ✅ Yaw angle control
- ✅ Multi-waypoint navigation
- ✅ PID with anti-windup
- ✅ Real-time data logging
- ✅ **PID component visualization** (P, I, D terms)
- ✅ "latest" directory for quick access
- ✅ **Flexible data sources** (VRPN/UWB for position, VRPN/Drone for yaw)

### DJI SDK
- ✅ Minimal design (2 core classes, ~150 lines)
- ✅ Pure function business layer
- ✅ 92% test coverage (42 unit tests)
- ✅ MQTT-based communication

### VRPN Integration
- ✅ Motion capture position feedback
- ✅ Quaternion to Euler conversion
- ✅ ZeroMQ-based communication

## 🔧 Configuration

Edit `control/config.py` to configure:

```python
# Data sources
POSITION_SOURCE = 'vrpn'  # 'vrpn' or 'uwb'
YAW_SOURCE = 'vrpn'       # 'vrpn' or 'drone'

# PID parameters
KP_XY = 150.0   # Position control
KD_XY = 200.0
KP_YAW = 3.0    # Yaw control
KD_YAW = 50.0

# Control frequency
CONTROL_FREQUENCY = 50  # Hz

# Connection settings
VRPN_DEVICE = "DJI_Mini4Pro"
UWB_DEVICE = "uwb://192.168.31.200:8888/drone1"
MQTT_CONFIG = {...}
```

**See [Data Source Configuration Guide](control/DATASOURCE_GUIDE.md) for detailed setup.**

## 📊 Data Visualization

All control tests automatically log data with:
- Position/angle tracking
- Control outputs (stick values)
- **PID components** (P, I, D terms)
- Error metrics and statistics

Visualize with interactive Plotly charts:
```bash
python control/visualize.py data/latest
```

Features:
- Multiple synchronized subplots
- PID component analysis (new!)
- Statistical summaries
- Auto-detection of data type

## 🧪 Testing Without Hardware

Use the mock simulator:
```bash
USE_MOCK_DRONE=1 python control/main.py
```

## 📖 Development Principles

This project follows **"Good Taste"** principles:
- ✅ Simple code that works > Complex code that "handles edge cases"
- ✅ No unnecessary abstraction
- ✅ Direct implementation over design patterns
- ✅ Pure functions where possible

See [`CLAUDE.md`](CLAUDE.md) for detailed guidelines.

## 🛠️ Common Commands

```bash
# Position control
python control/main.py

# Yaw control
python control/yaw_main.py

# Visualize data (auto-detects type)
python control/visualize.py data/latest
python control/visualize.py data/yaw/latest

# Monitor MQTT traffic
python utils/mqtt_sniffer.py

# Test VRPN connection
python vrpn_test.py

# Run SDK unit tests
cd djisdk && python tests/run_tests.py
```

## 📁 Data Directory Structure

```
data/
├── latest/                    # Latest plane+yaw control log (auto-updated)
│   ├── control_data.csv      # Full data with PID components
│   └── plane_yaw_analysis.html
├── yaw/
│   └── latest/               # Latest yaw-only log (auto-updated)
│       ├── yaw_control_data.csv
│       └── yaw_only_analysis.html
├── 20241030_103045/          # Timestamped logs
└── yaw/20241030_102030/
```

## 🆘 Troubleshooting

### VRPN connection fails
```bash
# Test VRPN connection
python vrpn_test.py
# Check device name in config.py
```

### MQTT connection fails
```bash
# Monitor MQTT traffic
python utils/mqtt_sniffer.py
```

### Control oscillation
- Reduce Kp (proportional gain)
- Increase Kd (derivative gain)
- See [PID Tuning Guide](docs/PID_TUNING_GUIDE.md)

### Inspect PID behavior
```bash
# Visualize PID components
python control/visualize.py data/latest
# Look at the PID components subplot
```

## 📝 Recent Updates

### 2024-11-10: Flexible Data Source Configuration
- ✅ Support for multiple position data sources (VRPN, UWB)
- ✅ Support for multiple yaw data sources (VRPN, Drone attitude)
- ✅ Unified data source abstraction layer
- ✅ UWB client template for custom positioning systems
- ✅ Comprehensive data source configuration guide

### 2024-10-30: PID Component Logging & Visualization
- ✅ PID controller now returns P, I, D components
- ✅ Logger records all PID components to CSV
- ✅ Visualizer shows PID component subplots
- ✅ "latest" directory mechanism for quick access
- ✅ Unified documentation in docs/

### 2024-10-29: Control Module Refactor
- ✅ Modular control package structure
- ✅ Separate plane and yaw control modes
- ✅ Unified visualization tool

---

**For complete documentation, see [`docs/README.md`](docs/README.md)**
