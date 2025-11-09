"""
UAV 面板模块

负责生成单个无人机的监控面板，包括：
- DJI OSD 数据（GPS、电池、速度、姿态等）
- 实时频率追踪
- 离线状态检测
- 航点任务进度（通过文件共享）
- IVAS 日志显示

重构后设计（Linus "Good Taste"）：
- 数据聚合：UAVState 统一管理所有数据源
- 单一职责：每个函数只负责一个显示区域
- 清晰数据流：构建状态 → 渲染 UI（无重复数据获取）
"""
import time
from typing import Dict, Any
from rich.panel import Panel
from rich.table import Table
from rich.console import Group

from ..state import UAVState


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


def create_waypoint_progress_bar(current: int, total: int) -> str:
    """
    创建航点进度条（类似电量条）

    Args:
        current: 当前航点序号 (1-based, 0表示准备中)
        total: 总航点数

    Returns:
        带颜色的进度条字符串

    Example:
        >>> create_waypoint_progress_bar(3, 10)
        '[bright_green]██[/bright_green][bright_yellow]█[/bright_yellow][dim]░░░░░░░[/dim] [bright_cyan][3/10][/bright_cyan]'

        显示效果：███░░░░░░░ [3/10]
                  ↑  ↑ ↑
                  绿 黄 灰
    """
    if total == 0:
        return "[dim]暂无任务[/dim]"

    # 限制当前航点在有效范围内
    current = max(0, min(current, total))

    # 已完成的航点（绿色）
    completed = current - 1 if current > 0 else 0
    completed_bar = f"[bright_green]{'█' * completed}[/bright_green]" if completed > 0 else ""

    # 当前航点（黄色）- 只在 current > 0 时显示
    current_bar = f"[bright_yellow]█[/bright_yellow]" if current > 0 else ""

    # 未完成的航点（灰色）
    remaining = total - current
    remaining_bar = f"[dim]{'░' * remaining}[/dim]" if remaining > 0 else ""

    # 数字显示
    progress_text = f"[bright_cyan][{current}/{total}][/bright_cyan]"

    return f"{completed_bar}{current_bar}{remaining_bar} {progress_text}"


def create_uav_panel(
    uav_client: Dict[str, Any],
    config: Dict[str, str],
    elapsed: int,
    offline_timeout: float = 2.0,
    ivas_adapter=None
) -> Panel:
    """
    为单个无人机创建实时监控面板

    重构后的三阶段设计：
    1. 数据聚合：构建 UAVState 快照（所有数据获取逻辑集中在一处）
    2. UI 渲染：调用辅助函数构建各个显示区域（单一职责）
    3. 面板包装：使用 UAVState 的样式方法（消除重复条件判断）

    UI 布局改进：
    - IVAS 日志显示在主表格下方（而非表格右列）
    - 宽度与主表格一致，避免左侧空白

    Args:
        uav_client: 无人机客户端数据 (mqtt, caller, heartbeat, connection_manager, ivas)
        config: 无人机配置 (sn, user_id, callsign)
        elapsed: 运行时间（秒）
        offline_timeout: 离线超时时间（秒）
        ivas_adapter: IVAS 适配器实例（可选，用于显示IVAS日志）

    Returns:
        Rich Panel 对象
    """
    # ========== 阶段 1: 构建状态快照（数据聚合）==========
    state = UAVState.from_uav_client(uav_client, config, elapsed, offline_timeout, ivas_adapter)

    # ========== 阶段 2: 创建 UI（只负责格式化显示）==========
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_magenta", justify="right")
    table.add_column(style="bold bright_white")

    # 分隔线函数（避免重复代码）
    def add_separator():
        table.add_row("", "[dim]" + "─" * 30 + "[/dim]")

    # 基本信息区域
    _add_basic_info(table, state, add_separator)

    # 连接状态区域
    _add_connection_status(table, state, add_separator, offline_timeout)

    # 飞行数据区域（模式、电池、位置、速度、HSI）
    _add_flight_data(table, state, add_separator)

    # 任务进度区域
    _add_mission_progress(table, state, add_separator)

    # ========== 组合内容（主表格 + IVAS 日志）==========
    # 如果有 IVAS 日志，将其显示在主表格下方（宽度一致）
    if state.ivas_logs:
        ivas_panel = _create_ivas_panel(state.ivas_logs)
        content = Group(table, ivas_panel)
    else:
        content = table

    # ========== 阶段 3: 包装面板（使用状态方法）==========
    return Panel(
        content,
        title=state.get_panel_title(),
        border_style=state.get_panel_color(),
        padding=(1, 2)
    )


