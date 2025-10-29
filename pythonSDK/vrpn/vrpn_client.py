"""VRPN Client - All-in-one interface for receiving VRPN data"""
import subprocess
import threading
import time
import ctypes
import zmq
from pathlib import Path
from typing import Optional, Callable, Any, Union
from .types import (
    MessageType,
    VRPN_TRACKERCB, VRPN_TRACKERVELCB, VRPN_TRACKERACCCB,
    VRPNPose, VRPNVelocity, VRPNAcceleration
)


class VRPNClient:
    """
    VRPN Client with automatic resource management.

    Usage:
        # Auto-start vrpn_send subprocess
        with VRPNClient("Drone001@192.168.31.100") as client:
            print(client.pose)
            print(client.velocity)

        # Connect to external vrpn_send
        with VRPNClient() as client:
            print(client.pose)
    """

    # Decoder mapping (Good Taste pattern - zero if-elif chains)
    _DECODERS = {
        MessageType.POSE: (VRPN_TRACKERCB, lambda d: VRPNPose(
            timestamp=d.msg_time_tv_sec + d.msg_time_tv_usec / 1e6,
            sensor=d.sensor,
            position=tuple(d.pos),
            quaternion=tuple(d.quat)
        )),
        MessageType.VELOCITY: (VRPN_TRACKERVELCB, lambda d: VRPNVelocity(
            timestamp=d.msg_time_tv_sec + d.msg_time_tv_usec / 1e6,
            sensor=d.sensor,
            linear=tuple(d.vel),
            angular_quat=tuple(d.vel_quat),
            dt=d.vel_quat_dt
        )),
        MessageType.ACCELERATION: (VRPN_TRACKERACCCB, lambda d: VRPNAcceleration(
            timestamp=d.msg_time_tv_sec + d.msg_time_tv_usec / 1e6,
            sensor=d.sensor,
            linear=tuple(d.acc),
            angular_quat=tuple(d.acc_quat),
            dt=d.acc_quat_dt
        ))
    }

    def __init__(
        self,
        device_name: Optional[str] = None,
        zmq_address: str = "tcp://localhost:5555",
        vrpn_send_path: Optional[str] = None,
        callback: Optional[Callable[[Any], None]] = None
    ):
        """
        Initialize VRPN Client.

        Args:
            device_name: VRPN device (e.g. "Drone001@192.168.31.100").
                        If provided, auto-start vrpn_send subprocess.
            zmq_address: ZeroMQ address to connect to
            vrpn_send_path: Path to vrpn_send executable (auto-detect if None)
            callback: Optional callback for each received message
        """
        self.zmq_address = zmq_address
        self._callback = callback

        # Subprocess management
        self._process: Optional[subprocess.Popen] = None
        self._vrpn_send_path = self._find_vrpn_send(vrpn_send_path)

        # Background thread
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

        # Thread-safe data cache
        self._lock = threading.Lock()
        self._pose: Optional[VRPNPose] = None
        self._velocity: Optional[VRPNVelocity] = None
        self._acceleration: Optional[VRPNAcceleration] = None

        # Auto-start if device_name provided
        if device_name:
            self._start_process(device_name)

        # Start receiving
        self._start_receiver()

    def __enter__(self) -> 'VRPNClient':
        """Context manager entry"""
        return self

    def __exit__(self, *args):
        """Context manager exit - automatic cleanup"""
        self.stop()

    def __del__(self):
        """Destructor fallback - cleanup if not stopped"""
        self.stop()

    @property
    def pose(self) -> Optional[VRPNPose]:
        """Get latest pose data (thread-safe)"""
        with self._lock:
            return self._pose

    @property
    def velocity(self) -> Optional[VRPNVelocity]:
        """Get latest velocity data (thread-safe)"""
        with self._lock:
            return self._velocity

    @property
    def acceleration(self) -> Optional[VRPNAcceleration]:
        """Get latest acceleration data (thread-safe)"""
        with self._lock:
            return self._acceleration

    @property
    def has_data(self) -> bool:
        """Check if any VRPN data has been received (thread-safe)"""
        with self._lock:
            return any([
                self._pose is not None,
                self._velocity is not None,
                self._acceleration is not None
            ])

    def stop(self):
        """Stop receiver and cleanup resources"""
        # Stop receiver thread
        if self._thread and self._thread.is_alive():
            self._stop_flag.set()
            self._thread.join(timeout=2)

        # Stop subprocess
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    @staticmethod
    def _decode(message: bytes) -> Optional[Union[VRPNPose, VRPNVelocity, VRPNAcceleration]]:
        """Decode VRPN message - unified decoder using dictionary lookup"""
        if len(message) < 1:
            return None

        msg_type = message[0]
        payload = message[1:]

        decoder_info = VRPNClient._DECODERS.get(msg_type)
        if not decoder_info:
            return None

        struct_type, converter = decoder_info

        if len(payload) != ctypes.sizeof(struct_type):
            return None

        raw_data = struct_type.from_buffer_copy(payload)
        return converter(raw_data)

    def _find_vrpn_send(self, path: Optional[str]) -> Path:
        """Find vrpn_send executable"""
        if path:
            return Path(path)

        # Auto-detect: assume we're in pythonSDK/vrpn/
        repo_root = Path(__file__).parent.parent
        return repo_root / "vrpn" / "build" / "vrpn_send"

    def _start_process(self, device_name: str):
        """Start vrpn_send subprocess"""
        if not self._vrpn_send_path.exists():
            raise FileNotFoundError(f"vrpn_send not found: {self._vrpn_send_path}")

        try:
            self._process = subprocess.Popen(
                [str(self._vrpn_send_path), device_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(0.5)  # Wait for ZMQ socket to bind
        except Exception as e:
            raise RuntimeError(f"Failed to start vrpn_send: {e}")

    def _start_receiver(self):
        """Start background receiver thread"""
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def _receive_loop(self):
        """Background thread - receive and decode messages"""
        context = zmq.Context()
        subscriber = context.socket(zmq.SUB)
        subscriber.connect(self.zmq_address)
        subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
        subscriber.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout

        try:
            while not self._stop_flag.is_set():
                try:
                    message = subscriber.recv()
                except zmq.Again:
                    continue

                # Decode message
                data = self._decode(message)
                if data is None:
                    continue

                # Update cache (thread-safe)
                with self._lock:
                    if isinstance(data, VRPNPose):
                        self._pose = data
                    elif isinstance(data, VRPNVelocity):
                        self._velocity = data
                    elif isinstance(data, VRPNAcceleration):
                        self._acceleration = data

                # Optional callback
                if self._callback:
                    self._callback(data)

        finally:
            subscriber.close()
            context.term()
