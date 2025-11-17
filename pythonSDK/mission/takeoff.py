#!/usr/bin/env python3
"""
无人机自动起飞任务 - 上升到10米

流程：
1. 连接并进入DRC模式
2. 外八解锁（3秒）
3. 上升到10米（油门+300）
4. 监控 relative_height
5. 到达 9.9m 时油门归中
6. 持续悬停监控，直到 Ctrl+C 退出

支持同时控制多架无人机，使用 djisdk.mission 模块简化实现
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
    'target_height': 100.0,       # 目标高度（米），必须 >= 5.0m
    'height_tolerance': 1.0,     # 高度容差（米）
    'throttle_offset': 660,      # 油门偏移量
}


def main():
    """主函数"""
    console.print(Panel.fit(
        "[bold cyan]🚁 无人机自动起飞任务 - 上升到10米[/bold cyan]\n"
        f"[dim]无人机数量: {len(MISSION_CONFIG['uav_configs'])}[/dim]\n"
        f"[dim]目标高度: {MISSION_CONFIG['target_height']}m[/dim]\n"
        f"[dim]MQTT: {MISSION_CONFIG['mqtt_config']['host']}:{MISSION_CONFIG['mqtt_config']['port']}[/dim]",
        border_style="cyan"
    ))

    # 步骤1: 连接所有无人机
    console.print("\n[bold cyan]━━━ 步骤 1/3: 并行连接无人机 ━━━[/bold cyan]")
    try:
        connections = setup_multiple_drc_connections(
            uav_configs=MISSION_CONFIG['uav_configs'],
            mqtt_config=MISSION_CONFIG['mqtt_config'],
            osd_frequency=MISSION_CONFIG['osd_frequency'],
            hsi_frequency=MISSION_CONFIG['hsi_frequency'],
            heartbeat_interval=MISSION_CONFIG['heartbeat_interval'],
            skip_drc_setup=True
        )
    except Exception as e:
        console.print(f"[red]✗ 连接失败: {e}[/red]")
        return 1

    # 步骤2: 运行任务（自动创建 MissionRunner、倒计时、监控）
    console.print("\n[bold cyan]━━━ 步骤 2/3: 执行任务 ━━━[/bold cyan]")
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

        # 步骤3: 持续监控高度（直到 Ctrl+C）
        console.print("\n[bold cyan]━━━ 步骤 3/3: 悬停监控 ━━━[/bold cyan]")
        console.print("[bold green]✓ 所有任务已完成，进入悬停监控模式[/bold green]")
        console.print("[yellow]💡 按 Ctrl+C 停止监控并退出[/yellow]\n")

        # 持续打印高度（每1秒更新一次）
        while True:
            time.sleep(1.0)

            # 打印所有无人机的高度
            height_info = []
            for runner in runners:
                mqtt = runner.mqtt
                callsign = runner.config['callsign']
                h = mqtt.get_relative_height()

                if h is not None:
                    height_info.append(f"[cyan]{callsign}[/cyan]: [green]{h:.2f}m[/green]")
                else:
                    height_info.append(f"[cyan]{callsign}[/cyan]: [dim]N/A[/dim]")

                # 持续发送悬停指令保持连接
                send_stick_control(mqtt)

            console.print(f"[dim]{time.strftime('%H:%M:%S')}[/dim] | " + " | ".join(height_info))

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ 收到中断信号 (Ctrl+C)[/yellow]")
    finally:
        # 清理资源
        if runners:
            cleanup_missions(runners, hover_duration=1.0)

    return 0


if __name__ == '__main__':
    exit(main())
