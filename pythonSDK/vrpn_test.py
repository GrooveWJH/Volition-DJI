#!/usr/bin/env python3
"""Minimal VRPN"""

import time
from vrpn_receiver import VRPNClient

droneName = "Drone001"

with VRPNClient(f"{droneName}@192.168.31.100") as client:

    # Wait for data
    print("Waiting for VRPN data...")
    while not client.has_data:
        time.sleep(0.1)

    print("\033[92mData received!\033[0m\n")

    # Print data continuously
    while True:
        time.sleep(0.1)
        print("Latest VRPN Data:")
        print(f"  Pose: {client.pose}")
        print(f"  Velocity: {client.velocity}")
        print(f"  Acceleration: {client.acceleration}")