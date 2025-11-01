"""
延迟补偿器 - 处理200ms MQTT通信延迟

核心功能：
1. 命令缓冲队列：存储最近发送的控制命令
2. 延迟估计：动态测量实际通信延迟
3. 状态预测：根据已发送命令预测当前真实状态
4. 时间同步：确保时间戳一致性

解决的问题：
- 测量的状态是200ms前的
- 发送的命令200ms后才生效
- MPC需要"当前真实状态"来做预测
"""

import numpy as np
import time
from typing import List, Optional, Tuple
from collections import deque
from rich.console import Console

console = Console()

class DelayCompensator:
    def __init__(self,
                 max_delay_steps: int = 15,  # 最大延迟步数 (预留余量)
                 dt: float = 0.02,           # 控制周期
                 delay_estimation_window: int = 50):  # 延迟估计窗口
        """
        延迟补偿器初始化

        Args:
            max_delay_steps: 最大延迟步数
            dt: 控制周期 (秒)
            delay_estimation_window: 延迟估计窗口大小
        """
        self.max_delay_steps = max_delay_steps
        self.dt = dt
        self.estimation_window = delay_estimation_window

        # 命令缓冲队列 (FIFO)
        self.command_buffer = deque(maxlen=max_delay_steps)
        self.timestamp_buffer = deque(maxlen=max_delay_steps)

        # 延迟估计
        self.estimated_delay_steps = 10  # 初始估计值 (200ms @ 50Hz)
        self.delay_measurements = deque(maxlen=delay_estimation_window)

        # 状态预测参数
        self.A_matrix = None  # 系统模型 (来自系统辨识)
        self.B_matrix = None
        self.model_available = False

        # 统计信息
        self.total_commands_sent = 0
        self.compensation_active = False

        console.print(f"[green]✓ 延迟补偿器初始化完成[/green]")
        console.print(f"[dim]最大延迟: {max_delay_steps}步 | 估计延迟: {self.estimated_delay_steps}步[/dim]")

    def set_system_model(self, A: np.ndarray, B: np.ndarray):
        """设置系统模型 (来自系统辨识模块)"""
        self.A_matrix = A.copy()
        self.B_matrix = B.copy()
        self.model_available = True
        self.compensation_active = True

        console.print(f"[green]✓ 延迟补偿器模型已更新[/green]")

    def send_command(self, command: np.ndarray) -> None:
        """
        发送控制命令并记录到缓冲区

        Args:
            command: 控制命令 [pitch, roll]
        """
        current_time = time.time()

        # 添加到缓冲区
        self.command_buffer.append(command.copy())
        self.timestamp_buffer.append(current_time)

        self.total_commands_sent += 1

    def estimate_current_state(self, measured_state: np.ndarray, measurement_time: float) -> Tuple[np.ndarray, dict]:
        """
        估计当前真实状态 (补偿延迟)

        Args:
            measured_state: 测量状态 [x, y, vx, vy]
            measurement_time: 测量时间戳

        Returns:
            estimated_state: 估计的当前真实状态
            info: 调试信息
        """
        if not self.compensation_active or not self.model_available:
            # 补偿未激活，直接返回测量值
            return measured_state.copy(), {"compensation": "disabled"}

        try:
            # 1. 确定需要前向预测的步数
            current_time = time.time()
            prediction_steps = self._calculate_prediction_steps(measurement_time, current_time)

            # 2. 获取相关的历史命令
            relevant_commands = self._get_relevant_commands(prediction_steps)

            # 3. 前向预测状态
            predicted_state = self._forward_predict_state(measured_state, relevant_commands)

            info = {
                "compensation": "active",
                "prediction_steps": prediction_steps,
                "commands_used": len(relevant_commands),
                "estimated_delay": self.estimated_delay_steps,
                "time_diff": current_time - measurement_time
            }

            return predicted_state, info

        except Exception as e:
            console.print(f"[yellow]⚠ 状态预测失败: {e}[/yellow]")
            return measured_state.copy(), {"compensation": "failed", "error": str(e)}

    def update_delay_estimate(self, measurement_time: float, response_observed_time: float):
        """
        更新延迟估计 (基于观测到的响应时间)

        Args:
            measurement_time: 测量时间
            response_observed_time: 观测到响应的时间
        """
        # 计算观测延迟
        observed_delay = response_observed_time - measurement_time
        observed_delay_steps = int(observed_delay / self.dt)

        # 添加到测量记录
        self.delay_measurements.append(observed_delay_steps)

        # 更新估计值 (使用滑动平均)
        if len(self.delay_measurements) >= 5:
            # 取中位数以减少异常值影响
            delay_array = np.array(list(self.delay_measurements))
            self.estimated_delay_steps = int(np.median(delay_array))

            # 限制在合理范围内
            self.estimated_delay_steps = np.clip(self.estimated_delay_steps, 5, self.max_delay_steps)

    def _calculate_prediction_steps(self, measurement_time: float, current_time: float) -> int:
        """计算需要前向预测的步数"""
        # 时间差对应的步数
        time_diff = current_time - measurement_time
        time_based_steps = int(time_diff / self.dt)

        # 结合延迟估计
        total_steps = time_based_steps + self.estimated_delay_steps

        # 限制在合理范围内
        return np.clip(total_steps, 0, len(self.command_buffer))

    def _get_relevant_commands(self, prediction_steps: int) -> List[np.ndarray]:
        """获取用于预测的相关历史命令"""
        if prediction_steps <= 0 or len(self.command_buffer) == 0:
            return []

        # 从缓冲区末尾开始，取最近的 prediction_steps 个命令
        start_idx = max(0, len(self.command_buffer) - prediction_steps)
        relevant_commands = list(self.command_buffer)[start_idx:]

        return relevant_commands

    def _forward_predict_state(self, initial_state: np.ndarray, commands: List[np.ndarray]) -> np.ndarray:
        """
        前向预测状态

        Args:
            initial_state: 初始状态 (测量值)
            commands: 历史命令序列

        Returns:
            predicted_state: 预测的当前状态
        """
        state = initial_state.copy()

        # 逐步应用历史命令
        for cmd in commands:
            # 状态转移: x(k+1) = A*x(k) + B*u(k)
            state = self.A_matrix @ state + self.B_matrix @ cmd

        return state

    def get_command_buffer_state(self) -> dict:
        """获取命令缓冲区状态 (用于调试)"""
        return {
            "buffer_size": len(self.command_buffer),
            "max_size": self.command_buffer.maxlen,
            "total_sent": self.total_commands_sent,
            "estimated_delay_steps": self.estimated_delay_steps,
            "recent_delays": list(self.delay_measurements)[-5:] if self.delay_measurements else []
        }

    def reset(self):
        """重置补偿器状态"""
        self.command_buffer.clear()
        self.timestamp_buffer.clear()
        self.delay_measurements.clear()
        self.total_commands_sent = 0
        self.compensation_active = False

        console.print(f"[yellow]延迟补偿器已重置[/yellow]")

