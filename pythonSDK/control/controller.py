"""
控制器模块
包含平面控制器和平面+Yaw控制器
"""
import math
from .pid import PIDController


class PlaneController:
    """平面位置控制器（X-Y平面，无Yaw控制）"""

    def __init__(self, kp, ki, kd, output_limit):
        self.x_pid = PIDController(kp, ki, kd, output_limit)  # X轴 → Pitch
        self.y_pid = PIDController(kp, ki, kd, output_limit)  # Y轴 → Roll

    def reset(self):
        """重置所有PID状态"""
        self.x_pid.reset()
        self.y_pid.reset()

    def compute(self, target_x, target_y, current_x, current_y, current_time):
        """计算控制输出，返回: (roll, pitch) 杆量偏移值"""
        error_x = target_x - current_x  # 前方向误差
        error_y = target_y - current_y  # 左方向误差
        pitch_offset = self.x_pid.compute(error_x, current_time)  # X → Pitch正
        roll_offset = -self.y_pid.compute(error_y, current_time)  # Y → Roll负
        return roll_offset, pitch_offset

    def get_distance(self, target_x, target_y, current_x, current_y):
        """计算当前位置到目标位置的距离"""
        dx = target_x - current_x
        dy = target_y - current_y
        return (dx**2 + dy**2) ** 0.5


class PlaneYawController:
    """平面+Yaw控制器（X-Y平面 + Yaw角度）"""

    def __init__(self, kp_xy, ki_xy, kd_xy, kp_yaw, ki_yaw, kd_yaw, output_limit):
        # XY平面控制器
        self.x_pid = PIDController(kp_xy, ki_xy, kd_xy, output_limit)
        self.y_pid = PIDController(kp_xy, ki_xy, kd_xy, output_limit)
        # Yaw角控制器
        self.yaw_pid = PIDController(kp_yaw, ki_yaw, kd_yaw, output_limit)

    def reset(self):
        """重置所有PID状态"""
        self.x_pid.reset()
        self.y_pid.reset()
        self.yaw_pid.reset()

    def compute(self, target_x, target_y, target_yaw,
                current_x, current_y, current_yaw, current_time):
        """
        计算控制输出

        返回: (roll, pitch, yaw) 杆量偏移值
        """
        # 计算XY平面误差
        error_x = target_x - current_x
        error_y = target_y - current_y

        # 计算Yaw角误差（处理-180~180度边界）
        error_yaw = self._normalize_angle(target_yaw - current_yaw)

        # 计算PID输出
        pitch_offset = self.x_pid.compute(error_x, current_time)    # X → Pitch
        roll_offset = -self.y_pid.compute(error_y, current_time)    # Y → Roll负
        yaw_offset = self.yaw_pid.compute(error_yaw, current_time)  # Yaw

        return roll_offset, pitch_offset, yaw_offset

    def get_distance(self, target_x, target_y, current_x, current_y):
        """计算XY平面距离"""
        dx = target_x - current_x
        dy = target_y - current_y
        return (dx**2 + dy**2) ** 0.5

    def get_yaw_error(self, target_yaw, current_yaw):
        """计算Yaw角误差（归一化到-180~180）"""
        return abs(self._normalize_angle(target_yaw - current_yaw))

    @staticmethod
    def _normalize_angle(angle):
        """归一化角度到-180~180度"""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle
