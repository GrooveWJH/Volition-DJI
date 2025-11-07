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

现在使用 djisdk.tasks.trajectory 模块简化实现。
"""
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from djisdk import (
    setup_multiple_drc_connections,
    send_stick_control,
    run_parallel_missions,
    cleanup_missions,
    return_home,
    create_takeoff_mission,
    load_trajectory,
    fly_trajectory_sequence,
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
    'hover_between_waypoints': 5.0,  # 航点间悬停时间（秒）
}


def display_trajectory_info(waypoints: list, height: float):
    """
    显示航点信息表格

    Args:
        waypoints: 航点列表
        height: 飞行高度
    """
    table = Table(title="[bold bright_cyan]📍 航点列表[/bold bright_cyan]", show_header=True)
    table.add_column("序号", style="bright_cyan", width=6)
    table.add_column("ID", style="bright_yellow", width=6)
    table.add_column("纬度 (Lat)", style="bright_green", width=12)
    table.add_column("经度 (Lon)", style="bright_green", width=12)
    table.add_column("高度 (m)", style="bright_magenta", width=10)

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


def main():
    """主函数"""
    console.print(Panel.fit(
        "[bold bright_cyan]🚁 无人机轨迹飞行任务[/bold bright_cyan]\n"
        f"[dim]无人机数量: {len(MISSION_CONFIG['uav_configs'])}[/dim]\n"
        f"[dim]1. 起飞到 {MISSION_CONFIG['target_height']}m[/dim]\n"
        f"[dim]2. 依次飞向所有航点[/dim]\n"
        f"[dim]3. 自动返航回起飞点[/dim]\n"
        f"[dim]航点文件: {MISSION_CONFIG['trajectory_file']}[/dim]\n"
        f"[dim]MQTT: {MISSION_CONFIG['mqtt_config']['host']}:{MISSION_CONFIG['mqtt_config']['port']}[/dim]",
        border_style="bright_cyan"
    ))

    # 步骤0: 加载航点数据（使用 SDK 函数）
    console.print("\n[bold bright_cyan]━━━ 步骤 0/5: 加载航点数据 ━━━[/bold bright_cyan]")
    try:
        waypoints = load_trajectory(MISSION_CONFIG['trajectory_file'])
        console.print(
            f"[bright_green]✓ 成功加载 {len(waypoints)} 个航点[/bright_green]")
        display_trajectory_info(
            waypoints, MISSION_CONFIG['waypoint_height'])
    except Exception as e:
        console.print(f"[bright_red]✗ 加载航点失败: {e}[/bright_red]")
        return 1

    # 用户确认
    input(
        f"\n[bold bright_yellow]即将执行 {len(waypoints)} 个航点的飞行任务，按 Enter 继续...[/bold bright_yellow]\n")

    # 步骤1: 连接所有无人机
    console.print("\n[bold bright_cyan]━━━ 步骤 1/5: 并行连接无人机 ━━━[/bold bright_cyan]")
    try:
        connections = setup_multiple_drc_connections(
            uav_configs=MISSION_CONFIG['uav_configs'],
            mqtt_config=MISSION_CONFIG['mqtt_config'],
            osd_frequency=MISSION_CONFIG['osd_frequency'],
            hsi_frequency=MISSION_CONFIG['hsi_frequency'],
            heartbeat_interval=MISSION_CONFIG['heartbeat_interval']
        )
    except Exception as e:
        console.print(f"[bright_red]✗ 连接失败: {e}[/bright_red]")
        return 1

    # 步骤2: 执行起飞任务
    console.print("\n[bold bright_cyan]━━━ 步骤 2/5: 起飞到指定高度 ━━━[/bold bright_cyan]")
    console.print(
        f"[bright_yellow]⚠️  任务将自动执行：外八解锁 → 上升到 {MISSION_CONFIG['target_height']}m[/bright_yellow]")

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

        console.print("\n[bold bright_green]✓ 所有无人机已完成起飞任务[/bold bright_green]")

        # 步骤3: 依次飞向所有航点（使用 SDK 函数）
        console.print("\n[bold bright_cyan]━━━ 步骤 3/5: 依次飞向所有航点 ━━━[/bold bright_cyan]")
        console.print(
            f"[bright_yellow]总航点数: {len(waypoints)}，飞行高度: {MISSION_CONFIG['waypoint_height']}m[/bright_yellow]\n")

        success = fly_trajectory_sequence(
            runners=runners,
            waypoints=waypoints,
            height=MISSION_CONFIG['waypoint_height'],
            max_speed=MISSION_CONFIG['max_speed'],
            hover_between_waypoints=MISSION_CONFIG['hover_between_waypoints'],
            show_progress=True
        )

        if success:
            console.print(
                f"\n[bold bright_green]✓ 所有航点任务完成！({len(waypoints)} 个航点)[/bold bright_green]")
        else:
            console.print(
                f"\n[bold bright_yellow]⚠ 航点任务完成，但有部分失败[/bold bright_yellow]")

        # 步骤4: 自动返航
        console.print("\n[bold bright_cyan]━━━ 步骤 4/5: 自动返航 ━━━[/bold bright_cyan]")
        console.print("[bright_yellow]正在发送返航指令...[/bright_yellow]")

        # 发送返航指令
        for runner in runners:
            caller = runner.caller
            callsign = runner.config['callsign']
            console.print(f"[bright_cyan][{callsign}] 发送返航指令...[/bright_cyan]")
            return_home(caller)

        console.print("\n[bold bright_green]✓ 所有无人机已触发返航[/bold bright_green]")

        # 步骤5: 悬停监控
        console.print("\n[bold bright_cyan]━━━ 步骤 5/5: 返航监控 ━━━[/bold bright_cyan]")
        console.print(
            "[bright_yellow]💡 无人机正在返航，按 Ctrl+C 停止监控并退出[/bright_yellow]\n")

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
                        f"[bright_cyan]{callsign}[/bright_cyan]: [bright_green]{h:.2f}m[/bright_green]")
                else:
                    height_info.append(
                        f"[bright_cyan]{callsign}[/bright_cyan]: [dim]N/A[/dim]")

                # 持续发送悬停指令
                send_stick_control(mqtt)

            console.print(
                f"[dim]{time.strftime('%H:%M:%S')}[/dim] | " + " | ".join(height_info))

    except KeyboardInterrupt:
        console.print("\n[bright_yellow]⚠ 收到中断信号 (Ctrl+C)[/bright_yellow]")
    finally:
        # 清理资源
        if runners:
            cleanup_missions(runners, hover_duration=1.0)

    return 0


if __name__ == '__main__':
    exit(main())
