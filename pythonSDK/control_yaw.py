#!/usr/bin/env python3
"""
Yaw角PID控制器 - 单独调试版本

功能：
- 使用VRPN姿态数据作为反馈
- 通过PID算法控制无人机旋转到目标Yaw角
- 只控制Yaw角，不控制位置和高度
- 支持多个目标角度循环测试

Yaw角规则：
- 逆时针旋转 → Yaw角增大（正值）
- 顺时针旋转 → Yaw角减小（负值）
- 杆量控制：左摇杆向左（<1024）→ 逆时针旋转
- 杆量控制：左摇杆向右（>1024）→ 顺时针旋转

使用方法：
1. 手动让无人机起飞到1m高度
2. 启动本程序
3. 无人机按顺序旋转到各个目标角度
4. 每到达一个角度，等待按 Enter 键
5. 自动前往下一个目标角度，循环往复
6. 按 Ctrl+C 退出程序
"""

import time
import csv
import os
import math
from datetime import datetime
from djisdk import MQTTClient, start_heartbeat, stop_heartbeat, send_stick_control
from vrpn import VRPNClient
from rich.console import Console
from rich.panel import Panel

# ========== 配置参数 ==========

# 无人机配置
GATEWAY_SN = '9N9CN2J0012CXY'
VRPN_DEVICE = 'Drone001@192.168.31.100'

# MQTT配置
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# 目标角度（单位：度）
# 无人机将按顺序旋转到这些角度
TARGET_YAWS = [
    0,      # 正北（初始朝向）
    90,     # 正东（逆时针90°）
    180,    # 正南（逆时针180°）
    -90,    # 正西（顺时针90°，等价于逆时针270°）
]

# PID参数（Yaw角专用）
# 针对严重过冲和振荡问题优化：降低Kp，禁用Ki，大幅增加Kd
KP_YAW = 3.0   # 比例增益（从10降到3，减少70%过冲）
KI_YAW = 0.0   # 积分增益（禁用！振荡时会累积误差加剧问题）
KD_YAW = 50.0  # 微分增益（从10增加到50，强力阻尼）

# 控制参数
CONTROL_FREQUENCY = 60     # 控制频率（Hz）
TOLERANCE_YAW = 1.0        # 到达阈值（度）
ARRIVAL_STABLE_TIME = 2.0  # 到达稳定时间（秒）
MAX_YAW_STICK_OUTPUT = 500 # 最大Yaw杆量输出限幅（满杆量，1024±660）
ENABLE_DATA_LOGGING = True # 是否启用数据记录

# 杆量常量
NEUTRAL = 1024


# ========== 辅助函数 ==========

def quaternion_to_yaw(quat):
    """
    从四元数提取Yaw角（偏航角）

    四元数格式: (qx, qy, qz, qw)
    返回: Yaw角度（度），范围 [-180, 180]
    """
    qx, qy, qz, qw = quat

    # 从四元数计算Yaw角（绕Z轴旋转）
    yaw_rad = math.atan2(2.0 * (qw * qz + qx * qy),
                         1.0 - 2.0 * (qy * qy + qz * qz))
    yaw_deg = math.degrees(yaw_rad)
    return yaw_deg


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


# ========== 数据记录器 ==========

class YawDataLogger:
    """Yaw角PID控制数据记录器"""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.csv_file = None
        self.csv_writer = None
        self.log_dir = None

        if self.enabled:
            self._setup_logging()

    def _setup_logging(self):
        """创建数据目录和CSV文件"""
        # 创建data/yaw目录（如果不存在）
        base_dir = os.path.join(os.path.dirname(__file__), 'data/yaw')
        os.makedirs(base_dir, exist_ok=True)

        # 创建时间戳目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_dir = os.path.join(base_dir, timestamp)
        os.makedirs(self.log_dir, exist_ok=True)

        # 创建CSV文件
        csv_path = os.path.join(self.log_dir, 'yaw_control_data.csv')
        self.csv_file = open(csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # 写入CSV头部
        self.csv_writer.writerow([
            'timestamp',       # 时间戳
            'target_yaw',      # 目标yaw角度（度）
            'current_yaw',     # 当前yaw角度（度）
            'error_yaw',       # yaw角误差（度）
            'yaw_offset',      # Yaw杆量偏移
            'yaw_absolute',    # Yaw绝对杆量
            'target_index'     # 当前目标索引
        ])
        self.csv_file.flush()

    def log(self, timestamp, target_yaw, current_yaw, error_yaw,
            yaw_offset, yaw_absolute, target_index):
        """记录一条数据"""
        if not self.enabled or self.csv_writer is None:
            return

        self.csv_writer.writerow([
            timestamp, target_yaw, current_yaw, error_yaw,
            yaw_offset, yaw_absolute, target_index
        ])

        # 每10条刷新一次
        if int(timestamp * CONTROL_FREQUENCY) % 10 == 0:
            self.csv_file.flush()

    def close(self):
        """关闭日志文件"""
        if self.csv_file:
            self.csv_file.close()
            console = Console()
            console.print(f"[green]✓ 数据已保存至: {self.log_dir}[/green]")

    def get_log_dir(self):
        """获取日志目录路径"""
        return self.log_dir


# ========== PID控制器 ==========

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


# ========== Yaw控制器 ==========

class YawController:
    """Yaw角控制器"""

    def __init__(self, kp, ki, kd, output_limit):
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


# ========== 主程序 ==========

def main():
    console = Console()
    targets_str = "\n".join([f"    目标{i}: {yaw}°" for i, yaw in enumerate(TARGET_YAWS)])
    console.print(Panel.fit(
        "[bold cyan]Yaw角PID控制器 - 单独调试版本[/bold cyan]\n"
        f"[dim]目标数量: {len(TARGET_YAWS)}[/dim]\n"
        f"[dim]{targets_str}[/dim]\n"
        f"[dim]到达阈值: ±{TOLERANCE_YAW:.1f}°[/dim]\n"
        f"[dim]PID参数: Kp={KP_YAW}, Ki={KI_YAW}, Kd={KD_YAW}[/dim]",
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
    controller = YawController(KP_YAW, KI_YAW, KD_YAW, MAX_YAW_STICK_OUTPUT)
    target_index = 0
    target_yaw = TARGET_YAWS[target_index]

    # 5. 初始化数据记录器
    logger = YawDataLogger(enabled=ENABLE_DATA_LOGGING)
    if logger.enabled:
        console.print(f"[green]✓ 数据记录已启用: {logger.get_log_dir()}[/green]")

    console.print("\n[bold green]✓ 初始化完成！开始控制...[/bold green]")
    console.print(f"[cyan]首个目标: 目标{target_index} - {target_yaw}°[/cyan]")
    console.print("[yellow]提示: 按Ctrl+C可随时退出[/yellow]\n")

    # 控制循环
    control_interval = 1.0 / CONTROL_FREQUENCY
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
                if abs_error < TOLERANCE_YAW:
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
            logger.log(
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