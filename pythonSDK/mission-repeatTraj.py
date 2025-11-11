#!/usr/bin/env python3
"""
循环往返飞行任务 - 多机版本

在配置的两个GPS航点之间循环往返飞行。
每到达一个航点后悬停2秒，然后飞往另一个航点。
"""
import time
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
    fly_to_point,
    return_home,
    create_takeoff_table,
)
from djisdk.services import reset_gimbal
from djisdk.services.drc_commands import set_camera_zoom

console = Console()

# ========== 配置 ==========

# 无人机配置（直接配置两个GPS航点）
UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot1',
        'callsign': 'Alpha',
        'flight_height': 90.0,  # 飞行高度（米）
        'waypoints': [
            {'id': 8, 'lat': 39.0432224, 'lon': 117.7259497},  # 航点A
            {'id': 9, 'lat': 39.0425837, 'lon': 117.7252676},  # 航点B
        ],
        'max_speed': 12,  # 最大速度（m/s）
        'hover_time': 2.0,  # 到达航点后悬停时间（秒）
        'camera': {
            'gimbal_mode': 1,  # 0=回中, 1=向下, 2=偏航回中, 3=俯仰向下
            'zoom_factor': 5,  # 变焦倍数（2-200）
        }
    },
    # {
    #     'sn': '9N9CN8400164WH',
    #     'user_id': 'pilot2',
    #     'callsign': 'Bravo',
    #     'flight_height': 100.0,
    #     'waypoints': [
    #         {'id': 10, 'lat': 39.0430000, 'lon': 117.7258000},
    #         {'id': 11, 'lat': 39.0428000, 'lon': 117.7254000},
    #     ],
    #     'max_speed': 10,
    #     'hover_time': 2.0,
    #     'camera': {
    #         'gimbal_mode': 1,
    #         'zoom_factor': 5,
    #     }
    # },
]

