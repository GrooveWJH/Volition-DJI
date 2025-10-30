#!/usr/bin/env python3
"""
PID平面定位控制器 - 多航点循环模式（模块化版本）

功能：
- 使用VRPN位置数据作为反馈
- 通过PID算法控制无人机飞到目标点
- 支持XY平面+Yaw角控制
- 模块化设计，支持从任意目录运行

坐标映射：
- X轴（前方向，x变大）→ Pitch杆量（正值）
- Y轴（左方向，y变大）→ Roll杆量（负值）
- Yaw角（逆时针为正）→ Yaw杆量（正值）

使用方法：
1. 手动让无人机起飞到1m高度
2. 从任意目录运行: python control/main.py 或 python main.py
3. 无人机按顺序飞到各个航点
4. 按 Ctrl+C 退出程序
"""

import sys
import os
import time
import math

# 添加pythonSDK到路径（支持从任意目录运行）
script_dir = os.path.dirname(os.path.abspath(__file__))
sdk_dir = os.path.dirname(script_dir)  # pythonSDK目录
if sdk_dir not in sys.path:
    sys.path.insert(0, sdk_dir)

# 导入DJI SDK
from djisdk import MQTTClient, start_heartbeat, stop_heartbeat, send_stick_control
from vrpn import VRPNClient
from rich.console import Console
from rich.panel import Panel

# 导入控制模块
from control.config import *
from control.controller import PlaneYawController
from control.logger import DataLogger


def quaternion_to_yaw(quaternion):
    """
    从四元数计算Yaw角（绕Z轴旋转）

    Args:
        quaternion: (x, y, z, w) 四元数

    Returns:
        float: Yaw角（度），范围 -180~180
    """
    x, y, z, w = quaternion
    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw_rad = math.atan2(siny_cosp, cosy_cosp)
    yaw_deg = math.degrees(yaw_rad)
    return yaw_deg


