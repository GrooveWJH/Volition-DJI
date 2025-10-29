"""
数据记录器模块
"""
import csv
import os
from datetime import datetime
from rich.console import Console


class DataLogger:
    """PID控制数据记录器"""

    def __init__(self, enabled=True, base_dir=None):
        self.enabled = enabled
        self.csv_file = None
        self.csv_writer = None
        self.log_dir = None

        if self.enabled:
            self._setup_logging(base_dir)

    def _setup_logging(self, base_dir=None):
        """创建数据目录和CSV文件"""
        # 确定基础目录
        if base_dir is None:
            # 获取pythonSDK目录（不管从哪里运行都能找到）
            import sys
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            # 如果从control目录运行，回到上一级
            if os.path.basename(script_dir) == 'control':
                script_dir = os.path.dirname(script_dir)
            base_dir = os.path.join(script_dir, 'data')

        os.makedirs(base_dir, exist_ok=True)

        # 创建时间戳目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_dir = os.path.join(base_dir, timestamp)
        os.makedirs(self.log_dir, exist_ok=True)

        # 创建CSV文件
        csv_path = os.path.join(self.log_dir, 'control_data.csv')
        self.csv_file = open(csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # 写入CSV头部
        self.csv_writer.writerow([
            'timestamp',      # 时间戳
            'target_x',       # 目标x位置
            'target_y',       # 目标y位置
            'target_yaw',     # 目标yaw角度
            'current_x',      # 当前x位置
            'current_y',      # 当前y位置
            'current_yaw',    # 当前yaw角度
            'error_x',        # x轴误差
            'error_y',        # y轴误差
            'error_yaw',      # yaw角误差
            'distance',       # 距离目标的距离
            'roll_offset',    # Roll杆量偏移
            'pitch_offset',   # Pitch杆量偏移
            'yaw_offset',     # Yaw杆量偏移
            'roll_absolute',  # Roll绝对杆量
            'pitch_absolute', # Pitch绝对杆量
            'yaw_absolute',   # Yaw绝对杆量
            'waypoint_index'  # 当前航点索引
        ])
        self.csv_file.flush()

    def log(self, timestamp, target_x, target_y, target_yaw,
            current_x, current_y, current_yaw,
            error_x, error_y, error_yaw, distance,
            roll_offset, pitch_offset, yaw_offset,
            roll_absolute, pitch_absolute, yaw_absolute, waypoint_index):
        """记录一条数据"""
        if not self.enabled or self.csv_writer is None:
            return

        self.csv_writer.writerow([
            timestamp, target_x, target_y, target_yaw,
            current_x, current_y, current_yaw,
            error_x, error_y, error_yaw, distance,
            roll_offset, pitch_offset, yaw_offset,
            roll_absolute, pitch_absolute, yaw_absolute, waypoint_index
        ])

        # 每10条刷新一次
        if int(timestamp * 50) % 10 == 0:  # 假设50Hz
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