MQTT_CONFIG = {
    'host': '81.70.222.38',
    # 'host': 'grve.me',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# 起飞参数（所有无人机共用）
TAKEOFF_TOLERANCE = 0.5  # 高度容差（米）
TAKEOFF_THROTTLE = 500  # 油门偏移量

# 循环控制
MAX_CYCLES = None  # 最大循环次数（None = 无限循环，直到 Ctrl+C）

# ========== 辅助函数 ==========


def execute_repeat_trajectory(runner, config):
    """执行单架无人机的循环往返飞行任务（在独立线程中运行）"""
    callsign = config.get('callsign', 'UAV')
    waypoints = config.get('waypoints', [])
    flight_height = config.get('flight_height', 100.0)
    max_speed = config.get('max_speed', 12)
    hover_time = config.get('hover_time', 2.0)

    if len(waypoints) != 2:
        runner.data['task_status'] = '航点数量错误'
        console.print(f"[red][{callsign}] 错误: 需要恰好2个航点，当前有 {len(waypoints)} 个[/red]")
        return False

    try:
        # 1. 读取配置中的航点
        waypoint_a = waypoints[0]
        waypoint_b = waypoints[1]

        lat_a = waypoint_a['lat']
        lon_a = waypoint_a['lon']
        lat_b = waypoint_b['lat']
        lon_b = waypoint_b['lon']

        console.print(f"[cyan][{callsign}] 航点A (id={waypoint_a.get('id', '?')}): GPS({lat_a:.6f}, {lon_a:.6f})[/cyan]")
        console.print(f"[cyan][{callsign}] 航点B (id={waypoint_b.get('id', '?')}): GPS({lat_b:.6f}, {lon_b:.6f})[/cyan]")

        # 2. 初始化相机设置
        runner.data['task_status'] = '初始化相机'
        mqtt = runner.mqtt
        camera_config = config.get('camera', {})
        payload_index = mqtt.get_payload_index() or "88-0-0"
        gimbal_mode = camera_config.get('gimbal_mode', 1)
        zoom_factor = camera_config.get('zoom_factor', 7)

        reset_gimbal(mqtt, payload_index=payload_index, reset_mode=gimbal_mode)
        set_camera_zoom(mqtt, payload_index=payload_index, zoom_factor=zoom_factor, camera_type="zoom")
        time.sleep(1)  # 等待相机设置生效

        # 3. 初始化进度数据
        runner.data['total_waypoints'] = 2
        runner.data['current_waypoint'] = 0
        runner.data['cycle_count'] = 0
        runner.data['task_status'] = '飞行中'

        # 4. 启动进度监控线程
        stop_monitor = threading.Event()

        def monitor_progress():
            """后台监控线程：更新距离和时间"""
            while not stop_monitor.is_set():
                try:
                    progress = mqtt.get_flyto_progress()
                    if progress and progress.get('status') == 'wayline_progress':
                        runner.data['remaining_distance'] = progress.get('remaining_distance')
                        runner.data['remaining_time'] = progress.get('remaining_time')
                    else:
                        runner.data.pop('remaining_distance', None)
                        runner.data.pop('remaining_time', None)
                except Exception:
                    pass
                time.sleep(0.5)

        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()

        # 6. 循环往返飞行
        cycle = 0
        current_target = 'B'  # 先飞往B点（最后一个航点）

        while runner.running:
            # 检查循环次数限制
            if MAX_CYCLES is not None and cycle >= MAX_CYCLES:
                console.print(f"[green][{callsign}] 达到最大循环次数 {MAX_CYCLES}[/green]")
                break

            # 选择目标航点
            if current_target == 'B':
                target_lat, target_lon = lat_b, lon_b
                target_name = f'B(id={waypoint_b.get("id", "?")})'
            else:
                target_lat, target_lon = lat_a, lon_a
                target_name = f'A(id={waypoint_a.get("id", "?")})'

            # 更新当前目标
            runner.data['current_waypoint'] = 1 if current_target == 'B' else 0
            runner.data['current_target'] = target_name

            # 发送 fly_to_point 指令
            console.print(f"[dim][{callsign}] → 航点{target_name} (GPS: {target_lat:.6f}, {target_lon:.6f})[/dim]")

            try:
                fly_to_point(
                    runner.caller,
                    latitude=target_lat,
                    longitude=target_lon,
                    height=flight_height,
                    max_speed=max_speed
                )
            except Exception as e:
                console.print(f"[red][{callsign}] fly_to_point 失败: {e}[/red]")
                runner.data['task_status'] = '飞点失败'
                break

            # 等待到达（检查距离或 flyto 进度）
            timeout = 60  # 最多等待60秒
            start_time = time.time()
            arrived = False

            while runner.running and (time.time() - start_time) < timeout:
                # 检查是否到达
                current_lat, current_lon, _ = mqtt.get_position()
                if current_lat and current_lon:
                    # 简单距离检查（度数差异）
                    lat_diff = abs(current_lat - target_lat)
                    lon_diff = abs(current_lon - target_lon)

                    # 容差约1米（约 0.00001 度）
                    if lat_diff < 0.00001 and lon_diff < 0.00001:
                        arrived = True
                        break

                time.sleep(0.5)

            if not arrived:
                console.print(f"[yellow][{callsign}] 警告: 到达航点{target_name}超时[/yellow]")

            # 到达后悬停
            if runner.running:
                console.print(f"[dim][{callsign}] 悬停 {hover_time}s...[/dim]")
                time.sleep(hover_time)

            # 切换目标
            if current_target == 'B':
                current_target = 'A'
                cycle += 1  # 完成一个完整循环（B→A）
                runner.data['cycle_count'] = cycle
            else:
                current_target = 'B'

        # 停止监控线程
        stop_monitor.set()
        monitor_thread.join(timeout=1)

        # 更新最终状态
        runner.data['task_status'] = f'完成 ({cycle}次循环)'
        runner.data.pop('remaining_distance', None)
        runner.data.pop('remaining_time', None)
        return True

    except Exception as e:
        console.print(f"[red][{callsign}] 异常: {e}[/red]")
        runner.data['task_status'] = f'异常: {str(e)[:20]}'
        return False


def create_repeat_trajectory_table(runners):
    """创建循环往返飞行进度表格"""
    table = Table(title="[bold cyan]循环往返飞行进度[/bold cyan]", show_header=True)
    table.add_column("无人机", style="yellow", width=10)
    table.add_column("循环次数", style="green", width=10)
    table.add_column("当前目标", style="cyan", width=10)
    table.add_column("剩余距离", style="magenta", width=12)
    table.add_column("剩余时间", style="blue", width=12)
    table.add_column("状态", style="white", width=20)

    for runner in runners:
        callsign = runner.config.get('callsign', 'UAV')
        cycle_count = runner.data.get('cycle_count', 0)
        current_target = runner.data.get('current_target', '-')
        remaining_dist = runner.data.get('remaining_distance')
        remaining_time = runner.data.get('remaining_time')
        task_status = runner.data.get('task_status', '未知')

        # 格式化距离和时间
        dist_str = f"{remaining_dist:.1f}m" if remaining_dist is not None else "-"
        time_str = f"{remaining_time:.1f}s" if remaining_time is not None else "-"

        table.add_row(
            callsign,
            str(cycle_count),
            current_target,
            dist_str,
            time_str,
            task_status
        )

    return table


# ========== 主流程 ==========


def main():
    console.rule("[bold bright_cyan]多无人机循环往返飞行任务[/bold bright_cyan]")
    console.print(f"[bright_yellow]将启动 {len(UAV_CONFIGS)} 架无人机[/bright_yellow]")
    console.print(f"[bright_yellow]循环模式: {'无限循环' if MAX_CYCLES is None else f'{MAX_CYCLES} 次循环'}[/bright_yellow]\n")

    # 1. 连接所有无人机
    console.print("[bold bright_magenta][1/4] 连接无人机...[/bold bright_magenta]")
    connections = setup_multiple_drc_connections(
        uav_configs=UAV_CONFIGS,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=100,
        hsi_frequency=10,
        skip_drc_setup=False,
    )
    console.print(f"[bright_green]✓ 已连接 {len(connections)} 架无人机[/bright_green]\n")

    runners = None

    try:
        # 2. 分别起飞到各自指定高度
        console.print("[bold bright_magenta][2/4] 起飞到各自指定高度...[/bold bright_magenta]")

        takeoff_missions = [
            create_takeoff_mission(
                target_height=config['flight_height'],
                height_tolerance=TAKEOFF_TOLERANCE,
                throttle_offset=TAKEOFF_THROTTLE
            ) for config in UAV_CONFIGS
        ]

        for config in UAV_CONFIGS:
            callsign = config['callsign']
            height = config['flight_height']
            console.print(f"[bright_cyan]  [{callsign}] 目标高度: {height}m[/bright_cyan]")

        runners = run_parallel_missions(connections, takeoff_missions, UAV_CONFIGS, countdown=3, show_monitor=False)

        with Live(create_takeoff_table(runners), refresh_per_second=4, console=console) as live:
            while any(r.running for r in runners):
                live.update(create_takeoff_table(runners))
                time.sleep(0.25)

        console.print("[bright_green]✓ 起飞完成[/bright_green]\n")

        # 3. 准备航点配置
        console.print("[bold bright_magenta][3/4] 航点配置...[/bold bright_magenta]")

        waypoints_table = Table(title="[bold bright_cyan]往返航点配置[/bold bright_cyan]", show_header=True)
        waypoints_table.add_column("无人机", style="bright_yellow", width=10)
        waypoints_table.add_column("航点A", style="bright_green", width=30)
        waypoints_table.add_column("航点B", style="bright_magenta", width=30)
        waypoints_table.add_column("飞行高度", style="bright_blue", width=10)

        for config in UAV_CONFIGS:
            callsign = config.get('callsign')
            waypoints = config.get('waypoints', [])
            flight_height = config.get('flight_height', 100.0)

            if len(waypoints) == 2:
                wp_a = waypoints[0]
                wp_b = waypoints[1]
                wp_a_str = f"id={wp_a.get('id', '?')} ({wp_a['lat']:.7f}, {wp_a['lon']:.7f})"
                wp_b_str = f"id={wp_b.get('id', '?')} ({wp_b['lat']:.7f}, {wp_b['lon']:.7f})"
                waypoints_table.add_row(
                    callsign,
                    wp_a_str,
                    wp_b_str,
                    f"{flight_height}m"
                )
            else:
                waypoints_table.add_row(
                    callsign,
                    f"[red]航点数量错误: {len(waypoints)}[/red]",
                    "-",
                    f"{flight_height}m"
                )

        console.print(waypoints_table)
        console.print()

        # 4. 并行执行循环往返飞行
        console.print(f"[bold bright_magenta][4/4] 开始循环往返飞行（{len(runners)} 架并行）...[/bold bright_magenta]")
        console.print("[bright_yellow]按 Ctrl+C 停止循环[/bright_yellow]\n")

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runners)) as executor:
            # 初始化 runner.data
            for runner, config in zip(runners, UAV_CONFIGS):
                runner.data['cycle_count'] = 0
                runner.data['current_target'] = '-'
                runner.data['task_status'] = '准备中'

            # 提交所有飞行任务
            futures = {
                executor.submit(execute_repeat_trajectory, runner, config): config
                for runner, config in zip(runners, UAV_CONFIGS)
            }

            # 实时监控进度
            with Live(create_repeat_trajectory_table(runners), refresh_per_second=2, console=console) as live:
                while not all(f.done() for f in futures):
                    live.update(create_repeat_trajectory_table(runners))
                    time.sleep(0.5)

            # 检查结果
            console.print("\n[bold bright_green]✓ 所有无人机任务结束[/bold bright_green]\n")

            for future, config in futures.items():
                callsign = config.get('callsign', 'UAV')
                try:
                    success = future.result()
                    if success:
                        console.print(f"[bright_green]✓ [{callsign}] 任务完成[/bright_green]")
                    else:
                        console.print(f"[bright_yellow]⚠ [{callsign}] 任务失败[/bright_yellow]")
                except Exception as e:
                    console.print(f"[bright_red]✗ [{callsign}] 线程异常: {e}[/bright_red]")

        # 5. 返航
        console.print("\n[bold bright_magenta]返航...[/bold bright_magenta]")
        for runner in runners:
            callsign = runner.config.get('callsign', 'UAV')
            return_home(runner.caller)
            console.print(f"[bright_cyan]  [{callsign}] 返航指令已发送[/bright_cyan]")
        console.print("[bright_green]✓ 所有返航指令已发送[/bright_green]\n")

        # 6. 悬停监控
        console.print("[bright_yellow]按 Ctrl+C 退出...[/bright_yellow]")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[bright_yellow]中断退出 - 停止所有循环[/bright_yellow]")

        # 停止所有 runner
        if runners:
            for runner in runners:
                runner.running = False

    finally:
        if runners:
            cleanup_missions(runners)


if __name__ == '__main__':
    main()