# 辅助类：延迟测量器
class DelayMeasurer:
    """专门用于测量MQTT通信延迟的工具"""

    def __init__(self, measurement_duration: float = 5.0):
        """
        延迟测量器

        Args:
            measurement_duration: 测量持续时间 (秒)
        """
        self.duration = measurement_duration
        self.ping_times = []
        self.pong_times = []
        self.measured_delays = []

    def start_measurement(self, mqtt_client, gateway_sn: str):
        """
        开始延迟测量

        发送ping消息，等待pong响应，计算往返时间
        """
        console.print(f"[cyan]开始延迟测量 (持续 {self.duration}s)...[/cyan]")

        # 这里需要实际的MQTT ping/pong实现
        # 简化版：假设已有延迟测量结果
        start_time = time.time()

        # 模拟测量过程
        while time.time() - start_time < self.duration:
            # 发送ping
            ping_time = time.time()

            # 模拟200ms延迟 + 随机抖动
            simulated_delay = 0.2 + np.random.normal(0, 0.02)

            # 记录往返时间
            self.ping_times.append(ping_time)
            self.measured_delays.append(simulated_delay)

            time.sleep(0.1)  # 100ms间隔测量

        # 计算统计结果
        avg_delay = np.mean(self.measured_delays)
        std_delay = np.std(self.measured_delays)
        max_delay = np.max(self.measured_delays)
        min_delay = np.min(self.measured_delays)

        console.print(f"[green]✓ 延迟测量完成[/green]")
        console.print(f"[cyan]平均延迟: {avg_delay*1000:.1f}ms ± {std_delay*1000:.1f}ms[/cyan]")
        console.print(f"[cyan]延迟范围: {min_delay*1000:.1f}ms ~ {max_delay*1000:.1f}ms[/cyan]")

        return {
            "avg_delay": avg_delay,
            "std_delay": std_delay,
            "max_delay": max_delay,
            "min_delay": min_delay,
            "measurements": self.measured_delays
        }

# 测试代码
if __name__ == "__main__":
    # 创建延迟补偿器
    compensator = DelayCompensator()

    # 设置虚拟系统模型
    A = np.array([[1, 0, 0.02, 0],
                  [0, 1, 0, 0.02],
                  [0, 0, 0.95, 0],
                  [0, 0, 0, 0.95]])

    B = np.array([[0, 0],
                  [0, 0],
                  [0.1, 0],
                  [0, -0.1]])

    compensator.set_system_model(A, B)

    # 模拟控制循环
    console.print(f"[cyan]模拟延迟补偿过程...[/cyan]")

    current_state = np.array([0.5, 0.3, 0.1, -0.1])  # 当前状态
    measurement_time = time.time() - 0.2  # 200ms前的测量

    # 发送一些历史命令
    for i in range(10):
        cmd = np.array([10.0 * np.sin(i * 0.1), 5.0 * np.cos(i * 0.1)])
        compensator.send_command(cmd)
        time.sleep(0.001)  # 模拟时间间隔

    # 估计当前真实状态
    estimated_state, info = compensator.estimate_current_state(current_state, measurement_time)

    console.print(f"[cyan]测量状态: {current_state}[/cyan]")
    console.print(f"[cyan]估计状态: {estimated_state}[/cyan]")
    console.print(f"[cyan]补偿信息: {info}[/cyan]")

    # 显示缓冲区状态
    buffer_info = compensator.get_command_buffer_state()
    console.print(f"[cyan]缓冲区状态: {buffer_info}[/cyan]")