# Mission Scripts

This directory contains mission scripts for DJI drone control.

## Available Missions

- **takeoff.py** - Automatic takeoff to specified height
- **flytoSingle.py** - Fly to a single GPS point and return
- **trajectory.py** - Multi-drone trajectory flight
- **repeatTraj.py** - Loop between two GPS waypoints

## Usage

All mission scripts can be executed from the root directory (`pythonSDK/`) using either method:

### Method 1: Direct execution (Recommended)

```bash
# From pythonSDK/ directory
python3 mission/takeoff.py
python3 mission/flytoSingle.py
python3 mission/trajectory.py
python3 mission/repeatTraj.py
```

### Method 2: Using Python module syntax

```bash
# From pythonSDK/ directory
python3 -m mission.takeoff
python3 -m mission.flytoSingle
python3 -m mission.trajectory
python3 -m mission.repeatTraj
```

Both methods work correctly - the scripts automatically add the parent directory to Python's module search path.

## Configuration

Each mission script contains a configuration section at the top where you can adjust:
- UAV serial numbers and callsigns
- MQTT broker settings
- Flight parameters (height, speed, etc.)
- Mission-specific settings

## Dependencies

All missions depend on the `djisdk` package located in the parent directory. Make sure you have installed the required dependencies:

```bash
pip install -r requirements.txt
```

## Notes

- All imports work correctly from the root directory (`pythonSDK/`)
- No need to modify `PYTHONPATH` or change directories
- Configuration is done within each mission file
