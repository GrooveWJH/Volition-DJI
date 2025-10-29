#!/usr/bin/env python3
"""
Yaw角PID控制器 - 主程序
使用统一的control模块重构版本

功能：
- 使用VRPN姿态数据作为反馈
- 通过PID算法控制无人机旋转到目标Yaw角
- 只控制Yaw角，不控制位置和高度
- 支持多个目标角度循环测试

使用方法：
1. 手动让无人机起飞到1m高度
2. 启动本程序: python control/yaw_main.py
3. 无人机按顺序旋转到各个目标角度
4. 每到达一个角度，等待按 Enter 键
5. 自动前往下一个目标角度，循环往复
6. 按 Ctrl+C 退出程序
"""

import time
import os
import sys

# 添加父目录到路径，确保能导入djisdk和vrpn
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from djisdk import MQTTClient, start_heartbeat, stop_heartbeat, send_stick_control
from vrpn import VRPNClient
from rich.console import Console
from rich.panel import Panel

# 导入control模块
from .config import *
from .controller import YawOnlyController, quaternion_to_yaw, get_yaw_error
from .logger import DataLogger


def main():
    console = Console()
    targets_str = "\n".join([f"    目标{i}: {yaw}°" for i, yaw in enumerate(TARGET_YAWS)])
    console.print(Panel.fit(
        "[bold cyan]Yaw角PID控制器 - 重构版本[/bold cyan]\n"
        f"[dim]目标数量: {len(TARGET_YAWS)}[/dim]\n"
        f"[dim]{targets_str}[/dim]\n"
        f"[dim]到达阈值: ±{TOLERANCE_YAW_ONLY:.1f}°[/dim]\n"
        f"[dim]PID参数: Kp={KP_YAW_ONLY}, Ki={KI_YAW_ONLY}, Kd={KD_YAW_ONLY}[/dim]",
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

    # 4. 初始化控制器和目标
    controller = YawOnlyController(KP_YAW_ONLY, KI_YAW_ONLY, KD_YAW_ONLY, MAX_YAW_STICK_OUTPUT)
    target_index = 0
    target_yaw = TARGET_YAWS[target_index]

    # 5. 初始化数据记录器
    logger = DataLogger(
        enabled=ENABLE_DATA_LOGGING,
        field_set='yaw_only',
        csv_name='yaw_control_data.csv',
        subdir='yaw'
    )
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    console.print(f"[cyan]首个目标: 目标{target_index} - {target_yaw}°[/cyan]")
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    # 控制循环
    control_interval = 1.0 / CONTROL_FREQUENCY_YAW
    reached = False
    in_tolerance_since = None  # 记录进入阈值范围的时间戳

    try:
        while True:
            loop_start = time.time()

            # 读取VRPN姿态
            pose = vrpn_client.pose
            if pose is None:
                console.print("[yellow]⚠ 等待VRPN数据...[/yellow]")
                time.sleep(0.1)
                continue

            current_yaw = quaternion_to_yaw(pose.quaternion)
            error_yaw = get_yaw_error(target_yaw, current_yaw)
            abs_error = abs(error_yaw)

            # 判断是否到达（带时间稳定性检查）
            if not reached:
                if abs_error < TOLERANCE_YAW_ONLY:
                    # 进入阈值范围
                    if in_tolerance_since is None:
                        in_tolerance_since = time.time()
                        console.print(f"[yellow]⏱ 进入阈值范围 (误差:{error_yaw:+.2f}°)，等待稳定 {ARRIVAL_STABLE_TIME}s...[/yellow]")
                    else:
                        # 检查是否已稳定足够时间
                        stable_duration = time.time() - in_tolerance_since
                        if stable_duration >= ARRIVAL_STABLE_TIME:
                            # 真正到达！
                            next_index = (target_index + 1) % len(TARGET_YAWS)
                            next_target = TARGET_YAWS[next_index]

                            console.print(f"\n[bold green]✓ 已到达目标{target_index} - {target_yaw}°！[/bold green]")
                            console.print(f"[dim]最终误差: {error_yaw:+.2f}° | 稳定时长: {stable_duration:.2f}s[/dim]")
                            console.print(f"[yellow]按 Enter 前往目标{next_index} - {next_target}°，或Ctrl+C退出...[/yellow]\n")

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
                                target_index = next_index
                                target_yaw = next_target
                                console.print(f"[bold cyan]切换目标 → 目标{target_index} - {target_yaw}°[/bold cyan]\n")
                                reached = False
                            except KeyboardInterrupt:
                                break
                            continue
                else:
                    # 离开阈值范围，重置计时器
                    if in_tolerance_since is not None:
                        console.print(f"[yellow]✗ 偏离目标 (误差:{error_yaw:+.2f}°)，重置稳定计时[/yellow]")
                        in_tolerance_since = None

            # PID计算并发送控制指令
            current_time = time.time()
            yaw_offset = controller.compute(target_yaw, current_yaw, current_time)
            yaw = int(NEUTRAL + yaw_offset)
            send_stick_control(mqtt_client, yaw=yaw)

            # 记录数据
            logger.log_yaw_only(
                timestamp=current_time,
                target_yaw=target_yaw,
                current_yaw=current_yaw,
                error_yaw=error_yaw,
                yaw_offset=yaw_offset,
                yaw_absolute=yaw,
                target_index=target_index
            )

            # 每次循环都打印状态（实时监控杆量输出）
            console.print(
                f"[cyan]目标: {target_yaw:+6.1f}° | "
                f"当前: {current_yaw:+6.1f}° | "
                f"误差: {error_yaw:+6.2f}° | "
                f"杆量: {yaw_offset:+6.0f} ({yaw})[/cyan]"
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