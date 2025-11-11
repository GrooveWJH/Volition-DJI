"""
IVAS 任务执行器 - 将 IVAS 任务映射到 djisdk 操作

负责接收 IVAS 任务数据并执行对应的无人机操作。

任务类型映射：
1: 起飞到预设高度 (从 uav_config['flight_height'] 读取)
2: 降落 (持续下拉油门)
3: 返航 (一键返航)
4: 飞向指定点 (需要 lat/lon/alt)
5-7: 执行预设轨迹任务 (Trajectory/uav1-3.json，使用预设高度)
"""
import time
import os
import threading
from typing import Dict, Any, Optional
from rich.console import Console

from ..services import fly_to_point, return_home, send_stick_control
from .takeoff import create_takeoff_mission
from .trajectory import load_trajectory, fly_trajectory_sequence
from .runner import MissionRunner

console = Console()


def execute_ivas_task(
    task_data: Dict[str, Any],
    mqtt_client,
    caller,
    uav_config: Dict[str, str],
    heartbeat_thread: Optional[threading.Thread] = None,
    runner: Optional['MissionRunner'] = None
) -> None:
    """
    执行 IVAS 任务（同步执行，应在后台线程调用）

    Args:
        task_data: IVAS 任务数据，包含 mission, id, lat, lon, alt 等字段
        mqtt_client: MQTT 客户端
        caller: 服务调用器
        uav_config: 无人机配置（包含 callsign, sn, flight_height 等）
        heartbeat_thread: 心跳线程（可选）
        runner: 外部传入的 MissionRunner（可选，用于任务中断）

    Example:
        >>> task = {'mission': 1, 'id': 1}
        >>> execute_ivas_task(task, mqtt, caller, config)
    """
    mission = task_data.get('mission')
    target_id = task_data.get('id')
    callsign = uav_config.get('callsign', '未知')

    # 🔍 DEBUG: 确认进入执行器
    console.print(f"[bold magenta]🔍 [DEBUG] [{callsign}] execute_ivas_task 被调用: mission={mission}, id={target_id}, caller={caller is not None}, heartbeat={heartbeat_thread is not None}[/bold magenta]")

    console.print(f"[bold cyan][{callsign}] 执行 IVAS 任务 {mission}[/bold cyan]")

    try:
        # 任务分发（打印详细的函数调用信息）
        if mission == 1:
            console.print(f"[dim][{callsign}] 📞 调用: _task_takeoff(target_height={uav_config.get('flight_height', 20.0)})[/dim]")
            _task_takeoff(mqtt_client, caller, heartbeat_thread, uav_config, runner)
        elif mission == 2:
            console.print(f"[dim][{callsign}] 📞 调用: _task_land()[/dim]")
            _task_land(mqtt_client, callsign, runner)
        elif mission == 3:
            console.print(f"[dim][{callsign}] 📞 调用: _task_return_home()[/dim]")
            _task_return_home(caller, callsign)
        elif mission == 4:
            lat = task_data.get('lat')
            lon = task_data.get('lon')
            alt = task_data.get('alt')
            console.print(f"[dim][{callsign}] 📞 调用: _task_fly_to_point(lat={lat}, lon={lon}, alt={alt})[/dim]")
            _task_fly_to_point(caller, lat, lon, alt, callsign)
        elif mission in [5, 6, 7]:
            trajectory_index = mission - 4
            trajectory_file = f"Trajectory/uav{trajectory_index}.json"
            console.print(f"[dim][{callsign}] 📞 调用: _task_trajectory(file={trajectory_file}, height={uav_config.get('flight_height', 20.0)})[/dim]")
            _task_trajectory(mqtt_client, caller, mission, uav_config, callsign, runner)
        else:
            console.print(f"[red][{callsign}] 未知任务类型: {mission}[/red]")

        console.print(f"[bold green][{callsign}] 任务 {mission} 执行完成[/bold green]")

    except Exception as e:
        console.print(f"[bold red][{callsign}] 任务执行失败: {e}[/bold red]")
        raise


def _task_takeoff(mqtt, caller, heartbeat, uav_config: Dict[str, Any], runner=None):
    """任务1: 起飞到预设高度"""
    # 从配置读取起飞高度，默认 20.0 米
    target_height = uav_config.get('flight_height', 20.0)
    callsign = uav_config.get('callsign', '未知')

    # 🔍 DEBUG: 确认进入起飞函数
    console.print(f"[bold magenta]🔍 [DEBUG] [{callsign}] _task_takeoff 被调用: target_height={target_height}, runner={runner is not None}, runner.running={runner.running if runner else 'N/A'}[/bold magenta]")

    console.print(f"[cyan][{callsign}] 开始起飞到预设高度 {target_height}m...[/cyan]")

    # 使用 djisdk 起飞任务
    takeoff_mission = create_takeoff_mission(
        target_height=target_height,
        height_tolerance=0.5,
        throttle_offset=440
    )

    # 使用外部传入的 runner（用于中断），如果没有则创建新的
    if runner is None:
        runner = MissionRunner(mqtt, caller, heartbeat, {'callsign': callsign, 'sn': mqtt.gateway_sn})

    runner.running = True  # 必须设置为 True，否则 takeoff_mission 中的 while runner.running 不会执行
    takeoff_mission(runner)

    console.print(f"[green][{callsign}] 起飞完成，当前高度: {mqtt.get_relative_height():.2f}m[/green]")


