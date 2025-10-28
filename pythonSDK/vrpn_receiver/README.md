# VRPN Receiver

A clean, minimal Python library for receiving VRPN tracker data via ZeroMQ.

## Features

- **Single class API** - Just `VRPNClient`, nothing else to learn
- **Automatic cleanup** - Context manager (`with` statement) handles everything
- **Property access** - `client.pose` instead of `get_latest_pose()`
- **Background threading** - Non-blocking data reception
- **Process management** - Automatically launch/stop vrpn_send subprocess
- **Thread-safe** - Safe concurrent access
- **Minimal code** - Only 327 lines total (3 files)

## Architecture

```
vrpn_receiver/
├── types.py         (75 lines)  - Data structures
├── vrpn_client.py   (228 lines) - VRPNClient class (all-in-one)
└── __init__.py      (24 lines)  - Public exports
```

**Simplified from v1.0:**
- ❌ Removed `decoder.py` → merged into `VRPNClient._decode()`
- ❌ Removed `receiver.py` → merged into `VRPNClient._receive_loop()`
- ❌ Removed `process_manager.py` → merged into `VRPNClient`
- ✅ **350 lines → 327 lines** (7% reduction)
- ✅ **5 files → 3 files** (40% reduction)
- ✅ **8 functions → 1 class** (cleaner API)

## Quick Start

### Minimal Usage (10 lines!)

```python
from vrpn_receiver import VRPNClient
import time

with VRPNClient("Drone001@192.168.31.100") as client:
    # Wait for data
    while not client.has_data:
        time.sleep(0.1)

    print(client.pose)
    print(client.velocity)
    print(client.acceleration)
# Auto-cleanup on exit
```

### External vrpn_send

```python
# Connect to already-running vrpn_send
with VRPNClient() as client:  # Defaults to tcp://localhost:5555
    print(client.pose)
```

### Real-time Callback

```python
def on_data(data):
    print(f"Received: {data}")

with VRPNClient("Drone001@192.168.31.100", callback=on_data) as client:
    # Callback runs in background thread for each message
    input("Press Enter to stop...")
```

### Manual Management (if needed)

```python
client = VRPNClient("Drone001@192.168.31.100")
print(client.pose)
client.stop()  # Manual cleanup
```

## API Reference

### VRPNClient Class

```python
class VRPNClient:
    def __init__(
        device_name: Optional[str] = None,
        zmq_address: str = "tcp://localhost:5555",
        vrpn_send_path: Optional[str] = None,
        callback: Optional[Callable] = None
    )
```

**Parameters:**
- `device_name`: VRPN device (e.g. "Drone001@192.168.31.100")
  - If provided, auto-starts vrpn_send subprocess
  - If None, connects to external vrpn_send
- `zmq_address`: ZeroMQ address to connect to
- `vrpn_send_path`: Path to vrpn_send executable (auto-detect if None)
- `callback`: Optional function called for each message

**Properties (read-only):**
- `client.pose` → `VRPNPose | None`
- `client.velocity` → `VRPNVelocity | None`
- `client.acceleration` → `VRPNAcceleration | None`
- `client.has_data` → `bool` (True if any data received)

**Methods:**
- `stop()` - Manually stop receiver and cleanup resources
- `__enter__()`, `__exit__()` - Context manager support

## Data Types

```python
@dataclass
class VRPNPose:
    timestamp: float                              # seconds since epoch
    sensor: int
    position: Tuple[float, float, float]          # (x, y, z)
    quaternion: Tuple[float, float, float, float] # (qx, qy, qz, qw)

@dataclass
class VRPNVelocity:
    timestamp: float
    sensor: int
    linear: Tuple[float, float, float]            # (vx, vy, vz)
    angular_quat: Tuple[float, float, float, float]
    dt: float

@dataclass
class VRPNAcceleration:
    timestamp: float
    sensor: int
    linear: Tuple[float, float, float]            # (ax, ay, az)
    angular_quat: Tuple[float, float, float, float]
    dt: float
```

## Automatic Resource Cleanup

VRPNClient automatically cleans up resources in three ways:

### 1. Context Manager (Recommended)

```python
with VRPNClient("Drone001@192.168.31.100") as client:
    # Use client...
    pass
# ✓ vrpn_send subprocess terminated
# ✓ Background thread stopped
# ✓ ZMQ connections closed
```

### 2. Manual Cleanup

```python
client = VRPNClient("Drone001@192.168.31.100")
# ... use client ...
client.stop()  # ✓ Clean shutdown
```

### 3. Destructor Fallback

```python
client = VRPNClient("Drone001@192.168.31.100")
# ... forget to call stop() ...
# ✓ __del__() automatically calls stop() on garbage collection
```

**No more orphaned processes!** 🎉

## Running the Examples

```bash
cd pythonSDK

# Minimal test (10 lines)
python3 vrpn_test.py

# Full interactive example
python3 vrpn_receiver/example.py Drone001@192.168.31.100
```

## Design Philosophy

Follows **"Less is more"** principle:

1. ✅ **Single class** - Everything in `VRPNClient`
2. ✅ **Property access** - `client.pose` instead of `get_latest_pose()`
3. ✅ **Context manager** - Automatic cleanup with `with` statement
4. ✅ **Good Taste decoder** - Dictionary lookup (no if-elif chains)
5. ✅ **Minimal abstractions** - Only what's necessary

## Comparison: v1.0 vs v2.0

| Aspect | v1.0 (Function API) | v2.0 (Class API) |
|--------|---------------------|------------------|
| **Files** | 5 modules | 3 modules |
| **Lines** | ~350 lines | 327 lines |
| **API** | 8 global functions | 1 class |
| **Cleanup** | Manual `stop_*()` calls | Automatic (context manager) |
| **Data access** | `get_latest_pose()` | `client.pose` |
| **Instantiation** | Singleton (implicit) | Explicit (`VRPNClient()`) |
| **Multiple clients** | ❌ Not possible | ✅ Supported |

### Migration from v1.0

```python
# OLD (v1.0)
from vrpn_receiver import start_vrpn_process, start_vrpn_receiver, get_latest_pose
start_vrpn_process("Drone001@192.168.31.100")
start_vrpn_receiver()
pose = get_latest_pose()
stop_vrpn_receiver()
stop_vrpn_process()

# NEW (v2.0)
from vrpn_receiver import VRPNClient
with VRPNClient("Drone001@192.168.31.100") as client:
    pose = client.pose
```

## Dependencies

- `pyzmq` - ZeroMQ Python bindings
- Python 3.7+ (for dataclasses)

```bash
pip install pyzmq
```

## License

Same as parent project.