# ========== 辅助函数：每个只负责一块显示逻辑 ==========


def _add_basic_info(table: Table, state: UAVState, add_separator):
    """
    基本信息区域

    显示：
    - 网关序列号
    - 无人机SN（如果有）
    - 呼号
    - 运行时间
    """
    table.add_row("网关序列号:", f"[bright_cyan]{state.sn}[/bright_cyan]")
    if state.aircraft_sn:
        table.add_row("无人机SN:", f"[bright_blue]{state.aircraft_sn}[/bright_blue]")
    table.add_row("呼号:", f"[bright_cyan]{state.callsign}[/bright_cyan]")
    table.add_row("运行时间:", f"[bright_green]{state.elapsed}[/bright_green] 秒")
    add_separator()


def _add_connection_status(table: Table, state: UAVState, add_separator, offline_timeout: float):
    """
    连接状态区域

    显示：
    - OSD 频率（带颜色）
    - 连接状态（在线/离线）
    - 心跳状态
    """
    # OSD 频率和在线状态
    freq_color = state.get_freq_color()
    table.add_row("OSD 频率:", f"[{freq_color}]{state.osd_frequency:.1f}[/{freq_color}] Hz")

    if state.is_online:
        table.add_row("连接状态:", state.get_connection_status_text())
    else:
        table.add_row("连接状态:", f"[bright_red]✗ 离线 (>{offline_timeout}s)[/bright_red]")

    add_separator()

    # 心跳状态
    table.add_row("心跳状态:", state.get_heartbeat_status_text())
    add_separator()


def _add_flight_data(table: Table, state: UAVState, add_separator):
    """
    飞行数据区域

    显示：
    - 飞行模式（带颜色）
    - 电池电量（进度条）
    - GPS 位置（经纬度、高度）
    - 航向角
    - 速度数据（水平速度、三轴分量）
    - HSI 高度
    """
    # 飞行模式
    mode_color = state.get_mode_color()
    table.add_row("飞行模式:", f"[{mode_color}]{state.flight_mode_name}[/{mode_color}]")
    add_separator()

    # 电池电量
    if state.battery_percent is not None:
        battery_display = create_battery_bar(state.battery_percent)
        table.add_row("电池电量:", battery_display)
    else:
        table.add_row("电池电量:", "[dim]暂无数据[/dim]")

    add_separator()

    # GPS 位置数据
    lat, lon, height = state.position
    if lat is not None and lon is not None:
        table.add_row("纬度:", f"[bright_blue]{lat:.8f}[/bright_blue]°")
        table.add_row("经度:", f"[bright_blue]{lon:.8f}[/bright_blue]°")
    else:
        table.add_row("GPS 位置:", "[bright_red]无信号[/bright_red]")

    # 全局高度
    if height is not None:
        table.add_row("全局高度:", f"[bright_green]{height:.2f}[/bright_green] 米")
        if state.relative_height is not None:
            table.add_row("距起飞点高:", f"[bright_magenta]{state.relative_height:.2f}[/bright_magenta] 米")
        else:
            table.add_row("距起飞点高:", "[dim]计算中...[/dim]")
    else:
        table.add_row("全局高度:", "[dim]暂无数据[/dim]")

    # 航向角
    if state.attitude_head is not None:
        table.add_row("航向角:", f"[bright_cyan]{state.attitude_head:.2f}[/bright_cyan]°")
    else:
        table.add_row("航向角:", "[dim]暂无数据[/dim]")

    add_separator()

    # 速度数据
    h_speed, speed_x, speed_y, speed_z = state.speed
    if h_speed is not None:
        table.add_row("水平速度:", f"[bright_magenta]{h_speed:.2f}[/bright_magenta] m/s")
        if speed_x is not None and speed_y is not None and speed_z is not None:
            table.add_row("X轴速度:", f"[bright_cyan]{speed_x:.2f}[/bright_cyan] m/s")
            table.add_row("Y轴速度:", f"[bright_cyan]{speed_y:.2f}[/bright_cyan] m/s")
            table.add_row("Z轴速度:", f"[bright_cyan]{speed_z:.2f}[/bright_cyan] m/s")
    else:
        table.add_row("速度数据:", "[dim]暂无数据[/dim]")

    add_separator()

    # HSI 数据
    if state.is_hsi_ok:
        if state.local_height is not None:
            height_in_meters = state.local_height / 100.0  # 厘米转米
            table.add_row("HSI高度:", f"[bright_blue]{height_in_meters:.2f}[/bright_blue] 米 [bright_green]✓[/bright_green]")
        else:
            table.add_row("HSI高度:", "[dim]暂无数据[/dim]")
    else:
        table.add_row("HSI高度:", "[bright_yellow]传感器未激活[/bright_yellow]")