def _task_land(mqtt, callsign: str, runner=None):
    """任务2: 降落（持续发送最小油门直到待机）"""
    console.print(f"[cyan][{callsign}] 开始降落...[/cyan]")

    # 创建一个简单的 runner（用于中断检查）
    if runner is None:
        from .runner import MissionRunner
        runner = MissionRunner(mqtt, None, None, {'callsign': callsign})

    runner.running = True  # 启用中断检查

    # 持续发送最小油门指令，直到飞行模式变为待机
    loop_count = 0
    while runner.running:  # 支持中断
        # 获取当前飞行模式
        flight_mode = mqtt.get_flight_mode()

        # 如果飞行模式为待机（0），停止降落
        if flight_mode == 0:
            console.print(f"[green][{callsign}] 已降落到地面（飞行模式：待机）[/green]")
            break

        # 超时保护（最多50秒）
        if loop_count >= 500:
            console.print(f"[yellow][{callsign}] 降落超时，当前飞行模式：{mqtt.get_flight_mode_name()}[/yellow]")
            break

        # 发送最小油门（全杆向下）
        send_stick_control(mqtt, throttle=364)  # 364 = 最小杆量
        time.sleep(0.1)

        # 每秒打印一次状态
        if loop_count % 10 == 0:
            current_height = mqtt.get_relative_height()
            mode_name = mqtt.get_flight_mode_name()
            console.print(f"[dim][{callsign}] 高度: {current_height:.2f}m | 模式: {mode_name}[/dim]")

        loop_count += 1

    # 最后发送悬停指令
    for _ in range(10):
        send_stick_control(mqtt)  # 悬停
        time.sleep(0.1)


def _task_return_home(caller, callsign: str):
    """任务3: 一键返航"""
    console.print(f"[cyan][{callsign}] 执行一键返航...[/cyan]")
    return_home(caller)
    console.print(f"[green][{callsign}] 返航指令已发送[/green]")


def _task_fly_to_point(caller, lat: float, lon: float, alt: float, callsign: str):
    """任务4: 飞向指定点"""
    console.print(f"[cyan][{callsign}] 飞向目标点 (lat:{lat:.6f}, lon:{lon:.6f}, alt:{alt:.1f}m)...[/cyan]")

    # 发送 Fly-to 指令
    fly_to_id = fly_to_point(
        caller,
        latitude=lat,
        longitude=lon,
        height=alt,
        max_speed=12
    )

    console.print(f"[green][{callsign}] Fly-to 指令已发送 (ID: {fly_to_id})[/green]")


def _task_trajectory(mqtt, caller, mission: int, uav_config: Dict[str, str], callsign: str, runner=None):
    """任务5-7: 执行预设轨迹任务"""
    trajectory_index = mission - 4  # 5->1, 6->2, 7->3
    trajectory_file = f"Trajectory/uav{trajectory_index}.json"

    console.print(f"[cyan][{callsign}] 执行轨迹任务: {trajectory_file}...[/cyan]")

    # 检查文件是否存在
    if not os.path.exists(trajectory_file):
        console.print(f"[red][{callsign}] 轨迹文件不存在: {trajectory_file}[/red]")
        return

    # 加载轨迹
    waypoints = load_trajectory(trajectory_file)
    console.print(f"[dim][{callsign}] 已加载 {len(waypoints)} 个航点[/dim]")

    # 使用外部传入的 runner（用于中断和进度跟踪），如果没有则创建新的
    if runner is None:
        runner_config = {
            'callsign': callsign,
            'sn': mqtt.gateway_sn,
            'trajectory_file': trajectory_file,
            'flight_height': uav_config.get('flight_height', 20.0)
        }
        runner = MissionRunner(mqtt, caller, None, runner_config)

    # 更新 runner 配置（确保有轨迹文件信息）
    runner.config['trajectory_file'] = trajectory_file
    runner.config['flight_height'] = uav_config.get('flight_height', 20.0)

    # 初始化任务数据（fly_trajectory_sequence 会自动更新到文件）
    runner.data['total_waypoints'] = len(waypoints)
    runner.data['current_waypoint'] = 0
    runner.data['task_status'] = '准备中'

    # 执行轨迹（内部自动写入 /tmp/djisdk_mission_state.json）
    flight_height = uav_config.get('flight_height', 20.0)
    success = fly_trajectory_sequence(
        runners=[runner],              # 传递 MissionRunner 列表
        waypoints=waypoints,
        height=flight_height,
        max_speed=12,
        hover_between_waypoints=5.0,
        show_progress=False,           # 后台执行，不打印详细日志
        debug=False
    )

    # 检查执行结果
    if success:
        console.print(f"[green][{callsign}] 轨迹任务执行完成[/green]")
    else:
        console.print(f"[red][{callsign}] 轨迹任务执行失败[/red]")
