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
    """平面位置控制器（X-Y平面，无Yaw控制）

    特性：
    - 距离自适应增益调度（远处激进，近处温和）
    - Smith预测器延迟补偿（处理网络延迟）
    """

    def __init__(self, kp, ki, kd, output_limit,
                 enable_gain_scheduling=True,
                 enable_smith_predictor=True,
                 estimated_delay=0.5,
                 gain_schedule_profile=None):
        """
        初始化平面控制器

        Args:
            kp, ki, kd: PID增益
            output_limit: 输出限幅
            enable_gain_scheduling: 是否启用增益调度
            enable_smith_predictor: 是否启用Smith预测器
            estimated_delay: 估计延迟时间（秒）
            gain_schedule_profile: {'far': {'kp_scale', 'kd_scale'}, 'near': {...}}
        """
        # 保存基础PID增益
        self.kp_base = kp
        self.ki_base = ki
        self.kd_base = kd
        self.output_limit = output_limit

        # 创建PID控制器
        self.x_pid = PIDController(kp, ki, kd, output_limit)  # X轴 → Pitch
        self.y_pid = PIDController(kp, ki, kd, output_limit)  # Y轴 → Roll

        # 增益调度配置
        self.enable_gain_scheduling = enable_gain_scheduling
        self.distance_far = 1.0      # 远距离阈值（米）
        self.distance_near = 0.3     # 近距离阈值（米）
        default_profile = {
            'far': {'kp_scale': 1.0, 'kd_scale': 0.5},
            'near': {'kp_scale': 0.4, 'kd_scale': 1.5},
        }
        self.gain_schedule_profile = gain_schedule_profile or default_profile

        # Smith预测器配置
        self.enable_smith_predictor = enable_smith_predictor
        self.estimated_delay = estimated_delay
        self.delay_buffer_x = []     # (时间戳, 指令值)
        self.delay_buffer_y = []
        self.response_gain = 0.0015  # 杆量到速度的响应增益（m/s per stick unit）

    def reset(self):
        """重置所有PID状态和延迟缓冲区"""
        self.x_pid.reset()
        self.y_pid.reset()
        self.delay_buffer_x.clear()
        self.delay_buffer_y.clear()

    def compute(self, target_x, target_y, current_x, current_y, current_time):
        """
        计算控制输出

        返回:
            roll_offset, pitch_offset: 杆量偏移值
            pid_components: {
                'x': (p, i, d),
                'y': (p, i, d)
            }
        """
        error_x = target_x - current_x  # 前方向误差
        error_y = target_y - current_y  # 左方向误差
        distance = math.sqrt(error_x**2 + error_y**2)

        # 【增益调度】根据距离调整PID增益
        if self.enable_gain_scheduling:
            self._apply_gain_scheduling(distance)

        # PID计算
        pitch_offset, x_components = self.x_pid.compute(error_x, current_time)  # X → Pitch正
        y_output, y_components = self.y_pid.compute(error_y, current_time)

        # 【Smith预测器】延迟补偿
        if self.enable_smith_predictor:
            pitch_offset = self._apply_smith_predictor(
                pitch_offset, self.delay_buffer_x, current_time, 'x'
            )
            y_output = self._apply_smith_predictor(
                y_output, self.delay_buffer_y, current_time, 'y'
            )

        # 输出限幅
        pitch_offset = max(-self.output_limit, min(self.output_limit, pitch_offset))
        y_output = max(-self.output_limit, min(self.output_limit, y_output))

        roll_offset = -y_output  # Y → Roll负

        # 组装PID分量字典
        pid_components = {
            'x': x_components,
            'y': y_components
        }

        return roll_offset, pitch_offset, pid_components

    def _apply_gain_scheduling(self, distance):
        """
        根据距离调整PID增益

        策略：
        - 远距离(>distance_far): 使用profile['far']给定的增益缩放
        - 中距离: 在远/近两组增益之间按距离线性插值
        - 近距离(<distance_near): 使用profile['near']给定的增益缩放
        """
        profile_far = self.gain_schedule_profile.get('far', {})
        profile_near = self.gain_schedule_profile.get('near', {})
        kp_far = profile_far.get('kp_scale', 1.0)
        kd_far = profile_far.get('kd_scale', 0.5)
        kp_near = profile_near.get('kp_scale', 0.4)
        kd_near = profile_near.get('kd_scale', 1.5)

        if distance > self.distance_far:
            kp_scale = kp_far
            kd_scale = kd_far
        elif distance > self.distance_near and self.distance_far > self.distance_near:
            # 线性插值
            ratio = (distance - self.distance_near) / (self.distance_far - self.distance_near)
            kp_scale = kp_near + (kp_far - kp_near) * ratio
            kd_scale = kd_near + (kd_far - kd_near) * ratio
        else:
            kp_scale = kp_near
            kd_scale = kd_near

        # 应用缩放
        self.x_pid.kp = self.kp_base * kp_scale
        self.x_pid.kd = self.kd_base * kd_scale
        self.y_pid.kp = self.kp_base * kp_scale
        self.y_pid.kd = self.kd_base * kd_scale

    def _apply_smith_predictor(self, command, buffer, current_time, axis):
        """
        Smith预测器延迟补偿

        原理：
        1. 存储当前指令到缓冲区
        2. 取出延迟时间前的历史指令
        3. 用简单模型预测该指令造成的当前速度
        4. 从当前指令中减去预测速度（抵消延迟效应）
        """
        # 存储当前指令
        buffer.append((current_time, command))

        # 清理1秒前的旧数据
        while buffer and buffer[0][0] < current_time - 1.0:
            buffer.pop(0)

        # 获取延迟时间前的历史指令
        delayed_time = current_time - self.estimated_delay
        delayed_command = self._get_delayed_command(buffer, delayed_time)

        # 预测该延迟指令造成的当前速度
        predicted_velocity = delayed_command * self.response_gain

        # 补偿：从当前指令减去预测速度的影响
        # 补偿增益根据经验调整
        compensation = predicted_velocity * 150
        compensated_command = command - compensation

        return compensated_command

    def _get_delayed_command(self, buffer, target_time):
        """从缓冲区获取指定时间的指令（线性插值）"""
        if not buffer:
            return 0.0

        # 找到目标时间前后的两个点
        for i, (t, cmd) in enumerate(buffer):
            if t >= target_time:
                if i == 0:
                    return cmd
                # 线性插值
                t1, cmd1 = buffer[i-1]
                t2, cmd2 = buffer[i]
                ratio = (target_time - t1) / (t2 - t1) if t2 > t1 else 0
                return cmd1 + (cmd2 - cmd1) * ratio

        # 如果目标时间在所有记录之后，返回最后一个
        return buffer[-1][1]

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

        返回:
            roll_offset, pitch_offset, yaw_offset: 杆量偏移值
            pid_components: {
                'x': (p, i, d),
                'y': (p, i, d),
                'yaw': (p, i, d)
            }
        """
        # 计算XY平面误差
        error_x = target_x - current_x
        error_y = target_y - current_y

        # 计算Yaw角误差（处理-180~180度边界）
        error_yaw = self._normalize_angle(target_yaw - current_yaw)

        # 计算PID输出（获取分量）
        pitch_offset, x_components = self.x_pid.compute(error_x, current_time)    # X → Pitch
        y_output, y_components = self.y_pid.compute(error_y, current_time)
        roll_offset = -y_output    # Y → Roll负
        yaw_offset, yaw_components = self.yaw_pid.compute(error_yaw, current_time)  # Yaw

        # 组装PID分量字典
        pid_components = {
            'x': x_components,
            'y': y_components,
            'yaw': yaw_components
        }

        return roll_offset, pitch_offset, yaw_offset, pid_components

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

    def __init__(self, kp, ki, kd, output_limit, i_activation_error=None):
        """
        初始化Yaw控制器

        Args:
            kp: 比例增益
            ki: 积分增益
            kd: 微分增益
            output_limit: 输出限幅
            i_activation_error: I项启动误差阈值（度），误差在此范围内才启动积分
        """
        self.yaw_pid = PIDController(kp, ki, kd, output_limit, i_activation_error)

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
            pid_components: (p_term, i_term, d_term) PID三个分量
        """
        # 计算Yaw角误差（考虑±180°边界）
        error_yaw = get_yaw_error(target_yaw, current_yaw)

        # PID控制（获取分量）
        # 注意：误差为正（需要逆时针旋转）→ 输出正值 → 杆量<1024（向左）
        output, pid_components = self.yaw_pid.compute(error_yaw, current_time)
        yaw_offset = -output

        return yaw_offset, pid_components

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
