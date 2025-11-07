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

from ..services import fly_to_point
from .runner import MissionRunner

console = Console()


def load_trajectory(filepath: str) -> List[Dict[str, Any]]:
    """
    从 JSON 文件加载航点数据

    Args:
        filepath: 航点文件路径

    Returns:
        航点列表，每个航点包含:
        - id: 航点编号
        - lat: 纬度
        - lon: 经度

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
    show_progress: bool = True,
    debug: bool = False
) -> bool:
    """
    依次飞向多个航点（所有无人机并行执行相同轨迹）

    Args:
        runners: MissionRunner 列表
        waypoints: 航点列表，每个航点包含:
            - lat, lon: 必需
        height: 飞行高度（椭球高，米）
        max_speed: 最大速度（m/s，0-15）
        hover_between_waypoints: 航点间悬停时间（秒）
        show_progress: 是否显示进度信息
        debug: 是否打印调试信息（包括完整的 event 数据）

    Returns:
        是否全部成功

    Example:
        >>> waypoints = [
        >>>     {'id': 1, 'lat': 39.0427514, 'lon': 117.7238255},
        >>>     {'id': 2, 'lat': 39.0428000, 'lon': 117.7239000},
        >>> ]
        >>> success = fly_trajectory_sequence(runners, waypoints, height=100.0, debug=True)
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

        # 发送 Fly-to 指令到所有无人机，并记录 fly_to_id
        fly_to_ids = {}  # {callsign: (result_data, fly_to_id)}
        for runner in runners:
            caller = runner.caller
            callsign = runner.config.get('callsign', 'UAV')
            if show_progress:
                console.print(f"[bright_cyan][{callsign}] 飞向航点 {wp_index}...[/bright_cyan]")

            try:
                result_data, fly_to_id = fly_to_point(
                    caller, latitude=lat, longitude=lon, height=height, max_speed=max_speed
                )
                fly_to_ids[callsign] = (result_data, fly_to_id)
            except Exception as e:
                # service call 失败，但不影响后续监控
                console.print(f"[bright_yellow]⚠ [{callsign}] Fly-to service 调用失败[/bright_yellow]")
                console.print(f"[dim]   原因: {e}[/dim]")
                all_success = False
                fly_to_ids[callsign] = (None, None)  # 标记为失败

        # 监控飞行进度（使用 wait_for_flyto_event）
        if show_progress:
            console.print(f"[dim]监控飞行进度...[/dim]\n")

        for runner in runners:
            mqtt = runner.mqtt
            callsign = runner.config.get('callsign', 'UAV')
            result_data, fly_to_id = fly_to_ids.get(callsign, (None, None))

            # 跳过 service call 失败的无人机
            if fly_to_id is None:
                if show_progress:
                    console.print(f"[dim][{callsign}] 跳过监控（service call 失败）[/dim]")
                continue

            # 等待航点事件（自动验证 fly_to_id，防止读取旧数据）
            try:
                if debug:
                    console.print(f"[dim]🐛 [{callsign}] 等待 fly_to_id={fly_to_id[:8]}... 的事件[/dim]")

                progress = mqtt.wait_for_flyto_event(
                    expected_fly_to_id=fly_to_id,
                    timeout=120.0,  # 2 分钟超时
                    poll_interval=1.0  # 1 秒轮询
                )

                status = progress.get('status')
                result_code = progress.get('result')

                # 调试：打印完整事件数据
                if debug:
                    console.print(f"[dim]🐛 [{callsign}] 收到事件: {progress}[/dim]")

                # 检查终止状态
                if status == 'wayline_ok':
                    if show_progress:
                        console.print(
                            f"[bold bright_green]✓ [{callsign}] 已到达航点 {wp_index}！[/bold bright_green]"
                        )
                elif status == 'wayline_failed':
                    if show_progress:
                        console.print(
                            f"[bold bright_red]✗ [{callsign}] 飞向航点 {wp_index} 失败[/bold bright_red]"
                        )
                        console.print(f"[dim]   result_code: {result_code}[/dim]")
                    all_success = False
                elif status == 'wayline_cancel':
                    if show_progress:
                        console.print(
                            f"[bold bright_yellow]⚠ [{callsign}] 飞向航点 {wp_index} 取消[/bold bright_yellow]"
                        )
                        console.print(f"[dim]   result_code: {result_code}[/dim]")
                    all_success = False

            except TimeoutError as e:
                console.print(f"[bold bright_red]✗ [{callsign}] 航点 {wp_index} 超时[/bold bright_red]")
                console.print(f"[dim]   {e}[/dim]")
                all_success = False
            except Exception as e:
                console.print(f"[bold bright_red]✗ [{callsign}] 航点 {wp_index} 异常[/bold bright_red]")
                console.print(f"[dim]   {e}[/dim]")
                all_success = False

        if show_progress:
            console.print(
                f"[bold bright_green]✓ 航点 {wp_index}/{total_waypoints} 飞行完成[/bold bright_green]")

        # 航点间等待（除了最后一个航点）
        if wp_index < total_waypoints and hover_between_waypoints > 0:
            if show_progress:
                console.print(
                    f"[dim]等待 {hover_between_waypoints:.1f} 秒后继续下一个航点...[/dim]")

            # 简单等待，不发送任何控制指令（fly_to_point 后飞机会自动悬停）
            time.sleep(hover_between_waypoints)

    return all_success


def create_trajectory_mission(
    waypoints: List[Dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True,
    debug: bool = False
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
        debug: 是否打印调试信息

    Returns:
        任务函数，签名: (runner: MissionRunner) -> None

    Example:
        >>> waypoints = load_trajectory('Trajectory/uav1.json')
        >>> mission = create_trajectory_mission(waypoints, height=100.0, debug=True)
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
            show_progress=show_progress,
            debug=debug
        )

        if not success:
            raise RuntimeError("轨迹飞行任务执行失败")

    return trajectory_mission
