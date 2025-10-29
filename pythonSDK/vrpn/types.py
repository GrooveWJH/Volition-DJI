"""VRPN data type definitions - zero logic, pure structures"""
from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple
import ctypes


class MessageType(IntEnum):
    """VRPN message types"""
    POSE = 0x01
    VELOCITY = 0x02
    ACCELERATION = 0x03


# C struct mappings (keep as-is, they match C++ layout)
class VRPN_TRACKERCB(ctypes.Structure):
    _fields_ = [
        ("msg_time_tv_sec", ctypes.c_long),
        ("msg_time_tv_usec", ctypes.c_long),
        ("sensor", ctypes.c_int32),
        ("pos", ctypes.c_double * 3),
        ("quat", ctypes.c_double * 4)
    ]


class VRPN_TRACKERVELCB(ctypes.Structure):
    _fields_ = [
        ("msg_time_tv_sec", ctypes.c_long),
        ("msg_time_tv_usec", ctypes.c_long),
        ("sensor", ctypes.c_int32),
        ("vel", ctypes.c_double * 3),
        ("vel_quat", ctypes.c_double * 4),
        ("vel_quat_dt", ctypes.c_double)
    ]


class VRPN_TRACKERACCCB(ctypes.Structure):
    _fields_ = [
        ("msg_time_tv_sec", ctypes.c_long),
        ("msg_time_tv_usec", ctypes.c_long),
        ("sensor", ctypes.c_int32),
        ("acc", ctypes.c_double * 3),
        ("acc_quat", ctypes.c_double * 4),
        ("acc_quat_dt", ctypes.c_double)
    ]


# Python-friendly data classes (for consumers)
@dataclass
class VRPNPose:
    """Parsed pose data"""
    timestamp: float  # seconds since epoch
    sensor: int
    position: Tuple[float, float, float]
    quaternion: Tuple[float, float, float, float]


@dataclass
class VRPNVelocity:
    """Parsed velocity data"""
    timestamp: float
    sensor: int
    linear: Tuple[float, float, float]
    angular_quat: Tuple[float, float, float, float]
    dt: float


@dataclass
class VRPNAcceleration:
    """Parsed acceleration data"""
    timestamp: float
    sensor: int
    linear: Tuple[float, float, float]
    angular_quat: Tuple[float, float, float, float]
    dt: float
