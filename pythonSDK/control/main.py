#!/usr/bin/env python3
"""
PID平面定位控制器 - 多航点循环模式（模块化版本）

功能：
- 使用VRPN位置数据作为反馈
- 通过PID算法控制无人机飞到目标点
- 支持XY平面+Yaw角控制
- 模块化设计，支持从任意目录运行

坐标映射：
- X轴（前方向，x变大）→ Pitch杆量（正值）
- Y轴（左方向，y变大）→ Roll杆量（负值）
- Yaw角（逆时针为正）→ Yaw杆量（正值）

使用方法：
1. 手动让无人机起飞到1m高度
2. 从任意目录运行: python control/main.py 或 python main.py
3. 无人机按顺序飞到各个航点
4. 按 Ctrl+C 退出程序

注意：此文件代码已暂时清空，待后续重构
"""

import sys
import os

# 添加pythonSDK到路径（支持从任意目录运行）
script_dir = os.path.dirname(os.path.abspath(__file__))
sdk_dir = os.path.dirname(script_dir)  # pythonSDK目录
if sdk_dir not in sys.path:
    sys.path.insert(0, sdk_dir)


def main():
    """平面+Yaw复合控制主程序（暂时清空）"""
    print("此功能暂时禁用，待重构")
    return 1


if __name__ == '__main__':
    exit(main())
