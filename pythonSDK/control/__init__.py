"""
PID控制系统模块

模块化结构：
- config.py: 配置参数（包括Yaw专用配置）
- pid.py: PID控制器
- logger.py: 参数化数据记录器
- controller.py: 平面控制器、平面+Yaw控制器、Yaw单独控制器
- main.py: 平面+Yaw控制主程序入口
- yaw_main.py: Yaw单独控制主程序入口
- visualize.py: 通用数据可视化工具
"""

from .pid import PIDController
from .controller import (
    PlaneController, PlaneYawController, YawOnlyController,
    quaternion_to_yaw, normalize_angle, get_yaw_error
)
from .logger import DataLogger
from .config import *

__all__ = [
    'PIDController',
    'PlaneController',
    'PlaneYawController',
    'YawOnlyController',
    'DataLogger',
    'quaternion_to_yaw',
    'normalize_angle',
    'get_yaw_error',
]
