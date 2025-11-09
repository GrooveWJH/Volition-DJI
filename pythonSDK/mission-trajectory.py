#!/usr/bin/env python3
"""
轨迹飞行任务 - 多机版本

支持多架无人机同时执行不同的轨迹文件。
每架无人机可以指定独立的轨迹文件、飞行参数和相机设置。
"""
import os
import time
import json
import threading
import concurrent.futures
from rich.console import Console
from rich.table import Table
from rich.live import Live
from djisdk import (
    setup_multiple_drc_connections,
    run_parallel_missions,
    cleanup_missions,
    create_takeoff_mission,
    load_trajectory,
    fly_trajectory_sequence,
    return_home,
    create_takeoff_table,
    create_trajectory_table,
)
from djisdk.services import reset_gimbal
from djisdk.services.drc_commands import set_camera_zoom

console = Console()

# ========== 配置 ==========

# 无人机配置（每架无人机可以有独立的轨迹文件和飞行参数）
UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot1',
        'callsign': 'Alpha',
        'trajectory_file': 'Trajectory/uav1.json',  # 独立轨迹文件
        'flight_height': 100.0,  # 飞行高度（米）
        'max_speed': 15,  # 最大速度（m/s）
        'hover_time': 10.0,  # 航点间悬停时间（秒）- 悬停时云台朝下
        'camera': {
            'gimbal_mode': 1,  # 0=回中, 1=向下, 2=偏航回中, 3=俯仰向下
            'zoom_factor': 5,  # 变焦倍数（2-200）
        }
    },
    {
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot2',
        'callsign': 'Bravo',
        'trajectory_file': 'Trajectory/uav2.json',  # 不同的轨迹
        'flight_height': 120.0,
        'max_speed': 12,
        'hover_time': 3.0,
        'camera': {
            'gimbal_mode': 1,
            'zoom_factor': 5,
        }
    },
    {
        'sn': '9N9CN180011TJN',
        'user_id': 'pilot3',
        'callsign': 'Charlie',
        'trajectory_file': 'Trajectory/uav3.json',
        'flight_height': 80.0,
        'max_speed': 10,
        'hover_time': 4.0,
        'camera': {
            'gimbal_mode': 1,
            'zoom_factor': 10,
        }
    },
]

