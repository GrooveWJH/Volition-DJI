#!/usr/bin/env python3
"""
Example: VRPN Data Receiver with VRPNClient

This script demonstrates the simplified usage of VRPNClient:
- Automatic vrpn_send process management
- Context manager for automatic cleanup
- Simple property-based data access
"""

import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vrpn_receiver import VRPNClient


def format_pose(pose):
    """Format pose data for display"""
    if not pose:
        return "  \033[90m<no data yet>\033[0m"
    return (f"  \033[96mTime:\033[0m {pose.timestamp:.3f}s  "
            f"\033[96mSensor:\033[0m {pose.sensor}\n"
            f"  \033[96mPosition:\033[0m ({pose.position[0]:7.3f}, {pose.position[1]:7.3f}, {pose.position[2]:7.3f})\n"
            f"  \033[96mQuaternion:\033[0m ({pose.quaternion[0]:6.3f}, {pose.quaternion[1]:6.3f}, "
            f"{pose.quaternion[2]:6.3f}, {pose.quaternion[3]:6.3f})")


def format_velocity(vel):
    """Format velocity data for display"""
    if not vel:
        return "  \033[90m<no data yet>\033[0m"
    return (f"  \033[93mTime:\033[0m {vel.timestamp:.3f}s  "
            f"\033[93mSensor:\033[0m {vel.sensor}\n"
            f"  \033[93mLinear:\033[0m ({vel.linear[0]:7.4f}, {vel.linear[1]:7.4f}, {vel.linear[2]:7.4f})\n"
            f"  \033[93mAngular:\033[0m ({vel.angular_quat[0]:6.4f}, {vel.angular_quat[1]:6.4f}, "
            f"{vel.angular_quat[2]:6.4f}, {vel.angular_quat[3]:6.4f}) dt={vel.dt:.4f}s")


def format_acceleration(acc):
    """Format acceleration data for display"""
    if not acc:
        return "  \033[90m<no data yet>\033[0m"
    return (f"  \033[91mTime:\033[0m {acc.timestamp:.3f}s  "
            f"\033[91mSensor:\033[0m {acc.sensor}\n"
            f"  \033[91mLinear:\033[0m ({acc.linear[0]:7.4f}, {acc.linear[1]:7.4f}, {acc.linear[2]:7.4f})\n"
            f"  \033[91mAngular:\033[0m ({acc.angular_quat[0]:6.4f}, {acc.angular_quat[1]:6.4f}, "
            f"{acc.angular_quat[2]:6.4f}, {acc.angular_quat[3]:6.4f}) dt={acc.dt:.4f}s")


def main():
    device_name = sys.argv[1] if len(sys.argv) > 1 else "Drone001@192.168.31.100"

    print("\033[1;92m=== VRPN Receiver Example ===\033[0m\n")
    print(f"Device: \033[96m{device_name}\033[0m")
    print("Press Ctrl+C to exit\n")

    # Use context manager - automatic cleanup on exit
    try:
        with VRPNClient(device_name) as client:
            while True:
                # Clear screen and show latest data
                print("\033[2J\033[H", end="")  # Clear screen
                print("\033[1;92m=== VRPN Latest Data ===\033[0m\n")

                print("\033[1;96m[POSE]\033[0m")
                print(format_pose(client.pose))

                print("\n\033[1;93m[VELOCITY]\033[0m")
                print(format_velocity(client.velocity))

                print("\n\033[1;91m[ACCELERATION]\033[0m")
                print(format_acceleration(client.acceleration))

                print("\n\033[90mPress Ctrl+C to exit...\033[0m")

                time.sleep(0.1)  # Update at 10Hz

    except KeyboardInterrupt:
        print("\n\n\033[92mGoodbye!\033[0m\n")


if __name__ == "__main__":
    main()
