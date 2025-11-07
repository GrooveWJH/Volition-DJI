"""
轨迹飞行任务模块

提供多航点顺序飞行任务的高级封装，支持：
- 从 JSON 文件加载航点
- 依次飞向多个航点
- 实时监控飞行进度
- 航点间悬停稳定
"""
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console

from ..services import fly_to_point, send_stick_control
from .runner import MissionRunner

console = Console()


def load_trajectory(filepath: str) -> List[Dict[str, Any]]:
    """
    从 JSON 文件加载航点数据

    Args:
        filepath: 航点文件路径

    Returns:
        航点列表，每个航点包含 id, lat, lon

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
        ValueError: 数据格式错误

    Example:
        >>> waypoints = load_trajectory('Trajectory/uav1.json')
        >>> print(f"加载了 {len(waypoints)} 个航点")
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


def fly_trajectory_sequence(
    runners: List[MissionRunner],
    waypoints: List[Dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True
) -> bool:
    """
    依次飞向多个航点（所有无人机并行执行相同轨迹）

    Args:
        runners: MissionRunner 列表
        waypoints: 航点列表，每个航点包含 lat, lon, 可选 id
        height: 飞行高度（椭球高，米）
        max_speed: 最大速度（m/s，0-15）
        hover_between_waypoints: 航点间悬停时间（秒）
        show_progress: 是否显示进度信息

    Returns:
        是否全部成功

    Example:
        >>> waypoints = [
        >>>     {'id': 1, 'lat': 39.0427514, 'lon': 117.7238255},
        >>>     {'id': 2, 'lat': 39.0428000, 'lon': 117.7239000},
        >>> ]
        >>> success = fly_trajectory_sequence(runners, waypoints, height=100.0)
    """
    total_waypoints = len(waypoints)
    all_success = True

    for wp_index, waypoint in enumerate(waypoints, 1):
        wp_id = waypoint.get('id', wp_index)
        lat = waypoint['lat']
        lon = waypoint['lon']

        if show_progress:
            console.print(
                f"\n[bold bright_cyan]━━━ 航点 {wp_index}/{total_waypoints} (ID: {wp_id}) ━━━[/bold bright_cyan]")
            console.print(
                f"[bright_yellow]目标: lat={lat:.7f}, lon={lon:.7f}, h={height:.1f}m[/bright_yellow]")

        # 发送 Fly-to 指令到所有无人机
        for runner in runners:
            caller = runner.caller
            callsign = runner.config.get('callsign', 'UAV')
            if show_progress:
                console.print(f"[bright_cyan][{callsign}] 飞向航点 {wp_index}...[/bright_cyan]")

            try:
                fly_to_point(caller, latitude=lat, longitude=lon, height=height, max_speed=max_speed)
            except Exception as e:
                console.print(f"[bright_red]✗ [{callsign}] 发送指令失败: {e}[/bright_red]")
                all_success = False

        # 监控飞行进度
        if show_progress:
            console.print(f"[dim]监控飞行进度...[/dim]\n")

        last_status = {}
        while True:
            time.sleep(1.0)

            all_done = True
            for runner in runners:
                mqtt = runner.mqtt
                callsign = runner.config.get('callsign', 'UAV')

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
                            if show_progress:
                                console.print(
                                    f"[bold bright_green]✓ [{callsign}] 已到达航点 {wp_index}！[/bold bright_green]")
                        elif status == 'wayline_failed':
                            if show_progress:
                                console.print(
                                    f"[bold bright_red]✗ [{callsign}] 飞向航点 {wp_index} 失败[/bold bright_red]")
                            all_success = False
                        elif status == 'wayline_cancel':
                            if show_progress:
                                console.print(
                                    f"[bold bright_yellow]⚠ [{callsign}] 飞向航点 {wp_index} 取消[/bold bright_yellow]")
                            all_success = False
                        last_status[callsign] = status
                elif status == 'wayline_progress':
                    all_done = False
                    # 打印进度信息
                    if show_progress and remaining_distance is not None and remaining_time is not None:
                        console.print(
                            f"[dim]{time.strftime('%H:%M:%S')}[/dim] | "
                            f"[bright_cyan]{callsign}[/bright_cyan]: "
                            f"[bright_yellow]航点 {wp_index} - 剩余 {remaining_distance:.1f}m, {remaining_time:.1f}s[/bright_yellow]"
                        )
                else:
                    # 还没收到进度数据
                    all_done = False

            # 所有无人机都完成了当前航点
            if all_done:
                break

        if show_progress:
            console.print(
                f"[bold bright_green]✓ 航点 {wp_index}/{total_waypoints} 完成[/bold bright_green]")

        # 悬停等待飞控状态稳定（除了最后一个航点）
        if wp_index < total_waypoints and hover_between_waypoints > 0:
            if show_progress:
                console.print(
                    f"[dim]悬停等待 {hover_between_waypoints:.1f} 秒，飞控状态稳定中...[/dim]")

            steps = int(hover_between_waypoints * 10)  # 10Hz
            for _ in range(steps):
                for runner in runners:
                    send_stick_control(runner.mqtt)
                time.sleep(0.1)

    return all_success


def create_trajectory_mission(
    waypoints: List[Dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True
):
    """
    创建轨迹飞行任务函数（用于 run_parallel_missions）

    这是一个高阶函数，返回一个任务函数，可以直接传给 run_parallel_missions。

    Args:
        waypoints: 航点列表
        height: 飞行高度（米）
        max_speed: 最大速度（m/s）
        hover_between_waypoints: 航点间悬停时间（秒）
        show_progress: 是否显示进度信息

    Returns:
        任务函数，签名: (runner: MissionRunner) -> None

    Example:
        >>> waypoints = load_trajectory('Trajectory/uav1.json')
        >>> mission = create_trajectory_mission(waypoints, height=100.0)
        >>> runners = run_parallel_missions(connections, mission, uav_configs)
    """
    def trajectory_mission(runner: MissionRunner):
        """执行轨迹飞行任务"""
        # 单个无人机的轨迹飞行
        success = fly_trajectory_sequence(
            runners=[runner],
            waypoints=waypoints,
            height=height,
            max_speed=max_speed,
            hover_between_waypoints=hover_between_waypoints,
            show_progress=show_progress
        )

        if not success:
            raise RuntimeError("轨迹飞行任务执行失败")

    return trajectory_mission
