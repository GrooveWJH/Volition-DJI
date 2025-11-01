"""
系统辨识模块 - 自动学习无人机动态特性

核心思想：
1. 发送随机激励信号 (white noise / chirp)
2. 记录输入-输出数据对 (杆量命令 → 位置响应)
3. 最小二乘法拟合线性模型: x(k+1) = A*x(k) + B*u(k-delay)
4. 验证模型精度 (R² > 0.8 视为可用)

输出：A, B 矩阵供MPC使用
"""

import numpy as np
import time
from typing import Tuple, List, Dict, Optional
from collections import deque
from rich.console import Console
import json

console = Console()

class SystemIdentification:
    def __init__(self,
                 dt: float = 0.02,  # 50Hz
                 state_dim: int = 4,  # [x, y, vx, vy]
                 control_dim: int = 2,  # [pitch, roll]
                 window_size: int = 500):  # 数据窗口大小
        """
        系统辨识初始化

        Args:
            dt: 采样周期
            state_dim: 状态维度
            control_dim: 控制维度
            window_size: 滑动窗口大小
        """
        self.dt = dt
        self.nx = state_dim
        self.nu = control_dim
        self.window_size = window_size

        # 数据存储
        self.states_history = deque(maxlen=window_size)      # 状态历史
        self.controls_history = deque(maxlen=window_size)    # 控制历史
        self.timestamps = deque(maxlen=window_size)          # 时间戳

        # 辨识结果
        self.A_matrix = None
        self.B_matrix = None
        self.model_quality = 0.0  # R² 分数
        self.is_identified = False

        # 激励信号参数
        self.excitation_amplitude = 50.0  # 激励信号幅值
        self.excitation_duration = 10.0   # 激励持续时间 (秒)

        console.print(f"[green]✓ 系统辨识器初始化完成[/green]")
        console.print(f"[dim]状态维度: {self.nx} | 控制维度: {self.nu} | 窗口大小: {self.window_size}[/dim]")

    def add_data_point(self, state: np.ndarray, control: np.ndarray, timestamp: float):
        """添加数据点到历史记录"""
        assert len(state) == self.nx, f"状态维度不匹配: {len(state)} != {self.nx}"
        assert len(control) == self.nu, f"控制维度不匹配: {len(control)} != {self.nu}"

        self.states_history.append(state.copy())
        self.controls_history.append(control.copy())
        self.timestamps.append(timestamp)

    def generate_excitation_signal(self, t: float, signal_type: str = "prbs") -> np.ndarray:
        """
        生成激励信号用于系统辨识

        Args:
            t: 当前时间
            signal_type: 信号类型 ("prbs", "chirp", "random")

        Returns:
            激励控制信号 [pitch_cmd, roll_cmd]
        """
        if signal_type == "prbs":
            # 伪随机二进制序列 (PRBS)
            freq = 2.0  # Hz
            phase_x = np.sin(2 * np.pi * freq * t)
            phase_y = np.sin(2 * np.pi * freq * t + np.pi/3)  # 相位差

            pitch_cmd = self.excitation_amplitude * np.sign(phase_x)
            roll_cmd = self.excitation_amplitude * np.sign(phase_y)

        elif signal_type == "chirp":
            # 扫频信号 (Chirp)
            f0, f1 = 0.1, 5.0  # 频率范围
            freq = f0 + (f1 - f0) * (t % self.excitation_duration) / self.excitation_duration

            pitch_cmd = self.excitation_amplitude * np.sin(2 * np.pi * freq * t)
            roll_cmd = self.excitation_amplitude * np.sin(2 * np.pi * freq * t + np.pi/2)

        elif signal_type == "random":
            # 白噪声
            np.random.seed(int(t * 1000) % 1000)  # 基于时间的伪随机种子
            pitch_cmd = self.excitation_amplitude * (np.random.random() - 0.5) * 2
            roll_cmd = self.excitation_amplitude * (np.random.random() - 0.5) * 2

        else:
            # 默认：正弦波组合
            pitch_cmd = self.excitation_amplitude * np.sin(2 * np.pi * 1.0 * t)
            roll_cmd = self.excitation_amplitude * np.sin(2 * np.pi * 1.5 * t)

        return np.array([pitch_cmd, roll_cmd])

    def identify_model(self, delay_steps: int = 10) -> Tuple[bool, Dict]:
        """
        执行系统辨识

        Args:
            delay_steps: 预期延迟步数

        Returns:
            success: 是否成功
            info: 辨识信息
        """
        if len(self.states_history) < 100:
            return False, {"error": "数据不足", "data_points": len(self.states_history)}

        console.print(f"[cyan]开始系统辨识...[/cyan]")
        console.print(f"[dim]数据点数: {len(self.states_history)} | 预期延迟: {delay_steps}步[/dim]")

        try:
            # 1. 准备数据矩阵
            X, Y = self._prepare_data_matrices(delay_steps)

            if X.shape[0] < 50:  # 至少需要50个有效样本
                return False, {"error": "有效样本不足", "samples": X.shape[0]}

            # 2. 最小二乘求解
            theta = np.linalg.lstsq(X, Y, rcond=None)[0]

            # 3. 提取 A 和 B 矩阵
            self.A_matrix = theta[:self.nx, :].T
            self.B_matrix = theta[self.nx:, :].T

            # 4. 验证模型质量
            self.model_quality = self._validate_model(X, Y, theta)

            # 5. 判断是否可用
            if self.model_quality > 0.6:  # R² > 0.6 认为可用
                self.is_identified = True
                console.print(f"[green]✓ 系统辨识成功！模型质量: R² = {self.model_quality:.3f}[/green]")
                return True, {
                    "A_matrix": self.A_matrix,
                    "B_matrix": self.B_matrix,
                    "model_quality": self.model_quality,
                    "samples_used": X.shape[0]
                }
            else:
                console.print(f"[yellow]⚠ 模型质量不佳: R² = {self.model_quality:.3f} < 0.6[/yellow]")
                return False, {
                    "error": "模型质量不达标",
                    "model_quality": self.model_quality,
                    "threshold": 0.6
                }

        except Exception as e:
            console.print(f"[red]✗ 系统辨识失败: {e}[/red]")
            return False, {"error": str(e)}

    def _prepare_data_matrices(self, delay_steps: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        准备最小二乘法的数据矩阵

        模型形式: x(k+1) = A*x(k) + B*u(k-delay)
        回归形式: Y = X*theta, 其中 theta = [A; B]
        """
        # 转换为numpy数组
        states = np.array(list(self.states_history))
        controls = np.array(list(self.controls_history))

        # 计算有效数据范围 (考虑延迟)
        n_samples = len(states) - delay_steps - 1

        if n_samples <= 0:
            raise ValueError(f"数据不足以处理 {delay_steps} 步延迟")

        # 构建回归矩阵
        X = np.zeros((n_samples, self.nx + self.nu))  # [x(k), u(k-delay)]
        Y = np.zeros((n_samples, self.nx))            # x(k+1)

        for i in range(n_samples):
            # 当前状态: x(k)
            X[i, :self.nx] = states[i + delay_steps]

            # 延迟控制: u(k-delay)
            X[i, self.nx:] = controls[i]

            # 下一状态: x(k+1)
            Y[i] = states[i + delay_steps + 1]

        return X, Y

    def _validate_model(self, X: np.ndarray, Y: np.ndarray, theta: np.ndarray) -> float:
        """
        验证模型质量 (计算R²决定系数)

        R² = 1 - SS_res / SS_tot
        """
        # 预测值
        Y_pred = X @ theta

        # 残差平方和
        ss_res = np.sum((Y - Y_pred) ** 2)

        # 总平方和
        y_mean = np.mean(Y, axis=0)
        ss_tot = np.sum((Y - y_mean) ** 2)

        # R² 决定系数
        if ss_tot < 1e-10:  # 避免除零
            return 0.0

        r_squared = 1 - ss_res / ss_tot
        return float(r_squared)

    def save_model(self, filepath: str):
        """保存辨识得到的模型"""
        if not self.is_identified:
            console.print(f"[yellow]⚠ 模型未辨识，无法保存[/yellow]")
            return

        model_data = {
            "A_matrix": self.A_matrix.tolist(),
            "B_matrix": self.B_matrix.tolist(),
            "model_quality": self.model_quality,
            "timestamp": time.time(),
            "parameters": {
                "dt": self.dt,
                "state_dim": self.nx,
                "control_dim": self.nu
            }
        }

        with open(filepath, 'w') as f:
            json.dump(model_data, f, indent=2)

        console.print(f"[green]✓ 模型已保存到: {filepath}[/green]")

    def load_model(self, filepath: str) -> bool:
        """加载已保存的模型"""
        try:
            with open(filepath, 'r') as f:
                model_data = json.load(f)

            self.A_matrix = np.array(model_data["A_matrix"])
            self.B_matrix = np.array(model_data["B_matrix"])
            self.model_quality = model_data["model_quality"]
            self.is_identified = True

            console.print(f"[green]✓ 模型已加载: {filepath}[/green]")
            console.print(f"[dim]模型质量: R² = {self.model_quality:.3f}[/dim]")
            return True

        except Exception as e:
            console.print(f"[red]✗ 模型加载失败: {e}[/red]")
            return False

    def get_current_model(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """获取当前辨识的模型"""
        if self.is_identified:
            return self.A_matrix.copy(), self.B_matrix.copy()
        else:
            return None, None

    def reset(self):
        """重置辨识器状态"""
        self.states_history.clear()
        self.controls_history.clear()
        self.timestamps.clear()
        self.A_matrix = None
        self.B_matrix = None
        self.model_quality = 0.0
        self.is_identified = False

        console.print(f"[yellow]系统辨识器已重置[/yellow]")

# 测试代码
if __name__ == "__main__":
    # 创建辨识器
    sysid = SystemIdentification()

    # 模拟数据收集过程
    console.print(f"[cyan]模拟数据收集...[/cyan]")

    # 真实系统 (用于生成测试数据)
    A_true = np.array([[1, 0, 0.02, 0],
                       [0, 1, 0, 0.02],
                       [0, 0, 0.9, 0],
                       [0, 0, 0, 0.9]])

    B_true = np.array([[0, 0],
                       [0, 0],
                       [0.05, 0],
                       [0, -0.05]])

    # 仿真数据生成
    x = np.array([0.0, 0.0, 0.0, 0.0])  # 初始状态
    delay_buffer = deque(maxlen=10)

    for i in range(600):  # 12秒的数据
        t = i * 0.02

        # 生成激励信号
        u_excite = sysid.generate_excitation_signal(t, "prbs")

        # 添加到延迟缓冲
        delay_buffer.append(u_excite)

        # 应用延迟的控制
        if len(delay_buffer) >= 10:
            u_delayed = delay_buffer[0]  # 10步前的控制
        else:
            u_delayed = np.zeros(2)

        # 系统响应 (含噪声)
        noise = np.random.normal(0, 0.001, 4)
        x_next = A_true @ x + B_true @ u_delayed + noise

        # 记录数据
        sysid.add_data_point(x, u_excite, t)

        # 更新状态
        x = x_next

    # 执行辨识
    success, info = sysid.identify_model(delay_steps=10)

    if success:
        A_id, B_id = sysid.get_current_model()
        console.print(f"[green]辨识成功！[/green]")
        console.print(f"[cyan]真实A矩阵:\n{A_true}[/cyan]")
        console.print(f"[cyan]辨识A矩阵:\n{A_id}[/cyan]")
        console.print(f"[cyan]A矩阵误差: {np.linalg.norm(A_true - A_id):.6f}[/cyan]")
    else:
        console.print(f"[red]辨识失败: {info}[/red]")