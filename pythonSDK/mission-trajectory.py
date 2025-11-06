#!/usr/bin/env python3
"""
无人机轨迹任务 - 起飞、依次飞向所有航点、返航

流程：
1. 连接并进入DRC模式
2. 外八解锁（1秒）
3. 上升到指定高度
4. 读取航点数据（Trajectory/uav1.json）
5. 依次飞向每个航点（id 1 → 2 → 3 → ... → N）
6. 监控飞行进度（剩余距离、时间）
7. 完成最后一个航点后自动返航
8. 悬停监控，直到 Ctrl+C 退出
"""
import time
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from djisdk import (
    setup_multiple_drc_connections,
    send_stick_control,
    run_parallel_missions,
    cleanup_missions,
    fly_to_point,
    return_home,
    create_takeoff_mission,
)

console = Console()

# ========== 配置参数 ==========
MISSION_CONFIG = {
    # 无人机配置
    'uav_configs': [
        {'sn': '9N9CN2J0012CXY', 'user_id': 'pilot1', 'callsign': 'Alpha'},
        # {'sn': '9N9CN8400164WH', 'user_id': 'pilot2', 'callsign': 'Bravo'},
        # {'sn': '9N9CN180011TJN', 'user_id': 'pilot3', 'callsign': 'Charlie'},
    ],
    # MQTT配置
    'mqtt_config': {
        'host': 'grve.me',
        'port': 1883,
        'username': 'dji',
        'password': 'lab605605'
    },
    # DRC配置
    'osd_frequency': 100,
    'hsi_frequency': 10,
    'heartbeat_interval': 0.2,
    # 起飞参数
    'target_height': 30.0,       # 目标高度（米），必须 >= 5.0m
    'height_tolerance': 1.0,     # 高度容差（米）
    'throttle_offset': 300,      # 油门偏移量
    # 航点参数
    'trajectory_file': 'Trajectory/uav1.json',  # 航点文件路径
    'waypoint_height': 100.0,    # 航点飞行高度（椭球高，米）
    'max_speed': 12,             # 最大飞行速度（m/s）
}


