#!/usr/bin/env python3
"""
平面位置PID控制器 - 主程序
使用统一的control模块重构版本

功能：
- 使用VRPN位置数据作为反馈
- 通过PID算法控制无人机飞到目标XY位置
- 只控制XY平面位置，不控制Yaw角和高度
- 支持多个航点循环测试

坐标映射：
- X轴（前方向，x变大）→ Pitch杆量（正值）
- Y轴（左方向，y变大）→ Roll杆量（负值）

使用方法：
1. 手动让无人机起飞到1m高度
2. 启动本程序: python control/plane_main.py
3. 无人机按顺序飞到各个航点
4. 每到达一个航点，等待按 Enter 键（或自动模式下自动前往下一个）
5. 循环往复
6. 按 Ctrl+C 退出程序
"""

import time
import os
import sys
import random

# 添加父目录到路径，确保能导入djisdk和vrpn
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from djisdk import MQTTClient, start_heartbeat, stop_heartbeat, send_stick_control
from vrpn import VRPNClient
from rich.console import Console
from rich.panel import Panel

# 导入control模块
from control.config import *
from control.controller import PlaneController
from control.logger import DataLogger


def generate_random_waypoint(current_x, current_y, min_distance=0.5, max_distance=2.0):
    """
    生成随机航点（确保与当前位置距离在指定范围内）

    Args:
        current_x: 当前X坐标（米）
        current_y: 当前Y坐标（米）
        min_distance: 最小距离（米）
        max_distance: 最大距离（米）

    Returns:
        (x, y) 随机航点坐标
    """
    import math
    # 生成随机角度和距离
    angle = random.uniform(0, 2 * math.pi)
    distance = random.uniform(min_distance, max_distance)
    # 计算新坐标
    new_x = current_x + distance * math.cos(angle)
    new_y = current_y + distance * math.sin(angle)
    return (new_x, new_y)


