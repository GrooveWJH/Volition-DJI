# VRPN Interface

Minimal VRPN tracker interface with C++ bridge and Python client.

## Architecture

```
vrpn/
├── send.cpp           # C++ VRPN → ZeroMQ bridge (core interface)
├── CMakeLists.txt     # C++ build configuration
├── vrpn_client.py     # Python ZeroMQ client
├── types.py           # Python data types
└── __init__.py        # Python module exports
```

## Build C++ Bridge

```bash
cd vrpn
mkdir build && cd build
cmake ..
make
```

This produces `vrpn_send` executable.

## C++ Interface: vrpn_send

**Purpose**: Bridge VRPN tracker data to ZeroMQ (tcp://*:5555)

```bash
./vrpn_send <Device@Host>

# Example
./vrpn_send Drone001@192.168.31.100
```

**Output**: Publishes 3 message types via ZeroMQ:
- `0x01` - Pose (position + quaternion)
- `0x02` - Velocity (linear + angular)
- `0x03` - Acceleration (linear + angular)

## Python Interface: VRPNClient

**Purpose**: Receive and decode ZeroMQ messages from vrpn_send

### Basic Usage

```python
from vrpn import VRPNClient

# Auto-start vrpn_send subprocess
with VRPNClient("Drone001@192.168.31.100") as client:
    print(client.pose)          # VRPNPose | None
    print(client.velocity)      # VRPNVelocity | None
    print(client.acceleration)  # VRPNAcceleration | None
```

### Connect to External vrpn_send

```python
# Connect to already-running vrpn_send
with VRPNClient() as client:
    print(client.pose)
```

### Constructor

```python
VRPNClient(
    device_name: Optional[str] = None,         # Auto-start vrpn_send if provided
    zmq_address: str = "tcp://localhost:5555", # ZeroMQ address
    vrpn_send_path: Optional[str] = None,      # Path to vrpn_send (auto-detect)
    callback: Optional[Callable] = None        # Optional callback for each message
)
```

### Data Types

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

## Dependencies

**C++**: CMake, VRPN library (fetched automatically)

**Python**:
```bash
pip install pyzmq
```

## Wire Protocol

ZeroMQ messages: `[1-byte type][binary payload]`

- Type `0x01` → 56 bytes (pose)
- Type `0x02` → 80 bytes (velocity)
- Type `0x03` → 80 bytes (acceleration)

Payload is raw C struct (little-endian, platform-dependent alignment).
