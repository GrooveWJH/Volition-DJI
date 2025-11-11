# UWB Real-time Web Visualization Guide

## Quick Start

```bash
# Run the web visualization server
python uwb/getdata_smoothed_web.py

# Open browser to:
http://localhost:8050
```

## System Overview

This visualization system provides real-time monitoring of UWB positioning data with automatic smoothing.

### Features

✅ **Real-time 2D Trajectory Display** (X-Y plane)
- Raw data shown as scatter points (red, semi-transparent)
- Smoothed data shown as connected line (green)
- Current position marked with blue star

✅ **Time Series Analysis**
- Separate plots for X and Y coordinates over time
- Raw vs smoothed data comparison
- Relative time display (seconds since start)

✅ **Live Statistics**
- Frame count and voltage monitoring
- Current position display (raw and smoothed)
- Standard deviation (σ) in millimeters
- Per-node data tracking

✅ **Multi-node Support**
- Dropdown selector for different TAG nodes
- Independent smoothing per node
- Up to 500 historical points per node

## Smoothing Algorithm

**Two-Level Cascade Filter:**

1. **Outlier Rejection** (3σ principle)
   - X-axis threshold: 85.8mm
   - Y-axis threshold: 38.7mm

2. **Moving Average Filter**
   - X-axis window: 5 samples (~50ms delay)
   - Y-axis window: 3 samples (~30ms delay)

### Performance Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| X std dev | 28.6mm | ~12mm | 58% ↓ |
| Y std dev | 12.9mm | ~7mm | 46% ↓ |
| Outliers | 1.5% | <0.1% | 93% ↓ |

## Configuration

### Serial Port Settings

Edit `SERIAL_PORT` and `BAUDRATE` in `getdata_smoothed_web.py`:

```python
SERIAL_PORT = "/dev/ttyACM0"  # Change if needed
BAUDRATE = 1500000
```

### Display Settings

```python
MAX_POINTS = 500           # Historical points to display
UPDATE_INTERVAL_MS = 100   # Refresh rate (milliseconds)
```

### Filter Parameters

```python
# X-axis filter
FILTER_WINDOW_X = 5         # Moving average window
OUTLIER_THRESHOLD_X = 0.085 # 85.8mm threshold

# Y-axis filter
FILTER_WINDOW_Y = 3         # Moving average window
OUTLIER_THRESHOLD_Y = 0.039 # 38.7mm threshold
```

## Troubleshooting

### Port Permission Error

```bash
sudo chmod 666 /dev/ttyACM0
# Or add user to dialout group:
sudo usermod -a -G dialout $USER
# Then logout/login
```

### Port Already in Use

```bash
# Find process using port 8050
lsof -i :8050
# Kill if needed
kill -9 <PID>
```

### No Data Appearing

1. Check serial connection: `ls -l /dev/ttyACM*`
2. Verify baudrate matches UWB device (1500000)
3. Check console output for error messages

### Dependencies Missing

```bash
pip install paho-mqtt dash plotly numpy
```

## File Structure

```
uwb/
├── getdata_smoothed_web.py      # Web visualization (this file)
├── getdata_smoothed.py          # Terminal-based version
├── statistics.py                # Data collection tool
├── SMOOTHING_ALGORITHM.md       # Algorithm documentation
└── README_WEB_VIS.md           # This guide

uwb_statistics/
├── analysis_20251109_194600.md  # Statistical analysis report
├── raw_data_20251109_194600.csv # Raw measurement data
└── statistics_20251109_194600.csv # Summary statistics
```

## Technical Details

### Data Flow

```
Serial Port → Parser → Outlier Filter → Moving Average → Web Display
     ↓                    ↓                   ↓              ↓
  896 bytes          Valid check         Smoothing       Plotly
  @ 100Hz           (3σ principle)      (SMA filter)    Dashboard
```

### Thread Safety

- Serial reader runs in background daemon thread
- `DataStore` class uses threading locks for safe concurrent access
- Dash callbacks read data atomically

### Memory Management

- Fixed-size deques (maxlen=500) prevent unbounded growth
- Old data automatically evicted (FIFO)
- Per-node memory: ~180 bytes

## Related Documentation

- **Algorithm Details**: See `SMOOTHING_ALGORITHM.md` for mathematical foundations
- **Statistical Analysis**: See `uwb_statistics/analysis_20251109_194600.md` for performance metrics
- **Original Implementation**: See `getdata.py` for raw data protocol

## Performance Tips

1. **Reduce update rate** if browser feels sluggish:
   ```python
   UPDATE_INTERVAL_MS = 200  # From 100ms to 200ms
   ```

2. **Decrease history size** for lower memory usage:
   ```python
   MAX_POINTS = 200  # From 500 to 200
   ```

3. **Run headless** for data logging without browser:
   ```python
   # Comment out: app.run_server(...)
   # Serial reader will continue running
   ```

## Example Usage Scenarios

### 1. Real-time Position Monitoring
- Monitor drone/robot position in real-time
- Visualize movement patterns
- Detect anomalies (sudden jumps)

### 2. Filter Parameter Tuning
- Adjust `FILTER_WINDOW_X/Y` to balance smoothness vs lag
- Modify `OUTLIER_THRESHOLD_X/Y` for different noise levels
- Observe results immediately in web UI

### 3. Multi-device Tracking
- Select different nodes from dropdown
- Compare behavior across multiple TAG devices
- Identify problematic hardware

### 4. Data Quality Assessment
- Monitor standard deviation over time
- Check for drift or systematic errors
- Validate UWB anchor placement

---

**Last Updated**: 2025-11-09
**Version**: 1.0
**Author**: UWB Development Team
