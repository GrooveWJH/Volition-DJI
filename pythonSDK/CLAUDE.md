# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL DEVELOPMENT PRINCIPLES ⚠️

### 🚨 **AVOID COMPLEXITY AT ALL COSTS!** 🚨

**THIS IS THE MOST IMPORTANT RULE - COMPLEXITY IS THE ENEMY OF FUNCTIONALITY!**

- **NEVER add features that weren't explicitly requested**
- **NEVER create "robust" or "enterprise-grade" solutions**
- **ALWAYS choose the simplest working solution**
- **ALWAYS prefer direct implementation over abstraction**

**Remember: Simple code that works > Complex code that "handles edge cases"**

This library follows **Linus Torvalds' "Good Taste" principle**: eliminate special cases through elegant design, not by adding complexity.

## Project Overview

**DJI Drone Control System** - A complete Python-based drone control system with three major components:

1. **djisdk/** - Minimal MQTT-based DJI Cloud API SDK (2 core classes, ~150 lines)
2. **control/** - PID-based position and yaw control system with data logging
3. **control_mpc/** - Model Predictive Control (MPC) for 200ms delay compensation
4. **vrpn/** - Motion capture integration via VRPN protocol

### Design Philosophy
- **Only 2 core classes** (~150 lines total)
- **Pure function business layer** (stateless services)
- **Zero code duplication** (`_call_service()` wrapper pattern)
- **No design patterns** (no factory, strategy, observer, etc.)
- **Direct flow** (no callbacks, no state machines)

### Architecture at a Glance
```
Core Layer (2 classes, 150 lines)
  ├── MQTTClient      - Connection + Future-based async responses
  └── ServiceCaller   - Sync wrapper that blocks on Futures

Business Layer (pure functions)
  ├── commands.py     - ALL DJI services in ONE file (167 lines)
  └── heartbeat.py    - Background thread (special case, 89 lines)
```

**Key Insight**: 4 separate service files (478 lines, 90% duplication) → 1 unified file (167 lines, 0% duplication)

## 🔄 CODE REUSE PRINCIPLES - CRITICAL!

### djisdk as a Reusable Library

**MOST IMPORTANT**: `djisdk/` is NOT just a module in this project - it's a **standalone, reusable library** used across multiple applications!

### Current Usage Scenarios

The djisdk library is actively reused in:

1. **control/** - PID control system imports djisdk for drone communication
2. **control_mpc/** - MPC controller imports djisdk for drone communication
3. **main.py** - Display system imports djisdk for telemetry
4. **Future projects** - Any Python project needing DJI drone control

```python
# All these applications use the SAME djisdk library
from djisdk import MQTTClient, ServiceCaller, start_heartbeat
from djisdk import request_control_auth, enter_drc_mode, send_joystick
```

### Decision Tree: Where to Put Code?

**BEFORE adding/modifying ANY code, ask:**

#### ✅ Add to djisdk/ IF:
- It's a **DJI Cloud API service call** (e.g., new camera command, gimbal control)
- It's **general drone communication logic** (MQTT, request/response handling)
- It's **reusable across ANY drone application** (not specific to PID/MPC/display)
- It has **NO dependencies on application logic** (no PID gains, no waypoints, no logging formats)

#### ❌ Keep in application code (control/, main.py, etc.) IF:
- It's **control strategy specific** (PID gains, MPC parameters, waypoint logic)
- It's **application UI/display logic** (Rich formatting for main.py, Plotly visualization)
- It's **data logging/analysis** (CSV format, file paths, visualization style)
- It uses **application-specific configuration** (control frequencies, threshold values)
- It **depends on external systems** (VRPN motion capture, specific sensor setups)

### Real-World Examples

#### ✅ CORRECT: Generic DJI Service → Add to djisdk

**Scenario**: Need to control gimbal angle

```python
# djisdk/services/commands.py (CORRECT - reusable across all apps)

def set_gimbal_angle(caller: ServiceCaller, pitch: float, roll: float, yaw: float) -> Dict[str, Any]:
    """Set gimbal angle (degrees)"""
    return _call_service(caller, "drc_gimbal_angle",
                        {"pitch": pitch, "roll": roll, "yaw": yaw},
                        f"Gimbal set to pitch={pitch}°")
```

**Why?** Generic DJI API wrapper - useful for ANY application (inspection, tracking, photography, etc.)

#### ❌ WRONG: Application Logic → Keep in application

**Scenario**: Gimbal control with PID-specific logic

```python
# control/gimbal_controller.py (CORRECT - app-specific)

from djisdk import set_gimbal_angle
from control.config import GIMBAL_TRACK_GAIN

def track_target_with_gimbal(caller, target_position, drone_position):
    """Point gimbal at target using control gains"""
    angle_error = calculate_angle(target_position, drone_position)
    pitch = angle_error * GIMBAL_TRACK_GAIN  # Application-specific logic
    set_gimbal_angle(caller, pitch=pitch, roll=0, yaw=0)
```

**Why?** Uses application-specific config (GIMBAL_TRACK_GAIN) and control logic - NOT reusable.

#### ❌ ANTI-PATTERN: Don't Do This!

```python
# ❌ WRONG: Adding PID logic to djisdk
# djisdk/services/control.py  <- NO!

def control_position_with_pid(caller, target, current, kp, kd):
    """Control drone position using PID"""  # <- Application logic in library!
    error = target - current
    output = kp * error + kd * derivative(error)
    send_joystick(caller, pitch=output, ...)
```

**Why wrong?** PID control is application-specific - other users might use MPC, LQR, or manual control!

### API Stability Rules

#### When Modifying djisdk, You MUST:

1. **Maintain backward compatibility** - Existing applications (control/, control_mpc/, main.py) must continue working
2. **Add, don't change** - Add new functions instead of changing existing signatures
3. **Use optional parameters** - New parameters should have sensible defaults
4. **Document breaking changes** - If unavoidable, document migration path

#### Good API Evolution

```python
# ✅ GOOD: Add optional parameter with default
def enter_drc_mode(caller, mqtt_broker, osd_frequency=30, hsi_frequency=10,
                   camera_frequency=5):  # New optional param
    """..."""
    # Existing code still works: enter_drc_mode(caller, broker)
```

```python
# ❌ BAD: Change required parameter
def enter_drc_mode(caller, mqtt_broker, config_dict):  # Changed signature!
    """..."""
    # BREAKS all existing code!
```

### Decoupling Guidelines

#### ✅ djisdk Should:
- Use **standard Python types** (str, int, float, dict, list)
- Depend only on **minimal external libraries** (paho-mqtt, rich for console)
- Have **zero knowledge** of applications using it
- Provide **thin wrappers** around DJI API (no business logic)

#### ❌ djisdk Should NEVER:
- Import from `control/`, `control_mpc/`, or any application module
- Hard-code application-specific values (PID gains, file paths, etc.)
- Make assumptions about how it will be used (e.g., "users always want logging")
- Include UI/display logic beyond basic console status messages

### Testing Impact

**When modifying djisdk**, you MUST ensure:

```bash
# 1. djisdk tests pass
python tests/run_tests.py

# 2. ALL applications still work
python control/main.py          # PID control works
python control_mpc/mpc_main.py  # MPC control works
python main.py                   # Display system works
```

**If ANY application breaks** → Your change violates reusability!

### Quick Reference

| Code Type | Location | Example |
|-----------|----------|---------|
| DJI API wrapper | `djisdk/services/commands.py` | `send_joystick()`, `enter_drc_mode()` |
| Control algorithm | `control/controller.py` | PID, waypoint navigation |
| System identification | `control_mpc/system_id.py` | PRBS signal generation |
| Data logging | `control/logger.py` | CSV format, file management |
| Visualization | `control/visualize.py` | Plotly charts |
| MQTT connection | `djisdk/core/mqtt_client.py` | Connection management |
| Configuration | `control/config.py`, `dashboard/config.py` | App-specific settings |

### Remember

**"Is this code useful for ANY drone application, or just THIS specific application?"**

- ANY application → djisdk/
- THIS application → application directory (control/, etc.)

When in doubt, **keep it OUT of djisdk** - it's easier to move reusable code INTO djisdk later than to remove application-specific code that leaked in!

## Development Commands

### Essential Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Control System Commands
python control/main.py                    # Run PID position + yaw control
python control/yaw_main.py               # Run yaw-only control
python control/visualize.py data/latest  # Visualize latest control logs

# MPC Control System Commands
python control_mpc/mpc_main.py           # Run MPC controller (real drone)
python control_mpc/test_mpc.py           # Test MPC with simulation

# Main Display System
python main.py                           # Multi-drone display with VRPN
USE_MOCK_DRONE=1 python main.py         # Use mock data instead of real drones

# DJI SDK Commands
# CLI module removed - use djisdk library directly in your code

# Monitoring and Testing
python utils/mqtt_sniffer.py            # Monitor MQTT traffic
python vrpn_test.py                      # Test VRPN connection
```

## Key System Components

### 1. Control System Architecture

**control/** - PID-based position and yaw control
- `config.py` - All control parameters (PID gains, thresholds, frequencies)
- `main.py` - Combined plane + yaw control with waypoint navigation
- `yaw_main.py` - Yaw-only control with automatic angle targets
- `controller.py` - Control strategies with advanced features
- `pid.py` - PID implementation with anti-windup
- `logger.py` - Data logging with PID component tracking
- `visualize.py` - Interactive Plotly visualization

**Configuration Pattern**: All tunable parameters centralized in `control/config.py`:
```python
# PID gains
KP_XY = 400.0    # Position control
KD_XY = 10.0
KP_YAW = 12.0    # Yaw control

# Control frequency and limits
CONTROL_FREQUENCY = 50  # Hz
MAX_STICK_OUTPUT = 150  # Half-stick limit
```

### 2. MPC System Architecture

**control_mpc/** - Model Predictive Control for 200ms delay compensation
- `mpc_controller.py` - Core MPC algorithm with QP optimization
- `system_id.py` - Automatic system identification using PRBS signals
- `delay_compensator.py` - State prediction for delay compensation
- `mpc_main.py` - Main control loop (identification → control)
- `test_mpc.py` - Simulation and validation

**Key Innovation**: Converts 200ms communication delay from disadvantage to advantage through predictive control.

### 3. VRPN Integration

**vrpn/** - Motion capture system integration
- Uses ZeroMQ for communication with VRPN server
- Provides position feedback for closed-loop control
- Quaternion to Euler angle conversion

### 4. Display System

**main.py** - Multi-drone real-time display
- Rich-based terminal UI with live updates
- Combines DJI telemetry + VRPN motion capture data
- Support for mock simulation mode (`USE_MOCK_DRONE=1`)

## Data Logging and Visualization

All control tests automatically create timestamped logs in `data/` directory:
- CSV files with full telemetry and PID components
- `latest/` directories for quick access to most recent logs
- Interactive HTML visualizations with Plotly

**Example workflow**:
```bash
python control/main.py        # Creates data/latest/
python control/visualize.py data/latest  # Opens interactive charts
```

## DJI SDK Architecture

### Quick Start Example

```python
from djisdk import (
    MQTTClient, ServiceCaller,
    request_control_auth, enter_drc_mode,
    start_heartbeat, stop_heartbeat
)

# 1. Connect
mqtt = MQTTClient('GATEWAY_SN', {'host': '192.168.31.73', 'port': 1883, 'username': 'dji', 'password': 'lab605605'})
mqtt.connect()

# 2. Request control
caller = ServiceCaller(mqtt)
request_control_auth(caller, user_id='pilot', user_callsign='Callsign')

# 3. Enter DRC mode
mqtt_broker_config = {
    'address': '192.168.31.73:1883', 'client_id': 'drc-client',
    'username': 'dji', 'password': 'lab605605',
    'expire_time': 1_700_000_000, 'enable_tls': False
}
enter_drc_mode(caller, mqtt_broker=mqtt_broker_config, osd_frequency=100, hsi_frequency=10)

# 4. Start heartbeat
heartbeat_thread = start_heartbeat(mqtt, interval=0.2)

# 5. Control drone...

# Cleanup
stop_heartbeat(heartbeat_thread)
mqtt.disconnect()
```

## Architecture Deep Dive

### Core Layer Design

#### MQTTClient (~100 lines)
**Responsibility**: MQTT connection + Future-based async request handling

```python
class MQTTClient:
    pending_requests: Dict[str, Future]  # tid -> Future mapping
    lock: threading.Lock                 # Thread-safe access

    def publish(method, data, tid) -> Future:
        """Publish request, return Future for response"""
        future = Future()
        with self.lock:
            self.pending_requests[tid] = future
        # Publish to /services topic
        return future

    def _on_message(client, userdata, msg):
        """MQTT callback - resolve Future when response arrives"""
        payload = json.loads(msg.payload)
        tid = payload['tid']
        with self.lock:
            future = self.pending_requests.pop(tid)
            if payload['info']['code'] == 0:
                future.set_result(payload['data'])
            else:
                future.set_exception(Exception(payload['info']['message']))
```

**Why Future pattern?**
- Converts async MQTT into sync API
- Automatic timeout handling
- Thread-safe response routing

#### ServiceCaller (~50 lines)
**Responsibility**: Sync wrapper + unique TID generation

```python
class ServiceCaller:
    def call(method, data, timeout=10):
        """Synchronous service call"""
        tid = str(uuid4())
        future = self.mqtt.publish(method, data, tid)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            self.mqtt.cleanup_request(tid)  # Prevent memory leak
            raise TimeoutError(f"Service timeout: {method}")
```

**Why sync wrapper?**
- Simpler API for users (no async/await)
- Automatic resource cleanup on timeout
- Easy to test with mock

### Business Layer Design

#### _call_service() Pattern (THE KEY INNOVATION)

**Problem**: Every service had identical boilerplate:
```python
# 90% duplication across 4 files (auth.py, drc_mode.py, live.py)
def some_service(caller, params):
    try:
        result = caller.call("method", data)
        if result.get('result') == 0:
            console.print("[green]Success[/green]")
            return result.get('data', {})
        else:
            console.print(f"[red]Failed: {result}[/red]")
            raise Exception(...)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise
```

**Solution**: Extract to universal wrapper:
```python
def _call_service(caller, method, data=None, success_msg=None):
    """Universal wrapper - used by ALL services"""
    try:
        result = caller.call(method, data or {})
        if result.get('result') == 0:
            if success_msg:
                console.print(f"[green]✓ {success_msg}[/green]")
            return result.get('data', {})
        else:
            raise Exception(f"{method} failed: {result.get('message')}")
    except Exception as e:
        console.print(f"[red]✗ {method}: {e}[/red]")
        raise
```

**Impact**: Every service becomes 1-2 lines:
```python
def request_control_auth(caller, user_id="default", user_callsign="Pilot"):
    console.print("[bold cyan]Requesting control...[/bold cyan]")
    return _call_service(caller, "cloud_control_auth_request",
                        {"user_id": user_id, "user_callsign": user_callsign, "control_keys": ["flight"]},
                        "Control auth granted")

def enter_drc_mode(caller, mqtt_broker, osd_frequency=30, hsi_frequency=10):
    console.print("[bold cyan]Entering DRC mode...[/bold cyan]")
    return _call_service(caller, "drc_mode_enter",
                        {"mqtt_broker": mqtt_broker, "osd_frequency": osd_frequency, "hsi_frequency": hsi_frequency},
                        f"DRC mode entered (OSD: {osd_frequency}Hz, HSI: {hsi_frequency}Hz)")
```

### Heartbeat - The Only Special Case

**Why separate?**
- Background thread (not request-response)
- Different topic (`/drc/down` instead of `/services`)
- Different protocol (seq instead of tid/bid)
- QoS 0 (no response expected)
- Precise timing required (perf_counter)

```python
def start_heartbeat(mqtt_client, interval=0.2) -> threading.Thread:
    """Start background heartbeat thread"""
    def heartbeat_loop():
        next_tick = time.perf_counter()
        seq = int(time.time() * 1000)
        while not stop_flag.is_set():
            # Precise timing
            current = time.perf_counter()
            if current >= next_tick:
                seq += 1
                mqtt_client.client.publish(
                    f"thing/product/{mqtt_client.gateway_sn}/drc/down",
                    json.dumps({"seq": seq, "method": "heart_beat", "data": {"timestamp": int(time.time() * 1000)}}),
                    qos=0
                )
                next_tick += interval
            time.sleep(0.001)

    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    thread.stop_flag = threading.Event()
    thread.start()
    return thread
```

## Adding New Functionality

### ✅ CORRECT Way: Add to commands.py

**Example 1: Simple service (1 line)**
```python
# djisdk/services/commands.py

def send_joystick(caller: ServiceCaller, pitch: float, roll: float, yaw: float, throttle: float) -> Dict[str, Any]:
    """Send virtual joystick command"""
    return _call_service(caller, "drc_joystick", {"pitch": pitch, "roll": roll, "yaw": yaw, "throttle": throttle})
```

**Example 2: Service with custom output**
```python
# djisdk/services/commands.py

def set_camera_mode(caller: ServiceCaller, mode: str) -> Dict[str, Any]:
    """Switch camera mode"""
    mode_names = {"photo": "Photo", "video": "Video", "timelapse": "Timelapse"}
    console.print(f"[cyan]Switching to {mode_names.get(mode, mode)} mode[/cyan]")
    return _call_service(caller, "drc_camera_mode", {"mode": mode}, f"Camera mode: {mode_names.get(mode, mode)}")
```

**Export in `services/__init__.py`:**
```python
from .commands import (
    # ... existing ...
    send_joystick,
    set_camera_mode,
)

__all__ = [
    # ... existing ...
    'send_joystick',
    'set_camera_mode',
]
```

**Export in `djisdk/__init__.py`:**
```python
from .services import (
    # ... existing ...
    send_joystick,
    set_camera_mode,
)

__all__ = [
    # ... existing ...
    'send_joystick',
    'set_camera_mode',
]
```

**Usage:**
```python
from djisdk import send_joystick, set_camera_mode

send_joystick(caller, pitch=0.5, roll=0, yaw=0, throttle=0.8)
set_camera_mode(caller, mode="photo")
```

### ❌ WRONG Way: Don't Do This

```python
# ❌ Don't create new files for each service
# djisdk/services/joystick.py  <- NO!

# ❌ Don't create classes for stateless services
class JoystickService:  <- NO!
    def send(self, ...):
        ...

# ❌ Don't duplicate try/except boilerplate
def send_joystick(caller, ...):  <- NO!
    try:
        result = caller.call(...)
        if result.get('result') == 0:
            console.print("[green]Success[/green]")
            return result.get('data', {})
        # ... 20 more lines of duplication ...
```

## Testing Guidelines

### Test Structure

Every module has comprehensive tests:
- `test_mqtt_client.py` - MQTTClient (10 tests)
- `test_service_caller.py` - ServiceCaller (8 tests)
- `test_commands.py` - Business services (15 tests)
- `test_heartbeat.py` - Heartbeat thread (9 tests)

**Total: 42 tests, 92% coverage**

### Testing Pattern

```python
import unittest
from unittest.mock import Mock, patch

class TestNewService(unittest.TestCase):
    def setUp(self):
        """Run before each test"""
        self.mock_caller = Mock()

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_new_service(self, mock_console, mock_call_service):
        """Test service calls _call_service correctly"""
        new_service_function(self.mock_caller, param="value")

        # Verify call arguments
        mock_call_service.assert_called_once_with(
            self.mock_caller,
            "service_method_name",
            {"param": "value"},
            "Success message"
        )

    def test_error_handling(self):
        """Test error propagation"""
        self.mock_caller.call.side_effect = Exception("Network error")

        with self.assertRaises(Exception) as context:
            service_function(self.mock_caller)

        self.assertIn("Network error", str(context.exception))
```

### Testing Checklist

When adding new functionality:
1. ✅ Write test BEFORE implementing (TDD)
2. ✅ Test success path
3. ✅ Test error path
4. ✅ Test with invalid parameters
5. ✅ Mock external dependencies (MQTT, network)
6. ✅ Verify console output
7. ✅ Check resource cleanup

## Common Patterns

### Pattern 1: Request-Response Service
```python
def service_name(caller: ServiceCaller, param1: str, param2: int) -> Dict[str, Any]:
    """Service description"""
    console.print("[cyan]Doing something...[/cyan]")
    return _call_service(caller, "dji_method_name",
                        {"param1": param1, "param2": param2},
                        "Success message")
```

### Pattern 2: Background Task
```python
def start_task(mqtt_client: MQTTClient, interval: float) -> threading.Thread:
    """Start background task"""
    def task_loop():
        while not stop_flag.is_set():
            # Do work
            time.sleep(interval)

    thread = threading.Thread(target=task_loop, daemon=True)
    thread.stop_flag = threading.Event()
    thread.start()
    return thread

def stop_task(thread: threading.Thread):
    """Stop background task"""
    if hasattr(thread, 'stop_flag'):
        thread.stop_flag.set()
    thread.join(timeout=2)
```

### Pattern 3: Custom Message Handler
```python
def custom_handler(client, userdata, msg):
    """Handle specific MQTT messages"""
    payload = json.loads(msg.payload.decode())
    method = payload.get('method')

    if method == 'specific_event':
        data = payload.get('data', {})
        # Process data
        print(f"Received: {data}")

# Register handler
mqtt.client.on_message = custom_handler
```

## Common Pitfalls & Solutions

### ❌ Pitfall 1: Creating Service Classes
**Wrong:**
```python
class AuthService:
    def request_auth(self, ...):
        ...
```

**Right:**
```python
def request_control_auth(caller, ...):
    return _call_service(...)
```

### ❌ Pitfall 2: Duplicating Error Handling
**Wrong:**
```python
def new_service(caller, ...):
    try:
        result = caller.call(...)
        if result.get('result') == 0:
            # ... duplication ...
```

**Right:**
```python
def new_service(caller, ...):
    return _call_service(caller, "method", data)
```

### ❌ Pitfall 3: Using Old HeartbeatKeeper Class
**Wrong:**
```python
heartbeat = HeartbeatKeeper(caller)  # Removed!
heartbeat.start()
```

**Right:**
```python
thread = start_heartbeat(mqtt, interval=0.2)
stop_heartbeat(thread)
```

### ❌ Pitfall 4: Not Cleaning Up Resources
**Wrong:**
```python
mqtt.connect()
# ... do work ...
# Forget to disconnect - connection leak!
```

**Right:**
```python
mqtt.connect()
try:
    # ... do work ...
finally:
    stop_heartbeat(thread)
    mqtt.disconnect()
```

## Code Review Checklist

Before committing code, verify:

### Code Reuse (CRITICAL!)
- [ ] **Proper separation**: DJI API wrappers in `djisdk/`, application logic in `control/` etc.
- [ ] **No coupling**: djisdk does NOT import from application modules
- [ ] **No app-specific logic in djisdk**: No PID gains, waypoints, file paths, or control strategies
- [ ] **Backward compatibility**: Existing applications (control/, control_mpc/, main.py) still work
- [ ] **All tests pass**: Both `python tests/run_tests.py` AND all application entry points work
- [ ] **API evolution**: New parameters are optional with sensible defaults

### Simplicity
- [ ] No unnecessary abstraction
- [ ] No complex design patterns
- [ ] Direct, obvious code flow
- [ ] Function names clearly describe behavior

### Consistency
- [ ] New services use `_call_service()` wrapper
- [ ] Console output uses Rich formatting (`[cyan]`, `[green]`, `[red]`)
- [ ] Type hints on function signatures
- [ ] Docstrings for public functions

### Testing
- [ ] Unit tests added for new functionality
- [ ] Tests use mocks to isolate dependencies
- [ ] Both success and error paths tested
- [ ] Test coverage maintained above 90%

### Documentation
- [ ] Function docstrings updated
- [ ] README.md examples updated if API changed
- [ ] No sensitive information (passwords, keys) in code

## File Organization

```
djisdk/
├── __init__.py              # Main exports
├── README.md                # User documentation (with PlantUML diagrams)
├── core/
│   ├── __init__.py
│   ├── mqtt_client.py       # MQTTClient class (~100 lines)
│   └── service_caller.py    # ServiceCaller class (~50 lines)
├── services/
│   ├── __init__.py
│   ├── commands.py          # ALL services (167 lines)
│   └── heartbeat.py         # Background heartbeat (89 lines)
├── cli/
│   ├── __init__.py
│   └── drc_control.py       # Interactive CLI tool
└── tests/
    ├── __init__.py
    ├── README.md            # Testing guide
    ├── run_tests.py         # Test runner
    ├── test_mqtt_client.py
    ├── test_service_caller.py
    ├── test_commands.py
    └── test_heartbeat.py

utils/
└── mqtt_sniffer.py          # Multi-topic MQTT monitor

ARCHITECTURE_REFACTOR.md     # Refactoring report
TEST_REPORT.md               # Test completion report
```

## Key Takeaways

1. **Simplicity wins** - 2 classes, pure functions, no patterns
2. **Eliminate duplication** - `_call_service()` wrapper is the key
3. **Code reuse is sacred** - djisdk is a library, NOT an application module
4. **Separation of concerns** - API wrappers in djisdk/, application logic stays out
5. **Test everything** - 92% coverage is not optional
6. **Stay focused** - Don't add features nobody asked for
7. **Trust the pattern** - When in doubt, look at existing services

---

**"Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away."** - Antoine de Saint-Exupéry
