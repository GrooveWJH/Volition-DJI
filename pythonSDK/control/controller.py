"""
控制器模块
包含平面控制器、平面+Yaw控制器和Yaw单独控制器
"""
import math
from .pid import PIDController


def quaternion_to_yaw(quat):
    """
    从四元数提取Yaw角（偏航角）

    Args:
        quat: 四元数格式 (qx, qy, qz, qw)

    Returns:
        Yaw角度（度），范围 [-180, 180]
    """
    qx, qy, qz, qw = quat
    yaw_rad = math.atan2(2.0 * (qw * qz + qx * qy),
                         1.0 - 2.0 * (qy * qy + qz * qz))
    return math.degrees(yaw_rad)


def normalize_angle(angle):
    """
    归一化角度到 [-180, 180] 范围

    Args:
        angle: 角度（度）

    Returns:
        归一化后的角度（度）
    """
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


def get_yaw_error(target_yaw, current_yaw):
    """
    计算Yaw角误差（考虑±180°边界）

    Args:
        target_yaw: 目标Yaw角（度）
        current_yaw: 当前Yaw角（度）

    Returns:
        误差（度），正值表示需要逆时针旋转
    """
    error = target_yaw - current_yaw
    return normalize_angle(error)


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


class YawOnlyController:
    """Yaw角单独控制器（仅控制偏航角）"""

    def __init__(self, kp, ki, kd, output_limit):
        """
        初始化Yaw控制器

        Args:
            kp: 比例增益
            ki: 积分增益
            kd: 微分增益
            output_limit: 输出限幅
        """
        self.yaw_pid = PIDController(kp, ki, kd, output_limit)

    def reset(self):
        """重置PID状态"""
        self.yaw_pid.reset()

    def compute(self, target_yaw, current_yaw, current_time):
        """
        计算Yaw控制输出

        Args:
            target_yaw: 目标Yaw角（度）
            current_yaw: 当前Yaw角（度）
            current_time: 当前时间

        Returns:
            yaw_offset: Yaw杆量偏移值
        """
        # 计算Yaw角误差（考虑±180°边界）
        error_yaw = get_yaw_error(target_yaw, current_yaw)

        # PID控制
        # 注意：误差为正（需要逆时针旋转）→ 输出正值 → 杆量<1024（向左）
        yaw_offset = -self.yaw_pid.compute(error_yaw, current_time)

        return yaw_offset

    def get_yaw_error(self, target_yaw, current_yaw):
        """
        计算Yaw角误差的绝对值

        Args:
            target_yaw: 目标Yaw角（度）
            current_yaw: 当前Yaw角（度）

        Returns:
            误差绝对值（度）
        """
        return abs(get_yaw_error(target_yaw, current_yaw))
