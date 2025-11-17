#!/usr/bin/env python3
"""
无人机 Fly-to 任务 - 起飞、飞向目标点、返航

流程：
1. 连接并进入DRC模式
2. 外八解锁（3秒）
3. 上升到10米（油门+300）
4. 用户按回车确认
5. 飞向目标点 (lat: 39.0427514, lon: 117.7238255)
6. 监控飞行进度（剩余距离、时间）
7. 用户按回车触发返航
8. 悬停监控，直到 Ctrl+C 退出
"""
import sys
import os
# Add parent directory to path to allow importing djisdk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from rich.console import Console
from rich.panel import Panel

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
    'target_height': 10.0,       # 目标高度（米），必须 >= 5.0m
    'height_tolerance': 0.1,     # 高度容差（米）
    'throttle_offset': 300,      # 油门偏移量
    # Fly-to 目标点
    'target_latitude': 39.0427514,
    'target_longitude': 117.7238255,
    'target_fly_height': 100.0,  # 目标点椭球高（米）
    'max_speed': 12,  # 最大飞行速度（m/s）
}


def main():
    """主函数"""
    console.print(Panel.fit(
        "[bold cyan]🚁 无人机 Fly-to + 返航任务[/bold cyan]\n"
        f"[dim]无人机数量: {len(MISSION_CONFIG['uav_configs'])}[/dim]\n"
        f"[dim]1. 起飞到 {MISSION_CONFIG['target_height']}m[/dim]\n"
        f"[dim]2. 飞向目标点 (lat: {MISSION_CONFIG['target_latitude']}, lon: {MISSION_CONFIG['target_longitude']})[/dim]\n"
        f"[dim]3. 返航回起飞点[/dim]\n"
        f"[dim]MQTT: {MISSION_CONFIG['mqtt_config']['host']}:{MISSION_CONFIG['mqtt_config']['port']}[/dim]",
        border_style="cyan"
    ))

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
    console.print("\n[bold cyan]━━━ 步骤 2/5: 起飞到10米 ━━━[/bold cyan]")
    console.print("[yellow]⚠️  任务将自动执行：外八解锁 → 上升到10米[/yellow]")

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

        # 步骤3: 等待用户确认并发送 Fly-to 指令
        console.print("\n[bold cyan]━━━ 步骤 3/5: 飞向目标点 ━━━[/bold cyan]")
        console.print(
            f"[yellow]目标点: lat={MISSION_CONFIG['target_latitude']}, lon={MISSION_CONFIG['target_longitude']}, h={MISSION_CONFIG['target_fly_height']}m[/yellow]")
        input("\n[bold yellow]按 Enter 键开始飞向目标点...[/bold yellow]")

        # 发送 Fly-to 指令
        for runner in runners:
            mqtt = runner.mqtt
            caller = runner.caller
            callsign = runner.config['callsign']

            console.print(f"[cyan][{callsign}] 发送 Fly-to 指令...[/cyan]")
            fly_to_point(
                caller,
                latitude=MISSION_CONFIG['target_latitude'],
                longitude=MISSION_CONFIG['target_longitude'],
                height=MISSION_CONFIG['target_fly_height'],
                max_speed=MISSION_CONFIG['max_speed']
            )

        # 步骤4: 监控飞行进度
        console.print("\n[bold cyan]━━━ 步骤 4/5: 监控飞行进度 ━━━[/bold cyan]")
        console.print("[yellow]💡 按 Ctrl+C 中断监控[/yellow]\n")

        # 持续监控进度
        last_status = {}  # 记录每架无人机的上一次状态，避免重复打印
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
                                f"[bold green]✓ [{callsign}] 已到达目标点！[/bold green]")
                        elif status == 'wayline_failed':
                            console.print(
                                f"[bold red]✗ [{callsign}] 飞行失败[/bold red]")
                        elif status == 'wayline_cancel':
                            console.print(
                                f"[bold yellow]⚠ [{callsign}] 飞行取消[/bold yellow]")
                        last_status[callsign] = status
                elif status == 'wayline_progress':
                    all_done = False
                    # 打印进度信息
                    if remaining_distance is not None and remaining_time is not None:
                        console.print(
                            f"[dim]{time.strftime('%H:%M:%S')}[/dim] | "
                            f"[cyan]{callsign}[/cyan]: "
                            f"[yellow]剩余 {remaining_distance:.1f}m, {remaining_time:.1f}s[/yellow]"
                        )
                    else:
                        console.print(
                            f"[dim]{time.strftime('%H:%M:%S')}[/dim] | [{callsign}] 执行中...")
                else:
                    # 还没收到进度数据
                    all_done = False

            # 所有无人机都完成了
            if all_done:
                break

        console.print("\n[bold green]✓ 所有 Fly-to 任务完成！[/bold green]")

        # 步骤5: 等待用户确认并发送返航指令
        console.print("\n[bold cyan]━━━ 步骤 5/5: 返航 ━━━[/bold cyan]")
        input("\n[bold yellow]按 Enter 键触发返航指令...[/bold yellow]")

        # 发送返航指令
        for runner in runners:
            caller = runner.caller
            callsign = runner.config['callsign']
            console.print(f"[cyan][{callsign}] 发送返航指令...[/cyan]")
            return_home(caller)

        console.print("\n[bold green]✓ 所有无人机已触发返航[/bold green]")

        # 进入悬停监控模式
        console.print("\n[bold cyan]进入悬停监控模式[/bold cyan]")
        console.print("[yellow]💡 无人机正在返航，按 Ctrl+C 停止监控并退出[/yellow]\n")

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