def load_trajectory(filepath: str) -> list:
    """
    加载航点数据

    Args:
        filepath: 航点文件路径

    Returns:
        航点列表，每个航点包含 id, lat, lon

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"航点文件不存在: {filepath}")

    with open(path, 'r', encoding='utf-8') as f:
        waypoints = json.load(f)

    if not isinstance(waypoints, list) or len(waypoints) == 0:
        raise ValueError(f"航点数据格式错误或为空: {filepath}")

    # 验证航点数据格式
    for i, wp in enumerate(waypoints):
        if 'lat' not in wp or 'lon' not in wp:
            raise ValueError(f"航点 {i+1} 缺少 lat 或 lon 字段: {wp}")

    return waypoints


def display_trajectory_info(waypoints: list, height: float):
    """
    显示航点信息表格

    Args:
        waypoints: 航点列表
        height: 飞行高度
    """
    table = Table(title="[bold cyan]📍 航点列表[/bold cyan]", show_header=True)
    table.add_column("序号", style="cyan", width=6)
    table.add_column("ID", style="yellow", width=6)
    table.add_column("纬度 (Lat)", style="green", width=12)
    table.add_column("经度 (Lon)", style="green", width=12)
    table.add_column("高度 (m)", style="magenta", width=10)

    for i, wp in enumerate(waypoints, 1):
        table.add_row(
            str(i),
            str(wp.get('id', '-')),
            f"{wp['lat']:.7f}",
            f"{wp['lon']:.7f}",
            f"{height:.1f}"
        )

    console.print("\n")
    console.print(table)
    console.print("\n")


def fly_trajectory_sequence(runners, waypoints, height, max_speed):
    """
    依次飞向所有航点

    Args:
        runners: MissionRunner 列表
        waypoints: 航点列表
        height: 飞行高度（米）
        max_speed: 最大速度（m/s）
    """
    total_waypoints = len(waypoints)

    for wp_index, waypoint in enumerate(waypoints, 1):
        wp_id = waypoint.get('id', wp_index)
        lat = waypoint['lat']
        lon = waypoint['lon']

        # 显示当前航点信息
        console.print(
            f"\n[bold cyan]━━━ 航点 {wp_index}/{total_waypoints} (ID: {wp_id}) ━━━[/bold cyan]")
        console.print(
            f"[yellow]目标: lat={lat:.7f}, lon={lon:.7f}, h={height:.1f}m[/yellow]")

        # 发送 Fly-to 指令
        for runner in runners:
            caller = runner.caller
            callsign = runner.config['callsign']
            console.print(f"[cyan][{callsign}] 飞向航点 {wp_index}...[/cyan]")
            fly_to_point(caller, latitude=lat, longitude=lon,
                         height=height, max_speed=max_speed)

        # 监控飞行进度
        console.print(f"[dim]监控飞行进度...[/dim]\n")
        last_status = {}

        while True:
            time.sleep(1.0)

            all_done = True
            for runner in runners:
                mqtt = runner.mqtt
                callsign = runner.config['callsign']

                # 获取进度数据
                progress = mqtt.get_flyto_progress()
                status = progress.get('status')
                remaining_distance = progress.get('remaining_distance')
                remaining_time = progress.get('remaining_time')

                # 检查是否完成
                if status in ['wayline_ok', 'wayline_failed', 'wayline_cancel']:
                    # 只在状态变化时打印
                    if last_status.get(callsign) != status:
                        if status == 'wayline_ok':
                            console.print(
                                f"[bold green]✓ [{callsign}] 已到达航点 {wp_index}！[/bold green]")
                        elif status == 'wayline_failed':
                            console.print(
                                f"[bold red]✗ [{callsign}] 飞向航点 {wp_index} 失败[/bold red]")
                        elif status == 'wayline_cancel':
                            console.print(
                                f"[bold yellow]⚠ [{callsign}] 飞向航点 {wp_index} 取消[/bold yellow]")
                        last_status[callsign] = status
                elif status == 'wayline_progress':
                    all_done = False
                    # 打印进度信息
                    if remaining_distance is not None and remaining_time is not None:
                        console.print(
                            f"[dim]{time.strftime('%H:%M:%S')}[/dim] | "
                            f"[cyan]{callsign}[/cyan]: "
                            f"[yellow]航点 {wp_index} - 剩余 {remaining_distance:.1f}m, {remaining_time:.1f}s[/yellow]"
                        )
                    else:
                        console.print(
                            f"[dim]{time.strftime('%H:%M:%S')}[/dim] | [{callsign}] 执行中...")
                else:
                    # 还没收到进度数据
                    all_done = False

            # 所有无人机都完成了当前航点
            if all_done:
                break

        console.print(
            f"[bold green]✓ 航点 {wp_index}/{total_waypoints} 完成[/bold green]")

        # 悬停等待飞控状态稳定（除了最后一个航点）
        if wp_index < total_waypoints:
            wait_time = 5  # 增加到 5 秒，让飞控完全稳定
            console.print(f"[dim]悬停等待 {wait_time} 秒，飞控状态稳定中...[/dim]")
            for _ in range(wait_time * 10):  # wait_time 秒 @ 10Hz
                for runner in runners:
                    send_stick_control(runner.mqtt)
                time.sleep(0.1)


def main():
    """主函数"""
    console.print(Panel.fit(
        "[bold cyan]🚁 无人机轨迹飞行任务[/bold cyan]\n"
        f"[dim]无人机数量: {len(MISSION_CONFIG['uav_configs'])}[/dim]\n"
        f"[dim]1. 起飞到 {MISSION_CONFIG['target_height']}m[/dim]\n"
        f"[dim]2. 依次飞向所有航点[/dim]\n"
        f"[dim]3. 自动返航回起飞点[/dim]\n"
        f"[dim]航点文件: {MISSION_CONFIG['trajectory_file']}[/dim]\n"
        f"[dim]MQTT: {MISSION_CONFIG['mqtt_config']['host']}:{MISSION_CONFIG['mqtt_config']['port']}[/dim]",
        border_style="cyan"
    ))

    # 步骤0: 加载航点数据
    console.print("\n[bold cyan]━━━ 步骤 0/5: 加载航点数据 ━━━[/bold cyan]")
    try:
        waypoints = load_trajectory(MISSION_CONFIG['trajectory_file'])
        console.print(
            f"[green]✓ 成功加载 {len(waypoints)} 个航点[/green]")
        display_trajectory_info(
            waypoints, MISSION_CONFIG['waypoint_height'])
    except Exception as e:
        console.print(f"[red]✗ 加载航点失败: {e}[/red]")
        return 1

    # 用户确认
    input(
        f"\n[bold yellow]即将执行 {len(waypoints)} 个航点的飞行任务，按 Enter 继续...[/bold yellow]\n")

    # 步骤1: 连接所有无人机
    console.print("\n[bold cyan]━━━ 步骤 1/5: 并行连接无人机 ━━━[/bold cyan]")
    try:
        connections = setup_multiple_drc_connections(
            uav_configs=MISSION_CONFIG['uav_configs'],
            mqtt_config=MISSION_CONFIG['mqtt_config'],
            osd_frequency=MISSION_CONFIG['osd_frequency'],
            hsi_frequency=MISSION_CONFIG['hsi_frequency'],
            heartbeat_interval=MISSION_CONFIG['heartbeat_interval']
        )
    except Exception as e:
        console.print(f"[red]✗ 连接失败: {e}[/red]")
        return 1

    # 步骤2: 执行起飞任务
    console.print("\n[bold cyan]━━━ 步骤 2/5: 起飞到指定高度 ━━━[/bold cyan]")
    console.print(
        f"[yellow]⚠️  任务将自动执行：外八解锁 → 上升到 {MISSION_CONFIG['target_height']}m[/yellow]")

    # 创建起飞任务函数（自动验证参数）
    takeoff_mission = create_takeoff_mission(
        target_height=MISSION_CONFIG['target_height'],
        height_tolerance=MISSION_CONFIG['height_tolerance'],
        throttle_offset=MISSION_CONFIG['throttle_offset']
    )

    runners = None
    try:
        runners = run_parallel_missions(
            connections=connections,
            mission_func=takeoff_mission,
            uav_configs=MISSION_CONFIG['uav_configs'],
            countdown=3
        )

        console.print("\n[bold green]✓ 所有无人机已完成起飞任务[/bold green]")

        # 步骤3: 依次飞向所有航点
        console.print("\n[bold cyan]━━━ 步骤 3/5: 依次飞向所有航点 ━━━[/bold cyan]")
        console.print(
            f"[yellow]总航点数: {len(waypoints)}，飞行高度: {MISSION_CONFIG['waypoint_height']}m[/yellow]\n")

        fly_trajectory_sequence(
            runners=runners,
            waypoints=waypoints,
            height=MISSION_CONFIG['waypoint_height'],
            max_speed=MISSION_CONFIG['max_speed']
        )

        console.print(
            f"\n[bold green]✓ 所有航点任务完成！({len(waypoints)} 个航点)[/bold green]")

        # 步骤4: 自动返航
        console.print("\n[bold cyan]━━━ 步骤 4/5: 自动返航 ━━━[/bold cyan]")
        console.print("[yellow]正在发送返航指令...[/yellow]")

        # 发送返航指令
        for runner in runners:
            caller = runner.caller
            callsign = runner.config['callsign']
            console.print(f"[cyan][{callsign}] 发送返航指令...[/cyan]")
            return_home(caller)

        console.print("\n[bold green]✓ 所有无人机已触发返航[/bold green]")

        # 步骤5: 悬停监控
        console.print("\n[bold cyan]━━━ 步骤 5/5: 返航监控 ━━━[/bold cyan]")
        console.print(
            "[yellow]💡 无人机正在返航，按 Ctrl+C 停止监控并退出[/yellow]\n")

        while True:
            time.sleep(1.0)

            # 打印所有无人机的高度
            height_info = []
            for runner in runners:
                mqtt = runner.mqtt
                callsign = runner.config['callsign']
                h = mqtt.get_relative_height()

                if h is not None:
                    height_info.append(
                        f"[cyan]{callsign}[/cyan]: [green]{h:.2f}m[/green]")
                else:
                    height_info.append(
                        f"[cyan]{callsign}[/cyan]: [dim]N/A[/dim]")

                # 持续发送悬停指令
                send_stick_control(mqtt)

            console.print(
                f"[dim]{time.strftime('%H:%M:%S')}[/dim] | " + " | ".join(height_info))

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ 收到中断信号 (Ctrl+C)[/yellow]")
    finally:
        # 清理资源
        if runners:
            cleanup_missions(runners, hover_duration=1.0)

    return 0


if __name__ == '__main__':
    exit(main())
