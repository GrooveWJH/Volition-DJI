#!/usr/bin/env python3
"""Minimal VRPN with Rich output."""

import math
import time
from typing import Iterable, Optional, Tuple

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from vrpn import VRPNClient

console = Console()

droneName = "Drone001"


def quaternion_to_euler(quaternion: Iterable[float]) -> Optional[Tuple[float, float, float]]:
    """Return roll, pitch, yaw (radians) for an (x, y, z, w) quaternion."""
    try:
        x, y, z, w = quaternion
    except (TypeError, ValueError):
        return None

    # Roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


def format_tuple(values: Optional[Iterable[float]], precision: int = 4) -> str:
    """Format an iterable of floats (or return '-') for display."""
    if values is None:
        return "-"
    try:
        return "(" + ", ".join(f"{value:.{precision}f}" for value in values) + ")"
    except TypeError:
        return "-"


def format_euler(rad_values: Optional[Iterable[float]]) -> str:
    """Format Euler angles in degrees and multiples of pi."""
    if rad_values is None:
        return "-"
    try:
        rad_list = [float(value) for value in rad_values]
    except (TypeError, ValueError):
        return "-"

    deg_list = [math.degrees(value) for value in rad_list]
    pi_list = [value / math.pi for value in rad_list]

    deg_str = "(" + ", ".join(f"{value:.3f}" for value in deg_list) + ") deg"
    pi_str = "(" + ", ".join(f"{value:.3f}" for value in pi_list) + ") pi"

    return f"{deg_str} / {pi_str}"


def build_table(client) -> Table:
    """Collect VRPN data into a table for rendering."""
    pose = client.pose
    velocity = client.velocity
    acceleration = client.acceleration

    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", justify="right")
    table.add_column()

    table.add_row("[bold]Pose[/bold]", "")
    table.add_row("timestamp", f"{getattr(pose, 'timestamp', 0.0):.3f}s")
    table.add_row("position", format_tuple(getattr(pose, "position", None)))
    pose_quat = getattr(pose, "quaternion", None)
    table.add_row("quaternion", format_tuple(pose_quat))
    table.add_row("euler (deg/pi)", format_euler(quaternion_to_euler(pose_quat)))

    table.add_row("", "")
    table.add_row("[bold]Velocity[/bold]", "")
    table.add_row("timestamp", f"{getattr(velocity, 'timestamp', 0.0):.3f}s")
    table.add_row("linear", format_tuple(getattr(velocity, "linear", None)))
    vel_quat = getattr(velocity, "angular_quat", None)
    table.add_row("angular quat", format_tuple(vel_quat))
    table.add_row("angular euler (deg/pi)", format_euler(quaternion_to_euler(vel_quat)))

    table.add_row("", "")
    table.add_row("[bold]Acceleration[/bold]", "")
    table.add_row("timestamp", f"{getattr(acceleration, 'timestamp', 0.0):.3f}s")
    table.add_row("linear", format_tuple(getattr(acceleration, "linear", None)))
    acc_quat = getattr(acceleration, "angular_quat", None)
    table.add_row("angular quat", format_tuple(acc_quat))
    table.add_row("angular euler (deg/pi)", format_euler(quaternion_to_euler(acc_quat)))

    return table


with VRPNClient(f"{droneName}@192.168.31.100") as client:
    console.print("[cyan]Waiting for VRPN data...[/cyan]")
    while not client.has_data:
        time.sleep(0.1)

    console.print("[bold green]Data received![/bold green]\n")

    with Live(console=console, refresh_per_second=5) as live:
        while True:
            time.sleep(0.1)
            panel = Panel(
                build_table(client),
                title="Latest VRPN Data",
                border_style="bright_blue",
            )
            live.update(panel)
