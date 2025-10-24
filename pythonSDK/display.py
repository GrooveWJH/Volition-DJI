"""
无人机实时监控 UI 显示模块
"""
from typing import Dict, Any
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn


def create_battery_bar(percent: int) -> str:
    """
    创建彩色电量条

    Args:
        percent: 电量百分比 (0-100)

    Returns:
        带颜色的电量条字符串
    """
    # 根据电量选择颜色
    if percent < 25:
        color = "red"
    elif percent < 50:
        color = "yellow"
    else:
        color = "green"

    # 创建进度条（10个字符宽度）
    filled = int(percent / 10)  # 每10%一个方块
    bar = "█" * filled + "░" * (10 - filled)

    return f"[{color}]{bar} {percent}%[/{color}]"


def create_uav_panel(uav_client: Dict[str, Any], config: Dict[str, str], elapsed: int) -> Panel:
    """
    为单个无人机创建实时监控面板

    Args:
        uav_client: 无人机客户端数据 (mqtt, caller, heartbeat)
        config: 无人机配置 (sn, user_id, callsign)
        elapsed: 运行时间（秒）

    Returns:
        Rich Panel 对象
    """
    mqtt = uav_client['mqtt']
    heartbeat = uav_client['heartbeat']
    uav_id = uav_client['id']

    # 获取数据
    lat, lon, height = mqtt.get_position()
    relative_height = mqtt.get_relative_height()
    attitude_head = mqtt.get_attitude_head()
    h_speed, speed_x, speed_y, speed_z = mqtt.get_speed()
    local_height = mqtt.get_local_height()
    is_hsi_ok = mqtt.is_local_height_ok()
    battery_percent = mqtt.get_battery_percent()
    is_heartbeat_alive = heartbeat and heartbeat.is_alive()

    # 创建表格
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column(style="bold white")

    # 分割线函数
    def add_separator():
        table.add_row("", "[dim]" + "─" * 30 + "[/dim]")

    # 基本信息
    table.add_row("序列号:", f"[yellow]{config['sn']}[/yellow]")
    table.add_row("呼号:", f"[yellow]{config['callsign']}[/yellow]")
    table.add_row("运行时间:", f"[green]{elapsed}[/green] 秒")
    add_separator()

    # 心跳状态
    heartbeat_status = "[green]✓ 正常[/green]" if is_heartbeat_alive else "[red]✗ 异常[/red]"
    table.add_row("心跳状态:", heartbeat_status)
    add_separator()

    # 电池电量
    if battery_percent is not None:
        battery_display = create_battery_bar(battery_percent)
        table.add_row("电池电量:", battery_display)
    else:
        table.add_row("电池电量:", "[dim]暂无数据[/dim]")

    add_separator()

    # GPS 位置数据（经纬度）
    if lat is not None and lon is not None:
        table.add_row("纬度:", f"[green]{lat:.8f}[/green]°")
        table.add_row("经度:", f"[green]{lon:.8f}[/green]°")
    else:
        table.add_row("GPS 位置:", "[red]无信号[/red]")

    # 全局高度（总是存在）
    if height is not None:
        table.add_row("全局高度:", f"[green]{height:.2f}[/green] 米")
        # 距起飞点高度
        if relative_height is not None:
            table.add_row("距起飞点高:", f"[cyan]{relative_height:.2f}[/cyan] 米")
        else:
            table.add_row("距起飞点高:", "[dim]计算中...[/dim]")
    else:
        table.add_row("全局高度:", "[dim]暂无数据[/dim]")

    # 航向角
    if attitude_head is not None:
        table.add_row("航向角:", f"[green]{attitude_head:.2f}[/green]°")
    else:
        table.add_row("航向角:", "[dim]暂无数据[/dim]")

    add_separator()

    # 速度数据
    if h_speed is not None:
        table.add_row("水平速度:", f"[green]{h_speed:.2f}[/green] m/s")
        if speed_x is not None and speed_y is not None and speed_z is not None:
            table.add_row("X轴速度:", f"[cyan]{speed_x:.2f}[/cyan] m/s")
            table.add_row("Y轴速度:", f"[cyan]{speed_y:.2f}[/cyan] m/s")
            table.add_row("Z轴速度:", f"[cyan]{speed_z:.2f}[/cyan] m/s")
    else:
        table.add_row("速度数据:", "[dim]暂无数据[/dim]")

    add_separator()

    # HSI 数据（HSI高度，原始单位：厘米）
    if is_hsi_ok:
        # 传感器正常，显示数值（转换为米）
        if local_height is not None:
            height_in_meters = local_height / 100.0  # 厘米转米
            table.add_row("HSI高度:", f"[green]{height_in_meters:.2f}[/green] 米 [green]✓[/green]")
        else:
            table.add_row("HSI高度:", "[dim]暂无数据[/dim]")
    else:
        # 传感器未激活（忽略 60000 等无效值）
        table.add_row("HSI高度:", "[yellow]传感器未激活[/yellow]")

    # 面板标题和边框颜色
    panel_color = "green" if is_heartbeat_alive else "red"
    title = f"[bold]无人机 #{uav_id}[/bold]"

    return Panel(
        table,
        title=title,
        border_style=panel_color,
        padding=(1, 2)
    )
