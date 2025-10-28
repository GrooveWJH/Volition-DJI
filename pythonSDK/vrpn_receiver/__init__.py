"""
VRPN Receiver - Simplified Python library for receiving VRPN tracker data.

Public API:
    VRPNClient - All-in-one client class

Example:
    with VRPNClient("Drone001@192.168.31.100") as client:
        print(client.pose)
        print(client.velocity)
        print(client.acceleration)
"""
from .vrpn_client import VRPNClient
from .types import VRPNPose, VRPNVelocity, VRPNAcceleration, MessageType

__all__ = [
    'VRPNClient',
    'VRPNPose',
    'VRPNVelocity',
    'VRPNAcceleration',
    'MessageType',
]

__version__ = '2.0.0'
