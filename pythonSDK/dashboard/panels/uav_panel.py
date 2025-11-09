"""
UAV 面板模块

负责生成单个无人机的监控面板，包括：
- DJI OSD 数据（GPS、电池、速度、姿态等）
- 实时频率追踪
- 离线状态检测
- 航点任务进度（通过文件共享）
- IVAS 日志显示
"""
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from rich.panel import Panel
from rich.table import Table


def create_battery_bar(percent: int) -> str:
    """
    创建彩色电量条

    Args:
        percent: 电量百分比 (0-100)

    Returns:
        带颜色的电量条字符串
    """
    # 根据电量选择颜色 - 前卫配色：霓虹色系
    if percent < 25:
        color = "bright_red"
    elif percent < 50:
        color = "bright_yellow"
    else:
        color = "bright_green"

    # 创建进度条（10个字符宽度）
    filled = int(percent / 10)  # 每10%一个方块
    bar = "█" * filled + "░" * (10 - filled)

    return f"[{color}]{bar} {percent}%[/{color}]"


def create_uav_panel(
    uav_client: Dict[str, Any],
    config: Dict[str, str],
    elapsed: int,
    offline_timeout: float = 2.0,
    ivas_adapter=None
) -> Panel:
    """
    为单个无人机创建实时监控面板（包含频率、离线状态和IVAS日志）

    Args:
        uav_client: 无人机客户端数据 (mqtt, caller, heartbeat, ivas)
        config: 无人机配置 (sn, user_id, callsign)
        elapsed: 运行时间（秒）
        offline_timeout: 离线超时时间（秒）
        ivas_adapter: IVAS 适配器实例（可选，用于显示IVAS日志）

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
    flight_mode_name = mqtt.get_flight_mode_name()
    aircraft_sn = mqtt.get_aircraft_sn()

    # 新增：获取频率和在线状态
    osd_frequency = mqtt.get_osd_frequency()
    is_online = mqtt.is_online(timeout=offline_timeout)

    # 创建表格 - 前卫配色：洋红标题 + 亮白数据
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_magenta", justify="right")
    table.add_column(style="bold bright_white")

    # 分割线函数
    def add_separator():
        table.add_row("", "[dim]" + "─" * 30 + "[/dim]")

    # 基本信息 - 前卫配色：亮青色数据
    table.add_row("网关序列号:", f"[bright_cyan]{config['sn']}[/bright_cyan]")
    if aircraft_sn:
        table.add_row("无人机SN:", f"[bright_blue]{aircraft_sn}[/bright_blue]")
    table.add_row("呼号:", f"[bright_cyan]{config['callsign']}[/bright_cyan]")
    table.add_row("运行时间:", f"[bright_green]{elapsed}[/bright_green] 秒")
    add_separator()

    # OSD 频率和在线状态 - 前卫配色：霓虹色系
    if is_online:
        freq_color = "bright_green" if osd_frequency >= 90 else "bright_yellow" if osd_frequency >= 50 else "bright_red"
        table.add_row("OSD 频率:", f"[{freq_color}]{osd_frequency:.1f}[/{freq_color}] Hz")
        table.add_row("连接状态:", "[bright_green]✓ 在线[/bright_green]")
    else:
        table.add_row("OSD 频率:", f"[dim]{osd_frequency:.1f}[/dim] Hz")
        table.add_row("连接状态:", f"[bright_red]✗ 离线 (>{offline_timeout}s)[/bright_red]")
    add_separator()

    # 心跳状态 - 前卫配色：霓虹绿/红
    heartbeat_status = "[bright_green]✓ 正常[/bright_green]" if is_heartbeat_alive else "[bright_red]✗ 异常[/bright_red]"
    table.add_row("心跳状态:", heartbeat_status)
    add_separator()

    # 飞行模式 - 前卫配色：多彩霓虹色系
    mode_color = "bright_green"
    if flight_mode_name in ["自动返航", "自动降落", "强制降落"]:
        mode_color = "bright_yellow"
    elif flight_mode_name in ["未连接", "未知"]:
        mode_color = "bright_red"
    elif flight_mode_name in ["手动飞行", "虚拟摇杆状态", "指令飞行"]:
        mode_color = "bright_cyan"

    table.add_row("飞行模式:", f"[{mode_color}]{flight_mode_name}[/{mode_color}]")
    add_separator()

    # 电池电量
    if battery_percent is not None:
        battery_display = create_battery_bar(battery_percent)
        table.add_row("电池电量:", battery_display)
    else:
        table.add_row("电池电量:", "[dim]暂无数据[/dim]")

    add_separator()

    # GPS 位置数据（经纬度）- 前卫配色：亮蓝色坐标
    if lat is not None and lon is not None:
        table.add_row("纬度:", f"[bright_blue]{lat:.8f}[/bright_blue]°")
        table.add_row("经度:", f"[bright_blue]{lon:.8f}[/bright_blue]°")
    else:
        table.add_row("GPS 位置:", "[bright_red]无信号[/bright_red]")

    # 全局高度 - 前卫配色：亮绿色高度 + 亮洋红色相对高度
    if height is not None:
        table.add_row("全局高度:", f"[bright_green]{height:.2f}[/bright_green] 米")
        if relative_height is not None:
            table.add_row("距起飞点高:", f"[bright_magenta]{relative_height:.2f}[/bright_magenta] 米")
        else:
            table.add_row("距起飞点高:", "[dim]计算中...[/dim]")
    else:
        table.add_row("全局高度:", "[dim]暂无数据[/dim]")

    # 航向角 - 前卫配色：亮青色
    if attitude_head is not None:
        table.add_row("航向角:", f"[bright_cyan]{attitude_head:.2f}[/bright_cyan]°")
    else:
        table.add_row("航向角:", "[dim]暂无数据[/dim]")

    add_separator()

    # 速度数据 - 前卫配色：亮洋红色主速度 + 亮青色分量
    if h_speed is not None:
        table.add_row("水平速度:", f"[bright_magenta]{h_speed:.2f}[/bright_magenta] m/s")
        if speed_x is not None and speed_y is not None and speed_z is not None:
            table.add_row("X轴速度:", f"[bright_cyan]{speed_x:.2f}[/bright_cyan] m/s")
            table.add_row("Y轴速度:", f"[bright_cyan]{speed_y:.2f}[/bright_cyan] m/s")
            table.add_row("Z轴速度:", f"[bright_cyan]{speed_z:.2f}[/bright_cyan] m/s")
    else:
        table.add_row("速度数据:", "[dim]暂无数据[/dim]")

    add_separator()

    # HSI 数据（HSI高度，原始单位：厘米）- 前卫配色：亮蓝色
    if is_hsi_ok:
        if local_height is not None:
            height_in_meters = local_height / 100.0  # 厘米转米
            table.add_row("HSI高度:", f"[bright_blue]{height_in_meters:.2f}[/bright_blue] 米 [bright_green]✓[/bright_green]")
        else:
            table.add_row("HSI高度:", "[dim]暂无数据[/dim]")
    else:
        table.add_row("HSI高度:", "[bright_yellow]传感器未激活[/bright_yellow]")

    # ========== 航点任务进度显示（进程间通信：文件共享）==========
    # 从共享文件读取任务元数据（总航点数等）
    mission_metadata = None
    try:
        mission_state_file = Path('/tmp/djisdk_mission_state.json')
        if mission_state_file.exists():
            with open(mission_state_file, 'r') as f:
                mission_state = json.load(f)
            mission_metadata = mission_state.get(config.get('callsign'))
    except Exception:
        pass  # 文件读取失败时静默忽略（优雅降级）

    # 从 MQTT 读取实时航点进度数据
    flyto_progress = mqtt.get_flyto_progress()
    flyto_status = flyto_progress.get('status') if flyto_progress else None

    # 只有在执行航线任务时才显示（wayline_progress 状态）
    if flyto_status == 'wayline_progress':
        add_separator()

        # 提取进度数据
        way_point_index = flyto_progress.get('way_point_index')
        remaining_distance = flyto_progress.get('remaining_distance')
        remaining_time = flyto_progress.get('remaining_time')
        total_waypoints = mission_metadata.get('total_waypoints') if mission_metadata else None

        # 显示航点进度
        if way_point_index is not None:
            if total_waypoints:
                # 有总数：显示 "3/10" 格式
                table.add_row("航点进度:", f"[bright_cyan]{way_point_index}/{total_waypoints}[/bright_cyan]")
            else:
                # 无总数：只显示当前航点索引（优雅降级）
                table.add_row("当前航点:", f"[bright_cyan]{way_point_index}[/bright_cyan]")

        # 显示剩余距离
        if remaining_distance is not None:
            table.add_row("剩余距离:", f"[bright_green]{remaining_distance:.1f}m[/bright_green]")

        # 显示预计时间
        if remaining_time is not None:
            table.add_row("预计时间:", f"[bright_yellow]{remaining_time:.1f}s[/bright_yellow]")

        # 显示飞行状态
        table.add_row("飞行状态:", "[bright_magenta]航线飞行中[/bright_magenta]")

    # IVAS 日志区域（使用独立的矩形框）
    if ivas_adapter:
        add_separator()

        # 创建IVAS日志的独立表格（带边框）
        ivas_table = Table.grid(padding=(0, 1))
        ivas_table.add_column(style="dim")

        logs = ivas_adapter.get_recent_logs(5)
        if logs:
            for log in logs:
                time_str = time.strftime("%H:%M:%S", time.localtime(log['time']))
                log_type = log['type']
                message = log['message']

                # 根据类型选择颜色 - 前卫配色：霓虹色系
                if log_type == 'success':
                    color = 'bright_green'
                elif log_type == 'error':
                    color = 'bright_red'
                else:  # 'info'
                    color = 'bright_cyan'

                ivas_table.add_row(f"[{color}]{time_str}[/{color}] {message}")
        else:
            ivas_table.add_row("[dim]暂无日志[/dim]")

        # 使用Panel包装IVAS日志，创建矩形框 - 前卫配色：亮洋红边框
        ivas_panel = Panel(
            ivas_table,
            title="[bold bright_magenta]IVAS 日志[/bold bright_magenta]",
            border_style="bright_magenta",
            padding=(0, 1),
            expand=False
        )

        # 将整个IVAS Panel作为一行添加到主表格（跨两列）
        table.add_row("", ivas_panel)

    # 面板标题和边框颜色（离线状态优先显示）- 前卫配色：霓虹色系边框
    # 新增：检测重连状态
    connection_manager = uav_client.get('connection_manager')
    if connection_manager and connection_manager.is_reconnecting():
        # 重连中：黄色边框
        panel_color = "bright_yellow"
        title = f"[bold]无人机 #{uav_id}[/bold] [bright_yellow]🔄 重连中...[/bright_yellow]"
    elif not is_online:
        panel_color = "bright_red"
        title = f"[bold]无人机 #{uav_id}[/bold] [bright_red]● 离线[/bright_red]"
    elif not is_heartbeat_alive:
        panel_color = "bright_yellow"
        title = f"[bold]无人机 #{uav_id}[/bold] [bright_yellow]⚠ 心跳异常[/bright_yellow]"
    else:
        panel_color = "bright_magenta"
        title = f"[bold]无人机 #{uav_id}[/bold]"

    return Panel(
        table,
        title=title,
        border_style=panel_color,
        padding=(1, 2)
    )
