"""
PID控制器基础类
"""


class PIDController:
    """单轴PID控制器"""

    def __init__(self, kp, ki, kd, output_limit=None):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit

        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None

    def reset(self):
        """重置PID状态"""
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None

    def compute(self, error, current_time):
        """计算PID输出"""
        dt = 0.0 if self.last_time is None else current_time - self.last_time

        # P项
        p_term = self.kp * error

        # I项（带积分限幅）
        if dt > 0:
            self.integral += error * dt
            if self.output_limit and self.ki > 0:
                max_integral = self.output_limit / self.ki
                self.integral = max(-max_integral, min(max_integral, self.integral))
        i_term = self.ki * self.integral

        # D项
        d_term = self.kd * ((error - self.last_error) / dt if dt > 0 else 0.0)

        # 总输出（带限幅）
        output = p_term + i_term + d_term
        if self.output_limit:
            output = max(-self.output_limit, min(self.output_limit, output))

        # 更新状态
        self.last_error = error
        self.last_time = current_time
        return output