def main():
    console = Console()

    gain_scheduling_cfg = PLANE_GAIN_SCHEDULING_CONFIG
    pid_reset_cfg = PLANE_PID_RESET_ON_APPROACH
    gain_scheduling_enabled = gain_scheduling_cfg['enabled']
    pid_reset_enabled = pid_reset_cfg['enabled']

    # 根据配置决定使用固定航点还是随机航点
    if PLANE_USE_RANDOM_WAYPOINTS:
        mode_info = f"[dim]模式: 随机航点生成 (距离: {PLANE_RANDOM_MIN_DISTANCE}~{PLANE_RANDOM_MAX_DISTANCE}m)[/dim]"
    else:
        waypoints_str = "\n".join([f"    航点{i}: ({wp[0]:.2f}, {wp[1]:.2f})m" for i, wp in enumerate(WAYPOINTS)])
        mode_info = f"[dim]航点数量: {len(WAYPOINTS)}[/dim]\n[dim]{waypoints_str}[/dim]"

    auto_mode_info = "[yellow]自动模式: 已启用[/yellow]" if PLANE_AUTO_NEXT_WAYPOINT else "[dim]手动模式: 到达后需按Enter[/dim]"

    # 控制特性说明
    features = []
    if gain_scheduling_enabled:
        features.append(f"[green]增益调度[/green] (远:{gain_scheduling_cfg['distance_far']}m, 近:{gain_scheduling_cfg['distance_near']}m)")
    if pid_reset_enabled:
        features.append(f"[green]PID重置[/green] (mask:{pid_reset_cfg['reset_mask']}, 触发距离:<{pid_reset_cfg['trigger_distance']}m, 静音:{pid_reset_cfg['mute_duration']}s)")
    features_info = " | ".join(features) if features else "[dim]基础PID控制[/dim]"

    console.print(Panel.fit(
        "[bold cyan]平面位置PID控制器 - 重构版本[/bold cyan]\n"
        f"{mode_info}\n"
        f"{auto_mode_info}\n"
        f"[dim]到达阈值: {TOLERANCE_XY*100:.1f} cm[/dim]\n"
        f"[dim]PID参数: Kp={KP_XY}, Ki={KI_XY}, Kd={KD_XY}[/dim]\n"
        f"[bold]控制特性:[/bold] {features_info}",
        border_style="cyan"
    ))

    # 1. 连接VRPN客户端
    console.print("\n[cyan]━━━ 步骤 1/3: 连接VRPN动捕系统 ━━━[/cyan]")
    try:
        vrpn_client = VRPNClient(device_name=VRPN_DEVICE)
        console.print(f"[green]✓ VRPN客户端已连接: {VRPN_DEVICE}[/green]")
    except Exception as e:
        console.print(f"[red]✗ VRPN连接失败: {e}[/red]")
        return 1

    # 2. 连接MQTT客户端
    console.print("\n[cyan]━━━ 步骤 2/3: 连接MQTT ━━━[/cyan]")
    mqtt_client = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
    try:
        mqtt_client.connect()
        console.print(f"[green]✓ MQTT已连接: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}[/green]")
    except Exception as e:
        console.print(f"[red]✗ MQTT连接失败: {e}[/red]")
        vrpn_client.stop()
        return 1

    # 3. 启动心跳
    console.print("\n[cyan]━━━ 步骤 3/3: 启动心跳 ━━━[/cyan]")
    heartbeat_thread = start_heartbeat(mqtt_client, interval=0.2)
    console.print("[green]✓ 心跳已启动 (5.0Hz)[/green]")

    # 4. 初始化控制器和航点
    controller = PlaneController(
        KP_XY, KI_XY, KD_XY,
        MAX_STICK_OUTPUT,
        enable_gain_scheduling=gain_scheduling_enabled,
        gain_schedule_profile=gain_scheduling_cfg.get('profile')
    )

    # 应用配置的增益调度参数
    if gain_scheduling_enabled:
        controller.distance_far = gain_scheduling_cfg['distance_far']
        controller.distance_near = gain_scheduling_cfg['distance_near']

    # 初始化航点
    if PLANE_USE_RANDOM_WAYPOINTS:
        # 随机模式：获取当前位置作为起点
        console.print("[yellow]等待初始位置数据...[/yellow]")
        while vrpn_client.pose is None:
            time.sleep(0.1)
        pose = vrpn_client.pose
        current_x, current_y = pose.position[0], pose.position[1]
        target_waypoint = (0, 0)  # 第一个目标是原点
        waypoint_index = 0
    else:
        waypoint_index = 0
        target_waypoint = WAYPOINTS[waypoint_index]

    # 5. 初始化数据记录器
    logger = DataLogger(
        enabled=ENABLE_DATA_LOGGING,
        field_set='plane_only',
        csv_name='plane_control_data.csv',
        subdir='plane'
    )
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    if PLANE_USE_RANDOM_WAYPOINTS:
        console.print(f"[cyan]首个目标: 航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/cyan]")
    else:
        console.print(f"[cyan]首个目标: 航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/cyan]")
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    # 控制循环
    control_interval = 1.0 / CONTROL_FREQUENCY
    reached = False
    in_tolerance_since = None  # 记录进入阈值范围的时间戳
    control_start_time = time.time()  # 记录开始控制的时间
    loop_count = 0  # 循环计数器
    pid_has_reset = False  # 记录当前航点是否已触发PID重置
    pid_mute_until = 0  # 记录PID静音结束的时间戳（0表示未静音）

    try:
        while True:
            loop_start = time.time()
            loop_count += 1

            # 读取VRPN位置
            pose = vrpn_client.pose
            if pose is None:
                time.sleep(0.1)
                continue

            current_x, current_y = pose.position[0], pose.position[1]
            target_x, target_y = target_waypoint
            distance = controller.get_distance(target_x, target_y, current_x, current_y)

            # 判断是否到达（带时间稳定性检查）
            if not reached:
                # 【PID重置】当距离进入触发范围时，第一次触发重置（防止积分饱和）
                if pid_reset_enabled and not pid_has_reset:
                    trigger_distance = pid_reset_cfg['trigger_distance']
                    if distance < trigger_distance:
                        console.print(f"[magenta]▶ 进入触发距离 ({distance*100:.1f}cm < {trigger_distance*100:.0f}cm)，触发PID重置 (mask:{pid_reset_cfg['reset_mask']})[/magenta]")
                        controller.selective_reset(pid_reset_cfg['reset_mask'])

                        # 设置PID静音时间，在此期间只发送归中杆量
                        mute_duration = pid_reset_cfg['mute_duration']
                        pid_mute_until = time.time() + mute_duration
                        console.print(f"[magenta]✓ PID重置完成，开始静音 {mute_duration}s（只发送归中杆量）[/magenta]")
                        pid_has_reset = True

                if distance < TOLERANCE_XY:
                    # 进入阈值范围
                    if in_tolerance_since is None:
                        in_tolerance_since = time.time()
                        console.print(f"[yellow]⏱ 进入阈值范围 (距离:{distance*100:.2f}cm)，等待稳定 {PLANE_ARRIVAL_STABLE_TIME}s...[/yellow]")
                    else:
                        # 检查是否已稳定足够时间
                        stable_duration = time.time() - in_tolerance_since
                        if stable_duration >= PLANE_ARRIVAL_STABLE_TIME:
                            # 真正到达！
                            total_control_time = time.time() - control_start_time

                            # 计算下一个航点
                            if PLANE_USE_RANDOM_WAYPOINTS:
                                next_waypoint = generate_random_waypoint(
                                    current_x, current_y,
                                    PLANE_RANDOM_MIN_DISTANCE,
                                    PLANE_RANDOM_MAX_DISTANCE
                                )
                                next_index = waypoint_index + 1
                                waypoint_desc = f"随机航点{next_index}"
                            else:
                                next_index = (waypoint_index + 1) % len(WAYPOINTS)
                                next_waypoint = WAYPOINTS[next_index]
                                waypoint_desc = f"航点{next_index}"

                            console.print(f"\n[bold green]✓ 已到达航点{waypoint_index} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m！[/bold green]")
                            console.print(f"[dim]最终距离: {distance*100:.2f} cm | 稳定时长: {stable_duration:.2f}s | 控制用时: {total_control_time:.2f}s[/dim]")

                            if PLANE_AUTO_NEXT_WAYPOINT:
                                console.print(f"[cyan]自动切换 → {waypoint_desc} - ({next_waypoint[0]:.2f}, {next_waypoint[1]:.2f})m (按Ctrl+C退出)[/cyan]\n")
                            else:
                                console.print(f"[yellow]按 Enter 前往 {waypoint_desc} - ({next_waypoint[0]:.2f}, {next_waypoint[1]:.2f})m，或Ctrl+C退出...[/yellow]\n")

                            # 悬停并重置PID
                            for _ in range(5):
                                send_stick_control(mqtt_client)
                                time.sleep(0.01)
                            controller.reset()
                            reached = True
                            in_tolerance_since = None

                            # 根据模式决定是否等待用户输入
                            if PLANE_AUTO_NEXT_WAYPOINT:
                                # 自动模式：直接切换
                                waypoint_index = next_index
                                target_waypoint = next_waypoint
                                console.print(f"[bold cyan]→ {waypoint_desc} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/bold cyan]\n")
                                reached = False
                                control_start_time = time.time()
                                loop_count = 0
                                pid_has_reset = False  # 重置PID重置标志
                                pid_mute_until = 0  # 重置静音标志
                            else:
                                # 手动模式：等待键盘输入
                                try:
                                    input()
                                    waypoint_index = next_index
                                    target_waypoint = next_waypoint
                                    console.print(f"[bold cyan]切换目标 → {waypoint_desc} - ({target_waypoint[0]:.2f}, {target_waypoint[1]:.2f})m[/bold cyan]\n")
                                    reached = False
                                    control_start_time = time.time()
                                    loop_count = 0
                                    pid_has_reset = False  # 重置PID重置标志
                                    pid_mute_until = 0  # 重置静音标志
                                except KeyboardInterrupt:
                                    break
                            continue
                else:
                    # 离开阈值范围，重置计时器
                    if in_tolerance_since is not None:
                        console.print(f"[yellow]✗ 偏离目标 (距离:{distance*100:.2f}cm)，重置稳定计时[/yellow]")
                        in_tolerance_since = None

                # PID计算并发送控制指令
                current_time = time.time()

                # 检查是否处于PID静音期（重置后强制归中）
                if current_time < pid_mute_until:
                    # 静音期：只发送归中杆量，不执行PID计算
                    roll = NEUTRAL
                    pitch = NEUTRAL
                    send_stick_control(mqtt_client, roll=roll, pitch=pitch)

                    # 为了日志记录，设置零偏移和零PID分量
                    roll_offset = 0
                    pitch_offset = 0
                    pid_components = {
                        'x': (0, 0, 0),
                        'y': (0, 0, 0)
                    }
                else:
                    # 正常PID控制
                    roll_offset, pitch_offset, pid_components = controller.compute(
                        target_x, target_y,
                        current_x, current_y,
                        current_time
                    )

                    roll = int(NEUTRAL + roll_offset)
                    pitch = int(NEUTRAL + pitch_offset)
                    send_stick_control(mqtt_client, roll=roll, pitch=pitch)

            # 每10次循环打印详细信息
            if loop_count % 2 == 0:
                error_x = target_x - current_x
                error_y = target_y - current_y
                kp_scale = controller.x_pid.kp / controller.kp_base if gain_scheduling_enabled else 1.0
                kd_scale = controller.x_pid.kd / controller.kd_base if gain_scheduling_enabled else 1.0
                info_parts = [
                    f"[cyan]#{loop_count:04d}[/cyan]",
                    f"WP{waypoint_index}",
                    f"目标({target_x:+.2f},{target_y:+.2f})",
                    f"当前({current_x:+.2f},{current_y:+.2f})",
                    f"距{distance*100:5.1f}cm"
                ]
                if gain_scheduling_enabled:
                    info_parts.append(f"[yellow]Kp×{kp_scale:.2f} Kd×{kd_scale:.2f}[/yellow]")

                # 显示是否处于静音期
                if current_time < pid_mute_until:
                    remaining_mute = pid_mute_until - current_time
                    info_parts.append(f"[magenta]MUTE({remaining_mute:.1f}s)[/magenta]")

                info_parts.append(f"Out:P{pitch_offset:+5.0f}/R{roll_offset:+5.0f}")
                info_parts.append(f"X(P{pid_components['x'][0]:+5.0f}/I{pid_components['x'][1]:+5.0f}/D{pid_components['x'][2]:+5.0f})")
                info_parts.append(f"Y(P{pid_components['y'][0]:+5.0f}/I{pid_components['y'][1]:+5.0f}/D{pid_components['y'][2]:+5.0f})")
                console.print(" | ".join(info_parts))


                # 记录数据（包含PID分量）
                error_x = target_x - current_x
                error_y = target_y - current_y
                logger.log(
                    timestamp=current_time,
                    target_x=target_x,
                    target_y=target_y,
                    current_x=current_x,
                    current_y=current_y,
                    error_x=error_x,
                    error_y=error_y,
                    distance=distance,
                    roll_offset=roll_offset,
                    pitch_offset=pitch_offset,
                    roll_absolute=roll,
                    pitch_absolute=pitch,
                    waypoint_index=waypoint_index,
                    # PID components for X (Pitch)
                    x_pid_p=pid_components['x'][0],
                    x_pid_i=pid_components['x'][1],
                    x_pid_d=pid_components['x'][2],
                    # PID components for Y (Roll)
                    y_pid_p=pid_components['y'][0],
                    y_pid_i=pid_components['y'][1],
                    y_pid_d=pid_components['y'][2]
                )


                # 精确控制循环频率
                sleep_time = control_interval - (time.time() - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠ 收到中断信号[/yellow]\n")
    except Exception as e:
        console.print(f"\n\n[red]✗ 发生错误: {e}[/red]")
        console.print(f"[red]错误类型: {type(e).__name__}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
    finally:
        console.print("[cyan]━━━ 清理资源 ━━━[/cyan]")

        # 关闭数据记录器
        logger.close()

        console.print("[yellow]发送悬停指令...[/yellow]")
        for _ in range(5):
            send_stick_control(mqtt_client)
            time.sleep(0.1)
        stop_heartbeat(heartbeat_thread)
        console.print("[green]✓ 心跳已停止[/green]")
        mqtt_client.disconnect()
        console.print("[green]✓ MQTT已断开[/green]")
        vrpn_client.stop()
        console.print("[green]✓ VRPN已断开[/green]")
        console.print("\n[bold green]✓ 已安全退出[/bold green]\n")
    return 0


if __name__ == '__main__':
    exit(main())