def main():
    console = Console()
    waypoints_str = "\n".join([f"    航点{i}: {wp}" for i, wp in enumerate(WAYPOINTS)])
    console.print(Panel.fit(
        "[bold cyan]PID平面定位控制器 - 多航点循环模式 (带Yaw控制)[/bold cyan]\n"
        f"[dim]航点数量: {len(WAYPOINTS)}[/dim]\n"
        f"[dim]{waypoints_str}[/dim]\n"
        f"[dim]XY阈值: {TOLERANCE_XY*100:.1f} cm | Yaw阈值: {TOLERANCE_YAW:.1f}°[/dim]",
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
    controller = PlaneYawController(
        kp_xy=KP_XY, ki_xy=KI_XY, kd_xy=KD_XY,
        kp_yaw=KP_YAW, ki_yaw=KI_YAW, kd_yaw=KD_YAW,
        output_limit=MAX_STICK_OUTPUT
    )
    waypoint_index = 0
    current_waypoint = WAYPOINTS[waypoint_index]
    target_yaw = 0.0  # 目标朝向（可扩展为航点属性）

    # 5. 初始化数据记录器
    logger = DataLogger(enabled=ENABLE_DATA_LOGGING)
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    console.print(f"[cyan]首个目标: 航点{waypoint_index} - {current_waypoint} | Yaw: {target_yaw:.1f}°[/cyan]")
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    # 控制循环
    control_interval = 1.0 / CONTROL_FREQUENCY
    reached = False
    in_tolerance_since = None

    try:
        while True:
            loop_start = time.time()

            # 读取VRPN位置
            pose = vrpn_client.pose
            if pose is None:
                console.print("[yellow]⚠ 等待VRPN数据...[/yellow]")
                time.sleep(0.1)
                continue

            current_x, current_y = pose.position[0], pose.position[1]
            # 从四元数计算Yaw角
            current_yaw = quaternion_to_yaw(pose.quaternion)

            target_x, target_y = current_waypoint
            distance = controller.get_distance(target_x, target_y, current_x, current_y)
            yaw_error = controller.get_yaw_error(target_yaw, current_yaw)

            # 判断是否到达（XY平面 + Yaw角同时满足）
            if not reached:
                xy_in_tolerance = distance < TOLERANCE_XY
                yaw_in_tolerance = yaw_error < TOLERANCE_YAW

                if xy_in_tolerance and yaw_in_tolerance:
                    if in_tolerance_since is None:
                        in_tolerance_since = time.time()
                        console.print(f"[yellow]⏱ 进入阈值范围 (XY:{distance*100:.2f}cm, Yaw:{yaw_error:.2f}°)，等待稳定 {ARRIVAL_STABLE_TIME}s...[/yellow]")
                    else:
                        stable_duration = time.time() - in_tolerance_since
                        if stable_duration >= ARRIVAL_STABLE_TIME:
                            next_index = (waypoint_index + 1) % len(WAYPOINTS)
                            next_waypoint = WAYPOINTS[next_index]

                            console.print(f"\n[bold green]✓ 已到达航点{waypoint_index} - {current_waypoint}！[/bold green]")
                            console.print(f"[dim]最终距离: {distance*100:.2f} cm | Yaw误差: {yaw_error:.2f}° | 稳定: {stable_duration:.2f}s[/dim]")
                            console.print(f"[yellow]按 Enter 前往航点{next_index} - {next_waypoint}，或Ctrl+C退出...[/yellow]\n")

                            # 悬停并重置PID
                            for _ in range(5):
                                send_stick_control(mqtt_client)
                                time.sleep(0.05)
                            controller.reset()
                            reached = True
                            in_tolerance_since = None

                            # 等待键盘输入
                            try:
                                input()
                                waypoint_index = next_index
                                current_waypoint = next_waypoint
                                console.print(f"[bold cyan]切换目标 → 航点{waypoint_index} - {current_waypoint}[/bold cyan]\n")
                                reached = False
                            except KeyboardInterrupt:
                                break
                            continue
                else:
                    if in_tolerance_since is not None:
                        console.print(f"[yellow]✗ 偏离目标 (XY:{distance*100:.2f}cm, Yaw:{yaw_error:.2f}°)，重置稳定计时[/yellow]")
                        in_tolerance_since = None

            # PID计算并发送控制指令
            current_time = time.time()
            roll_offset, pitch_offset, yaw_offset, pid_components = controller.compute(
                target_x, target_y, target_yaw,
                current_x, current_y, current_yaw,
                current_time
            )
            roll = int(NEUTRAL + roll_offset)
            pitch = int(NEUTRAL + pitch_offset)
            yaw = int(NEUTRAL + yaw_offset)
            send_stick_control(mqtt_client, roll=roll, pitch=pitch, yaw=yaw)

            # 记录数据（包含PID分量）
            error_x = target_x - current_x
            error_y = target_y - current_y
            error_yaw = controller._normalize_angle(target_yaw - current_yaw)
            logger.log(
                timestamp=current_time,
                target_x=target_x, target_y=target_y, target_yaw=target_yaw,
                current_x=current_x, current_y=current_y, current_yaw=current_yaw,
                error_x=error_x, error_y=error_y, error_yaw=error_yaw,
                distance=distance,
                roll_offset=roll_offset, pitch_offset=pitch_offset, yaw_offset=yaw_offset,
                roll_absolute=roll, pitch_absolute=pitch, yaw_absolute=yaw,
                waypoint_index=waypoint_index,
                # PID components for X (Pitch)
                x_pid_p=pid_components['x'][0],
                x_pid_i=pid_components['x'][1],
                x_pid_d=pid_components['x'][2],
                # PID components for Y (Roll)
                y_pid_p=pid_components['y'][0],
                y_pid_i=pid_components['y'][1],
                y_pid_d=pid_components['y'][2],
                # PID components for Yaw
                yaw_pid_p=pid_components['yaw'][0],
                yaw_pid_i=pid_components['yaw'][1],
                yaw_pid_d=pid_components['yaw'][2]
            )

            # 显示状态（每10次循环显示一次）
            if int(time.time() * CONTROL_FREQUENCY) % 10 == 0:
                console.print(
                    f"[cyan]航点{waypoint_index} {current_waypoint} | "
                    f"XY: ({current_x:+.3f}, {current_y:+.3f}) | "
                    f"Yaw: {current_yaw:+.1f}° | "
                    f"误差: XY={distance:.3f}m Yaw={yaw_error:.1f}° | "
                    f"输出: R={roll_offset:+.0f} P={pitch_offset:+.0f} Y={yaw_offset:+.0f}[/cyan]"
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