def _add_mission_progress(table: Table, state: UAVState, add_separator):
    """
    任务进度区域

    显示：
    - 航点进度条（如果有任务元数据）
    - 任务状态
    - 实时飞行数据（剩余距离、预计时间）
    """
    if not state.mission_metadata:
        return

    add_separator()

    # 从文件读取持久化的任务进度
    current_waypoint = state.mission_metadata.get('current_waypoint', 0)
    total_waypoints = state.mission_metadata.get('total_waypoints', 0)
    task_status = state.mission_metadata.get('task_status', '未知')

    # 显示航点进度条
    if total_waypoints > 0:
        waypoint_bar = create_waypoint_progress_bar(current_waypoint, total_waypoints)
        table.add_row("航点进度:", waypoint_bar)

    # 显示任务状态
    table.add_row("任务状态:", f"[bright_magenta]{task_status}[/bright_magenta]")

    # 实时飞行数据（来自 MQTT，可选显示）
    if state.flyto_progress and state.flyto_progress.get('status') == 'wayline_progress':
        remaining_distance = state.flyto_progress.get('remaining_distance')
        remaining_time = state.flyto_progress.get('remaining_time')

        # 显示实时剩余距离和时间（仅在飞行中显示）
        if remaining_distance is not None:
            table.add_row("剩余距离:", f"[bright_green]{remaining_distance:.1f}m[/bright_green]")
        if remaining_time is not None:
            table.add_row("预计时间:", f"[bright_yellow]{remaining_time:.1f}s[/bright_yellow]")


def _create_ivas_panel(logs: list) -> Panel:
    """
    创建 IVAS 日志面板（独立显示在主表格下方）

    显示最近 5 条 IVAS 日志，带时间戳和颜色分类。

    Args:
        logs: IVAS 日志列表

    Returns:
        Rich Panel 对象（宽度会自动与主表格一致）
    """
    # 创建 IVAS 日志表格
    ivas_table = Table.grid(padding=(0, 1))
    ivas_table.add_column(style="dim")

    if logs:
        for log in logs:
            time_str = time.strftime("%H:%M:%S", time.localtime(log['time']))
            log_type = log['type']
            message = log['message']

            # 根据类型选择颜色 - 前卫配色：霓虹色系
            color_map = {
                'success': 'bright_green',
                'error': 'bright_red',
                'info': 'bright_cyan'
            }
            color = color_map.get(log_type, 'bright_cyan')

            ivas_table.add_row(f"[{color}]{time_str}[/{color}] {message}")
    else:
        ivas_table.add_row("[dim]暂无日志[/dim]")

    # 使用 Panel 包装 IVAS 日志
    return Panel(
        ivas_table,
        title="[bold bright_magenta]IVAS 日志[/bold bright_magenta]",
        border_style="bright_magenta",
        padding=(0, 1),
        expand=True  # 自动扩展以匹配父容器宽度
    )
