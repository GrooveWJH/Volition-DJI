#!/usr/bin/env python3
"""
MPC平面控制器 - 主程序

解决200ms MQTT延迟的预测控制方案

运行流程：
1. 系统辨识阶段 (10-15秒)：发送激励信号，学习无人机动态模型
2. MPC控制阶段：使用学习的模型进行预测控制
3. 自动延迟补偿：实时估计状态，补偿通信延迟

核心优势：
- 预测式控制 vs PID反应式
- 自动模型学习，无需手动调参
- 延迟感知，充分利用系统动态特性

使用方法：
1. 手动起飞到1m高度
2. 运行: python control_mpc/mpc_main.py
3. 系统自动完成辨识→控制切换
"""

import time
import os
import sys
import numpy as np
from typing import Tuple, List

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from djisdk import MQTTClient, start_heartbeat, stop_heartbeat, send_stick_control
from vrpn import VRPNClient
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# 导入control模块 (复用配置)
from control.config import *
from control.logger import DataLogger

# 导入MPC模块
from control_mpc.mpc_controller import MPCController
from control_mpc.system_id import SystemIdentification
from control_mpc.delay_compensator import DelayCompensator

console = Console()

class MPCPlaneController:
    """MPC平面控制器主类"""

    def __init__(self):
        self.phase = "initialization"  # 控制阶段: initialization -> identification -> mpc_control

        # 核心组件
        self.mpc = MPCController(prediction_horizon=10, control_horizon=5)
        self.sysid = SystemIdentification(dt=1.0/CONTROL_FREQUENCY)
        self.delay_comp = DelayCompensator(dt=1.0/CONTROL_FREQUENCY)

        # 连接组件
        self.mqtt_client = None
        self.vrpn_client = None
        self.heartbeat_thread = None
        self.logger = None

        # 控制参数
        self.control_frequency = CONTROL_FREQUENCY
        self.dt = 1.0 / CONTROL_FREQUENCY
        self.waypoint_index = 0
        self.target_waypoint = WAYPOINTS[0] if WAYPOINTS else (0.0, 0.0)

        # 辨识参数
        self.identification_duration = 12.0  # 辨识持续时间 (秒)
        self.identification_start_time = None

        # 状态跟踪
        self.current_state = np.zeros(4)  # [x, y, vx, vy]
        self.last_measurement_time = 0.0
        self.control_start_time = None

        console.print(f"[green]✓ MPC控制器主类初始化完成[/green]")

    def initialize_connections(self) -> bool:
        """初始化所有连接 (VRPN + MQTT + 心跳)"""
        console.print("\n[cyan]━━━ 步骤 1/3: 连接VRPN动捕系统 ━━━[/cyan]")
        try:
            self.vrpn_client = VRPNClient(device_name=VRPN_DEVICE)
            console.print(f"[green]✓ VRPN客户端已连接: {VRPN_DEVICE}[/green]")
        except Exception as e:
            console.print(f"[red]✗ VRPN连接失败: {e}[/red]")
            return False

        console.print("\n[cyan]━━━ 步骤 2/3: 连接MQTT ━━━[/cyan]")
        self.mqtt_client = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
        try:
            self.mqtt_client.connect()
            console.print(f"[green]✓ MQTT已连接: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}[/green]")
        except Exception as e:
            console.print(f"[red]✗ MQTT连接失败: {e}[/red]")
            self.vrpn_client.stop()
            return False

        console.print("\n[cyan]━━━ 步骤 3/3: 启动心跳 ━━━[/cyan]")
        self.heartbeat_thread = start_heartbeat(self.mqtt_client, interval=0.2)
        console.print("[green]✓ 心跳已启动 (5.0Hz)[/green]")

        # 初始化数据记录器
        self.logger = DataLogger(
            enabled=ENABLE_DATA_LOGGING,
            field_set='mpc_control',
            csv_name='mpc_control_data.csv',
            subdir='mpc'
        )

        if self.logger.enabled:
            console.print(f"[green]✓ 数据记录已启用: {self.logger.get_log_dir()}[/green]")

        return True

    def wait_for_stable_position(self) -> bool:
        """等待无人机位置稳定"""
        console.print("[yellow]等待无人机位置稳定...[/yellow]")

        stable_count = 0
        required_stable_count = 50  # 1秒稳定 @ 50Hz

        while stable_count < required_stable_count:
            pose = self.vrpn_client.pose
            if pose is None:
                time.sleep(0.02)
                continue

            # 检查位置变化是否在合理范围内
            if hasattr(self, 'last_pose') and self.last_pose is not None:
                pos_change = np.linalg.norm(np.array(pose.position[:2]) - np.array(self.last_pose.position[:2]))
                if pos_change < 0.01:  # 1cm变化阈值
                    stable_count += 1
                else:
                    stable_count = 0

            self.last_pose = pose
            time.sleep(0.02)

        console.print("[green]✓ 位置已稳定，准备开始控制[/green]")
        return True

    def system_identification_phase(self) -> bool:
        """系统辨识阶段"""
        console.print(f"\n[bold cyan]═══ 阶段1: 系统辨识 (持续 {self.identification_duration}s) ═══[/bold cyan]")
        console.print("[yellow]⚠ 无人机将执行激励动作以学习动态特性，请确保安全空间充足[/yellow]")

        input("按 Enter 开始系统辨识...")

        self.phase = "identification"
        self.identification_start_time = time.time()

        # 进度显示
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=False
        ) as progress:
            task = progress.add_task("执行系统辨识...", total=None)

            loop_count = 0

            while True:
                loop_start = time.time()

                # 检查辨识时间
                elapsed = time.time() - self.identification_start_time
                if elapsed >= self.identification_duration:
                    break

                # 获取当前状态
                pose = self.vrpn_client.pose
                if pose is None:
                    time.sleep(0.02)
                    continue

                current_time = time.time()
                x, y = pose.position[0], pose.position[1]

                # 计算速度 (数值微分)
                if hasattr(self, 'last_x') and hasattr(self, 'last_time'):
                    dt_actual = current_time - self.last_time
                    if dt_actual > 0:
                        vx = (x - self.last_x) / dt_actual
                        vy = (y - self.last_y) / dt_actual
                    else:
                        vx = vy = 0.0
                else:
                    vx = vy = 0.0

                state = np.array([x, y, vx, vy])

                # 生成激励信号
                excitation_signal = self.sysid.generate_excitation_signal(elapsed, "chirp")

                # 发送控制命令
                pitch = int(NEUTRAL + excitation_signal[0])
                roll = int(NEUTRAL + excitation_signal[1])
                send_stick_control(self.mqtt_client, roll=roll, pitch=pitch)

                # 记录数据
                self.sysid.add_data_point(state, excitation_signal, current_time)
                self.delay_comp.send_command(excitation_signal)

                # 更新进度
                progress_percent = (elapsed / self.identification_duration) * 100
                progress.update(task, description=f"系统辨识进行中... {progress_percent:.1f}% ({loop_count}次迭代)")

                # 记录上一次状态
                self.last_x, self.last_y, self.last_time = x, y, current_time
                loop_count += 1

                # 精确控制频率
                sleep_time = self.dt - (time.time() - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        # 停止激励，悬停
        console.print("[yellow]停止激励信号，悬停稳定...[/yellow]")
        for _ in range(10):
            send_stick_control(self.mqtt_client)
            time.sleep(0.1)

        # 执行系统辨识
        console.print("[cyan]分析数据，识别系统模型...[/cyan]")
        success, info = self.sysid.identify_model(delay_steps=10)

        if success:
            console.print(f"[green]✓ 系统辨识成功！模型质量: R² = {info['model_quality']:.3f}[/green]")

            # 设置MPC模型
            A, B = self.sysid.get_current_model()
            self.mpc.set_model(A, B)
            self.delay_comp.set_system_model(A, B)

            # 保存模型
            model_path = "control_mpc/identified_model.json"
            self.sysid.save_model(model_path)

            return True
        else:
            console.print(f"[red]✗ 系统辨识失败: {info}[/red]")
            return False

    def mpc_control_phase(self):
        """MPC控制阶段"""
        console.print(f"\n[bold cyan]═══ 阶段2: MPC预测控制 ═══[/bold cyan]")
        console.print(f"[cyan]目标航点: ({self.target_waypoint[0]:.2f}, {self.target_waypoint[1]:.2f})m[/cyan]")

        self.phase = "mpc_control"
        self.control_start_time = time.time()

        loop_count = 0
        reached = False
        in_tolerance_since = None

        try:
            while True:
                loop_start = time.time()
                loop_count += 1

                # 获取当前测量
                pose = self.vrpn_client.pose
                if pose is None:
                    time.sleep(0.02)
                    continue

                measurement_time = time.time()
                x, y = pose.position[0], pose.position[1]

                # 计算速度
                if hasattr(self, 'last_x') and hasattr(self, 'last_time'):
                    dt_actual = measurement_time - self.last_time
                    if dt_actual > 0:
                        vx = (x - self.last_x) / dt_actual
                        vy = (y - self.last_y) / dt_actual
                    else:
                        vx = vy = 0.0
                else:
                    vx = vy = 0.0

                measured_state = np.array([x, y, vx, vy])

                # 延迟补偿：估计真实当前状态
                estimated_state, comp_info = self.delay_comp.estimate_current_state(
                    measured_state, measurement_time
                )

                # 构建参考轨迹 (简单：目标点悬停)
                target_x, target_y = self.target_waypoint
                reference_trajectory = [(target_x, target_y)] * 10  # 10步都是同一目标

                # 获取延迟命令历史
                buffer_state = self.delay_comp.get_command_buffer_state()
                delayed_commands = list(self.delay_comp.command_buffer)

                # MPC控制计算
                control, mpc_info = self.mpc.compute_control(
                    estimated_state, reference_trajectory, delayed_commands
                )

                # 发送控制命令
                if mpc_info["status"] == "success":
                    pitch = int(NEUTRAL + control[0])
                    roll = int(NEUTRAL + control[1])
                    send_stick_control(self.mqtt_client, roll=roll, pitch=pitch)

                    # 记录到延迟补偿器
                    self.delay_comp.send_command(control)
                else:
                    # MPC失败时发送悬停命令
                    send_stick_control(self.mqtt_client)
                    self.delay_comp.send_command(np.zeros(2))

                # 到达检测
                distance = np.linalg.norm(estimated_state[:2] - np.array([target_x, target_y]))

                if distance < TOLERANCE_XY:
                    if in_tolerance_since is None:
                        in_tolerance_since = time.time()
                        console.print(f"[yellow]⏱ 进入阈值范围 (距离:{distance*100:.2f}cm)...[/yellow]")
                    elif time.time() - in_tolerance_since >= PLANE_ARRIVAL_STABLE_TIME:
                        console.print(f"[bold green]✓ 已到达目标！[/bold green]")
                        reached = True
                        break
                else:
                    if in_tolerance_since is not None:
                        console.print(f"[yellow]✗ 偏离目标 (距离:{distance*100:.2f}cm)[/yellow]")
                        in_tolerance_since = None

                # 定期打印状态
                if loop_count % 10 == 0:
                    info_parts = [
                        f"[cyan]#{loop_count:04d}[/cyan]",
                        f"目标({target_x:+.2f},{target_y:+.2f})",
                        f"测量({x:+.2f},{y:+.2f})",
                        f"估计({estimated_state[0]:+.2f},{estimated_state[1]:+.2f})",
                        f"距{distance*100:5.1f}cm",
                        f"MPC:{mpc_info['status'][:3]}",
                        f"延迟补偿:{comp_info.get('prediction_steps', 0)}步",
                        f"控制[{control[0]:+5.0f},{control[1]:+5.0f}]"
                    ]
                    console.print(" | ".join(info_parts))

                # 数据记录
                if self.logger and self.logger.enabled:
                    self.logger.log(
                        timestamp=measurement_time,
                        target_x=target_x,
                        target_y=target_y,
                        measured_x=x,
                        measured_y=y,
                        estimated_x=estimated_state[0],
                        estimated_y=estimated_state[1],
                        estimated_vx=estimated_state[2],
                        estimated_vy=estimated_state[3],
                        distance=distance,
                        mpc_pitch=control[0],
                        mpc_roll=control[1],
                        mpc_cost=mpc_info.get('cost', 0),
                        delay_compensation=comp_info.get('compensation', 'unknown'),
                        prediction_steps=comp_info.get('prediction_steps', 0)
                    )

                # 记录状态历史
                self.last_x, self.last_y, self.last_time = x, y, measurement_time

                # 控制频率
                sleep_time = self.dt - (time.time() - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ 收到中断信号[/yellow]")

    def cleanup(self):
        """清理资源"""
        console.print("\n[cyan]━━━ 清理资源 ━━━[/cyan]")

        # 发送悬停指令
        console.print("[yellow]发送悬停指令...[/yellow]")
        if self.mqtt_client:
            for _ in range(5):
                send_stick_control(self.mqtt_client)
                time.sleep(0.1)

        # 关闭组件
        if self.logger:
            self.logger.close()

        if self.heartbeat_thread:
            stop_heartbeat(self.heartbeat_thread)
            console.print("[green]✓ 心跳已停止[/green]")

        if self.mqtt_client:
            self.mqtt_client.disconnect()
            console.print("[green]✓ MQTT已断开[/green]")

        if self.vrpn_client:
            self.vrpn_client.stop()
            console.print("[green]✓ VRPN已断开[/green]")

        console.print("\n[bold green]✓ 已安全退出[/bold green]\n")

    def run(self):
        """主运行函数"""
        console.print(Panel.fit(
            "[bold cyan]MPC平面控制器 - 解决200ms延迟的预测控制[/bold cyan]\n"
            "[dim]核心优势:[/dim]\n"
            "[green]• 预测式控制 (vs PID反应式)[/green]\n"
            "[green]• 自动模型学习 (vs 手动调参)[/green]\n"
            "[green]• 延迟感知补偿 (vs 盲目响应)[/green]\n"
            f"[dim]目标航点: ({self.target_waypoint[0]:.2f}, {self.target_waypoint[1]:.2f})m[/dim]\n"
            f"[dim]控制频率: {self.control_frequency}Hz[/dim]",
            border_style="cyan"
        ))

        try:
            # 1. 初始化连接
            if not self.initialize_connections():
                return 1

            # 2. 等待位置稳定
            if not self.wait_for_stable_position():
                return 1

            # 3. 系统辨识阶段
            if not self.system_identification_phase():
                console.print("[red]✗ 系统辨识失败，无法进行MPC控制[/red]")
                return 1

            # 4. MPC控制阶段
            self.mpc_control_phase()

            return 0

        except Exception as e:
            console.print(f"\n[red]✗ 发生未预期错误: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return 1

        finally:
            self.cleanup()

def main():
    """主入口函数"""
    controller = MPCPlaneController()
    return controller.run()

if __name__ == '__main__':
    exit(main())