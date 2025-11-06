#!/usr/bin/env python3

"""
多无人机实时监控系统 - 主入口

现已重构为 dashboard 模块，所有配置和功能都在 dashboard/ 目录下。

使用方式:
    python main.py                    # 使用真实无人机
    USE_MOCK_DRONE=1 python main.py   # 使用模拟器模式

配置文件:
    dashboard/config.py - 所有配置项（MQTT、无人机、频率等）

功能特性:
    - 实时 OSD 数据显示（100Hz）
    - 实时频率追踪（滑动窗口法）
    - 离线检测（2秒超时）
    - VRPN 动捕系统集成（可选）
    - 多机并行连接
    - 模拟器支持
"""

from dashboard import run

if __name__ == "__main__":
    run()
