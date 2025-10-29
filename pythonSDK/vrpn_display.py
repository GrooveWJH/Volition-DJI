"""
VRPN 动捕数据显示模块
"""
from typing import Dict, Any, Optional
from rich.panel import Panel
from rich.table import Table
from vrpn import VRPNClient


def create_vrpn_panel(vrpn_client: Optional[VRPNClient], drone_name: str, elapsed: int) -> Panel:
    """
    为单个无人机创建 VRPN 动捕数据面板

    Args:
        vrpn_client: VRPN 客户端实例
        drone_name: 无人机名称 (如 "Drone001")
        elapsed: 运行时间（秒）

    Returns:
        Rich Panel 对象
    """
    # 创建表格
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column(style="bold white")

    # 分割线函数
    def add_separator():
        table.add_row("", "[dim]" + "─" * 30 + "[/dim]")

    # 基本信息
    table.add_row("设备名称:", f"[yellow]{drone_name}[/yellow]")
    table.add_row("运行时间:", f"[green]{elapsed}[/green] 秒")
    add_separator()

    # 检查是否有数据
    if vrpn_client is None or not vrpn_client.has_data:
        table.add_row("状态:", "[yellow]等待动捕数据...[/yellow]")
        return Panel(
            table,
            title=f"[bold]VRPN - {drone_name}[/bold]",
            border_style="yellow",
            padding=(1, 2)
        )

    # 获取最新数据
    pose = vrpn_client.pose
    velocity = vrpn_client.velocity
    acceleration = vrpn_client.acceleration

    # 数据状态
    table.add_row("状态:", "[green]✓ 数据接收中[/green]")
    add_separator()

    # 位置数据 (Pose)
    if pose:
        table.add_row("[bold]位置 (Position):[/bold]", "")
        x, y, z = pose.position
        table.add_row("  X:", f"[green]{x:>8.4f}[/green] m")
        table.add_row("  Y:", f"[green]{y:>8.4f}[/green] m")
        table.add_row("  Z:", f"[green]{z:>8.4f}[/green] m")

        table.add_row("[bold]姿态 (Quaternion):[/bold]", "")
        qx, qy, qz, qw = pose.quaternion
        table.add_row("  qx:", f"[cyan]{qx:>8.4f}[/cyan]")
        table.add_row("  qy:", f"[cyan]{qy:>8.4f}[/cyan]")
        table.add_row("  qz:", f"[cyan]{qz:>8.4f}[/cyan]")
        table.add_row("  qw:", f"[cyan]{qw:>8.4f}[/cyan]")

        table.add_row("时间戳:", f"[dim]{pose.timestamp:.3f}[/dim]")
        add_separator()

    # 速度数据 (Velocity)
    if velocity:
        table.add_row("[bold]线速度 (Linear):[/bold]", "")
        vx, vy, vz = velocity.linear
        table.add_row("  Vx:", f"[green]{vx:>8.4f}[/green] m/s")
        table.add_row("  Vy:", f"[green]{vy:>8.4f}[/green] m/s")
        table.add_row("  Vz:", f"[green]{vz:>8.4f}[/green] m/s")

        table.add_row("[bold]角速度 (Angular):[/bold]", "")
        wx, wy, wz, ww = velocity.angular_quat
        table.add_row("  ωx:", f"[cyan]{wx:>8.4f}[/cyan]")
        table.add_row("  ωy:", f"[cyan]{wy:>8.4f}[/cyan]")
        table.add_row("  ωz:", f"[cyan]{wz:>8.4f}[/cyan]")
        table.add_row("  ωw:", f"[cyan]{ww:>8.4f}[/cyan]")

        table.add_row("Δt:", f"[dim]{velocity.dt:.3f}[/dim] s")
        add_separator()

    # 加速度数据 (Acceleration)
    if acceleration:
        table.add_row("[bold]线加速度 (Linear):[/bold]", "")
        ax, ay, az = acceleration.linear
        table.add_row("  Ax:", f"[green]{ax:>8.4f}[/green] m/s²")
        table.add_row("  Ay:", f"[green]{ay:>8.4f}[/green] m/s²")
        table.add_row("  Az:", f"[green]{az:>8.4f}[/green] m/s²")

        table.add_row("[bold]角加速度 (Angular):[/bold]", "")
        αx, αy, αz, αw = acceleration.angular_quat
        table.add_row("  αx:", f"[cyan]{αx:>8.4f}[/cyan]")
        table.add_row("  αy:", f"[cyan]{αy:>8.4f}[/cyan]")
        table.add_row("  αz:", f"[cyan]{αz:>8.4f}[/cyan]")
        table.add_row("  αw:", f"[cyan]{αw:>8.4f}[/cyan]")

        table.add_row("Δt:", f"[dim]{acceleration.dt:.3f}[/dim] s")

    # 面板标题和边框颜色
    panel_color = "green" if vrpn_client.has_data else "yellow"
    title = f"[bold]VRPN - {drone_name}[/bold]"

    return Panel(
        table,
        title=title,
        border_style=panel_color,
        padding=(1, 2)
    )