MQTT_CONFIG = {
    'host': 'grve.me',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# 起飞参数（所有无人机共用）
TAKEOFF_TOLERANCE = 0.5  # 高度容差（米）
TAKEOFF_THROTTLE = 500  # 油门偏移量

# 调试选项
DEBUG_MODE = False  # 是否打印详细的 event 数据
SHOW_PROGRESS = False  # 是否在 fly_trajectory_sequence 内部显示详细进度（已关闭，使用 Rich 表格）

# ========== 辅助函数 ==========


def execute_single_trajectory(runner, config):
    """执行单架无人机的轨迹飞行任务（在独立线程中运行）"""
    callsign = config.get('callsign', 'UAV')

    try:
        # 1. 加载轨迹文件
        trajectory_file = config.get('trajectory_file')
        if not trajectory_file:
            runner.data['task_status'] = '未指定轨迹'
            return False

        waypoints = load_trajectory(trajectory_file)
        runner.data['task_status'] = '初始化相机'
        runner.data['total_waypoints'] = len(waypoints)

        # 2. 初始化相机设置
        mqtt = runner.mqtt
        camera_config = config.get('camera', {})
        payload_index = mqtt.get_payload_index() or "88-0-0"
        gimbal_mode = camera_config.get('gimbal_mode', 1)
        zoom_factor = camera_config.get('zoom_factor', 7)

        reset_gimbal(mqtt, payload_index=payload_index, reset_mode=gimbal_mode)
        set_camera_zoom(mqtt, payload_index=payload_index, zoom_factor=zoom_factor, camera_type="zoom")
        time.sleep(1)  # 等待相机设置生效

        # 3. 启动进度监控线程
        stop_monitor = threading.Event()

        def monitor_progress():
            """后台监控线程：更新距离和时间（航点索引由 fly_trajectory_sequence 维护）"""
            while not stop_monitor.is_set():
                try:
                    progress = mqtt.get_flyto_progress()
                    if progress and progress.get('status') == 'wayline_progress':
                        runner.data['remaining_distance'] = progress.get('remaining_distance')
                        runner.data['remaining_time'] = progress.get('remaining_time')
                        runner.data['task_status'] = '飞行中'
                    else:
                        runner.data.pop('remaining_distance', None)
                        runner.data.pop('remaining_time', None)
                except Exception:
                    pass
                time.sleep(0.5)

        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()

        # 4. 执行轨迹飞行
        success = fly_trajectory_sequence(
            runners=[runner],
            waypoints=waypoints,
            height=config.get('flight_height', 100.0),
            max_speed=config.get('max_speed', 12),
            hover_between_waypoints=config.get('hover_time', 5.0),
            show_progress=False,
            debug=False
        )

        # 停止监控线程
        stop_monitor.set()
        monitor_thread.join(timeout=1)

        # 更新状态
        if success:
            runner.data['task_status'] = f'完成 ({len(waypoints)}航点)'
            runner.data['current_waypoint'] = len(waypoints)
        else:
            runner.data['task_status'] = '任务失败'

        runner.data.pop('remaining_distance', None)
        runner.data.pop('remaining_time', None)
        return success

    except Exception as e:
        runner.data['task_status'] = f'异常: {str(e)[:20]}'
        return False


# ========== 主流程 ==========


def main():
    console.rule("[bold bright_cyan]多无人机轨迹飞行任务[/bold bright_cyan]")
    console.print(f"[bright_yellow]将启动 {len(UAV_CONFIGS)} 架无人机[/bright_yellow]\n")

    # 1. 连接所有无人机
    console.print("[bold bright_magenta][1/5] 连接无人机...[/bold bright_magenta]")
    connections = setup_multiple_drc_connections(
        uav_configs=UAV_CONFIGS,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=100,
        hsi_frequency=10,
        skip_drc_setup=True,
    )
    console.print(f"[bright_green]✓ 已连接 {len(connections)} 架无人机[/bright_green]\n")

    runners = None

    try:
        # 2. 分别起飞到各自指定高度
        console.print("[bold bright_magenta][2/5] 起飞到各自指定高度...[/bold bright_magenta]")

        # 为每架无人机创建独立的起飞任务（根据各自的 flight_height）
        takeoff_missions = [
            create_takeoff_mission(
                target_height=config['flight_height'],
                height_tolerance=TAKEOFF_TOLERANCE,
                throttle_offset=TAKEOFF_THROTTLE
            ) for config in UAV_CONFIGS
        ]

        # 显示各无人机的目标高度
        for config in UAV_CONFIGS:
            callsign = config['callsign']
            height = config['flight_height']
            console.print(f"[bright_cyan]  [{callsign}] 目标高度: {height}m[/bright_cyan]")

        # 启动起飞任务（不显示内部监控）
        runners = run_parallel_missions(connections, takeoff_missions, UAV_CONFIGS, countdown=3, show_monitor=False)

        # 实时监控起飞进度
        with Live(create_takeoff_table(runners), refresh_per_second=4, console=console) as live:
            while any(r.running for r in runners):
                live.update(create_takeoff_table(runners))
                time.sleep(0.25)

        console.print("[bright_green]✓ 起飞完成[/bright_green]\n")

        # 3. 准备轨迹任务
        console.print("[bold bright_magenta][3/5] 准备轨迹任务...[/bold bright_magenta]")

        # 创建航点摘要表格
        waypoints_table = Table(title="[bold bright_cyan]航点任务配置[/bold bright_cyan]", show_header=True)
        waypoints_table.add_column("无人机", style="bright_yellow", width=10)
        waypoints_table.add_column("航点数", style="bright_green", width=8)
        waypoints_table.add_column("轨迹文件", style="bright_cyan", width=30)
        waypoints_table.add_column("飞行高度", style="bright_magenta", width=10)

        mission_state = {}
        for config in UAV_CONFIGS:
            callsign = config.get('callsign')
            trajectory_file = config.get('trajectory_file')
            flight_height = config.get('flight_height', 100.0)

            if trajectory_file:
                try:
                    waypoints = load_trajectory(trajectory_file)
                    mission_state[callsign] = {
                        'total_waypoints': len(waypoints),
                        'current_waypoint': 0,
                        'task_status': '准备中',
                        'trajectory_file': trajectory_file,
                        'timestamp': time.time()
                    }
                    waypoints_table.add_row(callsign, str(len(waypoints)), trajectory_file, f"{flight_height}m")
                except Exception as e:
                    console.print(f"[bright_red]  [{callsign}] ⚠ 加载轨迹失败: {e}[/bright_red]")

        console.print(waypoints_table)
        console.print()

        # 写入状态文件（供 dashboard 使用）
        try:
            with open('/tmp/djisdk_mission_state.json', 'w') as f:
                json.dump(mission_state, f, indent=2)
            console.print("[bright_green]✓ 任务元数据已写入 /tmp/djisdk_mission_state.json[/bright_green]")
            console.print("[dim]  Dashboard 现在可以显示航点总进度[/dim]\n")
        except Exception as e:
            console.print(f"[bright_yellow]⚠ 写入状态文件失败: {e}[/bright_yellow]")
            console.print("[dim]  Dashboard 将只显示当前航点索引（降级模式）[/dim]\n")

        # 4. 并行执行轨迹飞行
        console.print(f"[bold bright_magenta][4/5] 开始轨迹飞行（{len(runners)} 架并行）...[/bold bright_magenta]")

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runners)) as executor:
            # 初始化 runner.data
            for runner, config in zip(runners, UAV_CONFIGS):
                callsign = config.get('callsign')
                runner.data['total_waypoints'] = mission_state.get(callsign, {}).get('total_waypoints', 0)
                runner.data['current_waypoint'] = 0
                runner.data['task_status'] = '准备中'

            # 提交所有飞行任务
            futures = {
                executor.submit(execute_single_trajectory, runner, config): config
                for runner, config in zip(runners, UAV_CONFIGS)
            }

            # 实时监控进度
            with Live(create_trajectory_table(runners, mission_state), refresh_per_second=2, console=console) as live:
                all_success = True
                completed_count = 0

                while completed_count < len(runners):
                    live.update(create_trajectory_table(runners, mission_state))
                    done_futures = [f for f in futures if f.done()]
                    completed_count = len(done_futures)

                    # 检查新完成的任务
                    for future in done_futures:
                        if future not in getattr(create_trajectory_table, '_processed', set()):
                            config = futures[future]
                            callsign = config.get('callsign', 'UAV')
                            try:
                                success = future.result()
                                if not success:
                                    all_success = False
                            except Exception as e:
                                console.print(f"[bright_red]✗ [{callsign}] 线程异常: {e}[/bright_red]")
                                all_success = False

                            if not hasattr(create_trajectory_table, '_processed'):
                                create_trajectory_table._processed = set()
                            create_trajectory_table._processed.add(future)

                    time.sleep(0.5)

        if all_success:
            console.print("\n[bold bright_green]✓ 所有无人机轨迹飞行完成[/bold bright_green]\n")
        else:
            console.print("\n[bold bright_yellow]⚠ 部分无人机轨迹飞行失败[/bold bright_yellow]\n")

        # 5. 返航
        console.print("[bold bright_magenta][5/5] 返航...[/bold bright_magenta]")
        for runner in runners:
            callsign = runner.config.get('callsign', 'UAV')
            return_home(runner.caller)
            console.print(f"[bright_cyan]  [{callsign}] 返航指令已发送[/bright_cyan]")
        console.print("[bright_green]✓ 所有返航指令已发送[/bright_green]\n")

        # 清理状态文件
        try:
            os.remove('/tmp/djisdk_mission_state.json')
            console.print("[bright_green]✓ 任务状态文件已清理[/bright_green]\n")
        except Exception:
            pass

        # 6. 悬停监控
        console.print("[bright_yellow]按 Ctrl+C 退出...[/bright_yellow]")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[bright_yellow]中断退出[/bright_yellow]")
    finally:
        try:
            os.remove('/tmp/djisdk_mission_state.json')
        except Exception:
            pass

        if runners:
            cleanup_missions(runners)


if __name__ == '__main__':
    main()
