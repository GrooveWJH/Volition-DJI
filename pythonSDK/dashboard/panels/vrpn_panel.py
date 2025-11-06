"""
VRPN 面板模块

负责生成 VRPN 动捕数据面板，包括：
- 位置数据（Position）
- 姿态数据（Quaternion）
- 速度数据（Linear/Angular Velocity）
- 加速度数据（Linear/Angular Acceleration）
"""
from rich.panel import Panel
from rich.table import Table


def create_vrpn_panel(vrpn_client, drone_name: str, elapsed: int) -> Panel:
    """
    为单个无人机创建 VRPN 动捕数据面板

    Args:
        vrpn_client: VRPN 客户端实例
        drone_name: 无人机名称 (如 "Drone001")
        elapsed: 运行时间（秒）

    Returns:
        Rich Panel 对象
    """
    # 创建表格 - 前卫配色：亮青标题 + 亮白数据
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_cyan", justify="right")
    table.add_column(style="bold bright_white")

    # 分割线函数
    def add_separator():
        table.add_row("", "[dim]" + "─" * 30 + "[/dim]")

    # 基本信息 - 前卫配色：亮洋红色设备名
    table.add_row("设备名称:", f"[bright_magenta]{drone_name}[/bright_magenta]")
    table.add_row("运行时间:", f"[bright_green]{elapsed}[/bright_green] 秒")
    add_separator()

    # 检查是否有数据 - 前卫配色：亮黄等待状态
    if vrpn_client is None or not vrpn_client.has_data:
        table.add_row("状态:", "[bright_yellow]等待动捕数据...[/bright_yellow]")
        return Panel(
            table,
            title=f"[bold]VRPN - {drone_name}[/bold]",
            border_style="bright_yellow",
            padding=(1, 2)
        )

    # 获取最新数据
    pose = vrpn_client.pose
    velocity = vrpn_client.velocity
    acceleration = vrpn_client.acceleration

    # 数据状态 - 前卫配色：亮绿成功状态
    table.add_row("状态:", "[bright_green]✓ 数据接收中[/bright_green]")
    add_separator()

    # 位置数据 (Pose) - 前卫配色：亮蓝色位置 + 亮洋红姿态
    if pose:
        table.add_row("[bold]位置 (Position):[/bold]", "")
        x, y, z = pose.position
        table.add_row("  X:", f"[bright_blue]{x:>8.4f}[/bright_blue] m")
        table.add_row("  Y:", f"[bright_blue]{y:>8.4f}[/bright_blue] m")
        table.add_row("  Z:", f"[bright_blue]{z:>8.4f}[/bright_blue] m")

        table.add_row("[bold]姿态 (Quaternion):[/bold]", "")
        qx, qy, qz, qw = pose.quaternion
        table.add_row("  qx:", f"[bright_magenta]{qx:>8.4f}[/bright_magenta]")
        table.add_row("  qy:", f"[bright_magenta]{qy:>8.4f}[/bright_magenta]")
        table.add_row("  qz:", f"[bright_magenta]{qz:>8.4f}[/bright_magenta]")
        table.add_row("  qw:", f"[bright_magenta]{qw:>8.4f}[/bright_magenta]")

        table.add_row("时间戳:", f"[dim]{pose.timestamp:.3f}[/dim]")
        add_separator()

    # 速度数据 (Velocity) - 前卫配色：亮绿线速度 + 亮青角速度
    if velocity:
        table.add_row("[bold]线速度 (Linear):[/bold]", "")
        vx, vy, vz = velocity.linear
        table.add_row("  Vx:", f"[bright_green]{vx:>8.4f}[/bright_green] m/s")
        table.add_row("  Vy:", f"[bright_green]{vy:>8.4f}[/bright_green] m/s")
        table.add_row("  Vz:", f"[bright_green]{vz:>8.4f}[/bright_green] m/s")

        table.add_row("[bold]角速度 (Angular):[/bold]", "")
        wx, wy, wz, ww = velocity.angular_quat
        table.add_row("  ωx:", f"[bright_cyan]{wx:>8.4f}[/bright_cyan]")
        table.add_row("  ωy:", f"[bright_cyan]{wy:>8.4f}[/bright_cyan]")
        table.add_row("  ωz:", f"[bright_cyan]{wz:>8.4f}[/bright_cyan]")
        table.add_row("  ωw:", f"[bright_cyan]{ww:>8.4f}[/bright_cyan]")

        table.add_row("Δt:", f"[dim]{velocity.dt:.3f}[/dim] s")
        add_separator()

    # 加速度数据 (Acceleration) - 前卫配色：亮黄线加速度 + 亮洋红角加速度
    if acceleration:
        table.add_row("[bold]线加速度 (Linear):[/bold]", "")
        ax, ay, az = acceleration.linear
        table.add_row("  Ax:", f"[bright_yellow]{ax:>8.4f}[/bright_yellow] m/s²")
        table.add_row("  Ay:", f"[bright_yellow]{ay:>8.4f}[/bright_yellow] m/s²")
        table.add_row("  Az:", f"[bright_yellow]{az:>8.4f}[/bright_yellow] m/s²")

        table.add_row("[bold]角加速度 (Angular):[/bold]", "")
        αx, αy, αz, αw = acceleration.angular_quat
        table.add_row("  αx:", f"[bright_magenta]{αx:>8.4f}[/bright_magenta]")
        table.add_row("  αy:", f"[bright_magenta]{αy:>8.4f}[/bright_magenta]")
        table.add_row("  αz:", f"[bright_magenta]{αz:>8.4f}[/bright_magenta]")
        table.add_row("  αw:", f"[bright_magenta]{αw:>8.4f}[/bright_magenta]")

        table.add_row("Δt:", f"[dim]{acceleration.dt:.3f}[/dim] s")

    # 面板标题和边框颜色 - 前卫配色：亮蓝边框
    panel_color = "bright_blue" if vrpn_client.has_data else "bright_yellow"
    title = f"[bold]VRPN - {drone_name}[/bold]"

    return Panel(
        table,
        title=title,
        border_style=panel_color,
        padding=(1, 2)
    )
