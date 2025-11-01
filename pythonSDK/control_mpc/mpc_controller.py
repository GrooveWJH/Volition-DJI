"""
MPC控制器核心 - 解决200ms延迟的预测控制

关键思想:
- 预测时域 N=10步 (对应200ms延迟的2倍，确保充分预测)
- 状态: [x, y, vx, vy] 位置+速度4维状态
- 控制: [pitch_cmd, roll_cmd] 杆量命令
- 约束: 杆量限幅防止过激反应
- 目标: 跟踪位置轨迹 + 控制平滑
"""

import numpy as np
from typing import Tuple, List, Optional
import time
from rich.console import Console

console = Console()

class MPCController:
    def __init__(self,
                 prediction_horizon: int = 10,
                 control_horizon: int = 5,
                 dt: float = 0.02,  # 50Hz控制频率
                 max_stick_output: float = 150.0):
        """
        MPC控制器初始化

        Args:
            prediction_horizon: 预测时域步数 (N=10, 对应200ms)
            control_horizon: 控制时域步数 (通常 <= prediction_horizon)
            dt: 控制周期 (秒)
            max_stick_output: 最大杆量输出
        """
        self.N = prediction_horizon  # 预测时域
        self.M = control_horizon     # 控制时域
        self.dt = dt
        self.max_stick = max_stick_output

        # 状态维度: [x, y, vx, vy]
        self.nx = 4  # 状态维度
        self.nu = 2  # 控制维度 [pitch_cmd, roll_cmd]

        # 权重矩阵 (调参核心)
        self.Q = np.diag([100.0, 100.0, 1.0, 1.0])  # 状态权重: 位置重要，速度次要
        self.R = np.diag([1.0, 1.0])                # 控制权重: 杆量平滑
        self.Qf = self.Q * 2                        # 终端权重: 最终位置最重要

        # 系统模型 (待辨识)
        self.A = None  # 状态转移矩阵
        self.B = None  # 控制矩阵
        self.model_ready = False

        # 延迟参数
        self.delay_steps = 10  # 200ms @ 50Hz = 10步延迟

        console.print(f"[green]✓ MPC控制器初始化完成[/green]")
        console.print(f"[dim]预测时域: {self.N}步 | 控制时域: {self.M}步 | 延迟: {self.delay_steps}步[/dim]")

    def set_model(self, A: np.ndarray, B: np.ndarray):
        """设置系统模型 (来自系统辨识)"""
        assert A.shape == (self.nx, self.nx), f"A矩阵维度错误: {A.shape}"
        assert B.shape == (self.nx, self.nu), f"B矩阵维度错误: {B.shape}"

        self.A = A.copy()
        self.B = B.copy()
        self.model_ready = True

        console.print(f"[green]✓ 系统模型已更新[/green]")
        console.print(f"[dim]A矩阵:\n{A}[/dim]")
        console.print(f"[dim]B矩阵:\n{B}[/dim]")

    def compute_control(self,
                       current_state: np.ndarray,
                       reference_trajectory: List[Tuple[float, float]],
                       delayed_commands: Optional[List[np.ndarray]] = None) -> Tuple[np.ndarray, dict]:
        """
        计算MPC控制量

        Args:
            current_state: 当前状态 [x, y, vx, vy]
            reference_trajectory: 参考轨迹 [(x_ref, y_ref), ...]
            delayed_commands: 延迟命令队列 (用于预测真实状态)

        Returns:
            control: 控制量 [pitch_cmd, roll_cmd]
            info: 调试信息
        """
        if not self.model_ready:
            # 模型未准备好，返回零控制
            return np.zeros(self.nu), {"status": "model_not_ready"}

        # 1. 补偿延迟：预测真实当前状态
        if delayed_commands is not None and len(delayed_commands) > 0:
            predicted_state = self._predict_real_state(current_state, delayed_commands)
        else:
            predicted_state = current_state.copy()

        # 2. 构建参考轨迹矩阵
        ref_matrix = self._build_reference_matrix(reference_trajectory)

        # 3. 求解二次规划问题
        try:
            optimal_controls = self._solve_qp(predicted_state, ref_matrix)

            # 4. 返回第一个控制量 (MPC的递推策略)
            u_optimal = optimal_controls[:self.nu]

            # 5. 限幅
            u_clamped = np.clip(u_optimal, -self.max_stick, self.max_stick)

            info = {
                "status": "success",
                "predicted_state": predicted_state,
                "optimal_sequence": optimal_controls,
                "cost": self._compute_cost(predicted_state, optimal_controls, ref_matrix)
            }

            return u_clamped, info

        except Exception as e:
            console.print(f"[red]MPC求解失败: {e}[/red]")
            return np.zeros(self.nu), {"status": "solver_failed", "error": str(e)}

    def _predict_real_state(self, measured_state: np.ndarray, delayed_commands: List[np.ndarray]) -> np.ndarray:
        """
        根据延迟命令队列预测真实当前状态

        核心思想：测量到的状态是过去的，需要用已发送的命令"前向预测"到现在
        """
        state = measured_state.copy()

        # 应用队列中的每个延迟命令
        for cmd in delayed_commands[-self.delay_steps:]:  # 只考虑延迟范围内的命令
            state = self.A @ state + self.B @ cmd

        return state

    def _build_reference_matrix(self, reference_trajectory: List[Tuple[float, float]]) -> np.ndarray:
        """构建预测时域内的参考轨迹矩阵"""
        ref_matrix = np.zeros((self.N, self.nx))

        for i in range(self.N):
            if i < len(reference_trajectory):
                x_ref, y_ref = reference_trajectory[i]
                ref_matrix[i] = [x_ref, y_ref, 0.0, 0.0]  # 期望速度为0 (悬停)
            else:
                # 超出轨迹长度时，保持最后一个点
                if len(reference_trajectory) > 0:
                    x_ref, y_ref = reference_trajectory[-1]
                    ref_matrix[i] = [x_ref, y_ref, 0.0, 0.0]

        return ref_matrix

    def _solve_qp(self, initial_state: np.ndarray, ref_matrix: np.ndarray) -> np.ndarray:
        """
        求解二次规划优化问题

        最小化: sum_{k=0}^{N-1} ||x_k - x_ref_k||_Q^2 + ||u_k||_R^2 + ||x_N - x_ref_N||_Qf^2
        约束:   x_{k+1} = A*x_k + B*u_k
               |u_k| <= max_stick
        """
        # 简化实现：使用解析解 (假设无约束)
        # 实际工程中可使用 cvxpy 或 casadi 求解器

        # 构建预测矩阵 (状态预测)
        Phi = np.zeros((self.N * self.nx, self.nx))  # 状态预测矩阵
        Gamma = np.zeros((self.N * self.nx, self.M * self.nu))  # 控制预测矩阵

        # 填充预测矩阵
        for i in range(self.N):
            # 状态预测: x_k = A^k * x_0
            Phi[i*self.nx:(i+1)*self.nx, :] = np.linalg.matrix_power(self.A, i+1)

            # 控制预测: x_k 受前 min(i+1, M) 个控制量影响
            for j in range(min(i+1, self.M)):
                if i-j >= 0:
                    Gamma[i*self.nx:(i+1)*self.nx, j*self.nu:(j+1)*self.nu] = \
                        np.linalg.matrix_power(self.A, i-j) @ self.B

        # 构建扩展权重矩阵
        Q_extended = np.kron(np.eye(self.N-1), self.Q)
        Q_extended = np.block([[Q_extended, np.zeros((Q_extended.shape[0], self.nx))],
                              [np.zeros((self.nx, Q_extended.shape[1])), self.Qf]])

        R_extended = np.kron(np.eye(self.M), self.R)

        # 参考轨迹向量化
        ref_vector = ref_matrix.flatten()

        # 二次型系数
        H = Gamma.T @ Q_extended @ Gamma + R_extended
        f = 2 * Gamma.T @ Q_extended @ (Phi @ initial_state - ref_vector)

        # 求解 (简化版：直接求逆，实际应用中需要更鲁棒的方法)
        try:
            u_optimal = -np.linalg.solve(H, f)
        except np.linalg.LinAlgError:
            # 矩阵奇异时的备用方案
            u_optimal = -np.linalg.pinv(H) @ f

        # 扩展到完整预测时域 (控制时域后保持最后一个值)
        if self.M < self.N:
            u_extended = np.zeros(self.N * self.nu)
            u_extended[:self.M * self.nu] = u_optimal
            # 后续步骤保持最后一个控制量
            for i in range(self.M, self.N):
                u_extended[i*self.nu:(i+1)*self.nu] = u_optimal[-self.nu:]
            return u_extended
        else:
            return u_optimal

    def _compute_cost(self, state: np.ndarray, controls: np.ndarray, ref_matrix: np.ndarray) -> float:
        """计算当前优化解的代价函数值 (用于调试)"""
        cost = 0.0
        x = state.copy()

        for i in range(self.N):
            # 状态代价
            x_ref = ref_matrix[i]
            state_error = x - x_ref

            if i == self.N - 1:  # 终端代价
                cost += state_error.T @ self.Qf @ state_error
            else:  # 运行代价
                cost += state_error.T @ self.Q @ state_error

            # 控制代价
            if i < self.M:
                u = controls[i*self.nu:(i+1)*self.nu]
                cost += u.T @ self.R @ u

                # 状态更新
                x = self.A @ x + self.B @ u

        return float(cost)

# 测试代码
if __name__ == "__main__":
    # 创建MPC控制器
    mpc = MPCController(prediction_horizon=10, control_horizon=5)

    # 设置虚拟模型 (仅用于测试)
    A = np.array([[1, 0, 0.02, 0],
                  [0, 1, 0, 0.02],
                  [0, 0, 0.95, 0],
                  [0, 0, 0, 0.95]])

    B = np.array([[0, 0],
                  [0, 0],
                  [0.1, 0],
                  [0, -0.1]])  # pitch影响vx, roll影响vy (负号表示坐标映射)

    mpc.set_model(A, B)

    # 测试控制计算
    current_state = np.array([0.5, 0.3, 0.1, -0.1])  # 当前位置和速度
    reference = [(0.0, 0.0), (0.0, 0.0)]  # 目标：回到原点

    control, info = mpc.compute_control(current_state, reference)

    console.print(f"[cyan]当前状态: {current_state}[/cyan]")
    console.print(f"[cyan]控制输出: {control}[/cyan]")
    console.print(f"[cyan]求解状态: {info['status']}[/cyan]")
    console.print(f"[cyan]优化代价: {info.get('cost', 'N/A')}[/cyan]")