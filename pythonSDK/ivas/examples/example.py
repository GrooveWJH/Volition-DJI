#!/usr/bin/env python3
"""
IVAS SDK 使用示例

演示如何使用 ivas 包与 IVAS 服务器进行交互。
"""

import sys
import time
import threading

# 如果未通过 pip 安装，需要添加父目录到路径
# import os
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ivas import IVASClient


def single_device_example():
    """单设备示例"""

    print("=" * 60)
    print("IVAS SDK 使用示例 - 单设备")
    print("=" * 60)

    # 配置参数
    config = {
        'device_code': 1,
        'account': 'ZSDX001',
        'password': 'your_password',  # 请替换为实际密码
        'base_lat': 23.0,  # 基准纬度
        'base_lon': 113.0,  # 基准经度
        'base_alt': 100.0,  # 基准海拔
        'coord_range': {
            'lat_offset': 0.001,  # 纬度随机偏移
            'lon_offset': 0.001,  # 经度随机偏移
            'alt_offset': 10.0    # 海拔随机偏移
        },
        'base_url': 'http://localhost:5001',  # IVAS 服务器地址
        'report_hz': 1.0,  # 位置上报频率 (1Hz)
        'task_hz': 0.2     # 任务轮询频率 (0.2Hz)
    }

    print("\n配置信息:")
    print(f"  设备编号: {config['device_code']}")
    print(f"  账号: {config['account']}")
    print(f"  服务器地址: {config['base_url']}")
    print(f"  上报频率: {config['report_hz']} Hz")
    print(f"  轮询频率: {config['task_hz']} Hz")
    print()

    # 创建客户端实例
    client = IVASClient(**config)

    print("正在启动客户端...")

    # 在单独的线程中运行客户端
    client_thread = threading.Thread(target=client.run, daemon=True)
    client_thread.start()

    print("客户端已启动！按 Ctrl+C 停止运行。\n")

    try:
        # 主线程等待
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n正在停止客户端...")
        client.stop()
        client_thread.join(timeout=2)
        print("客户端已停止。")


def multi_device_example():
    """多设备示例 - 同时运行 3 个无人机客户端"""

    print("=" * 60)
    print("多设备示例 - 同时运行 3 个无人机客户端")
    print("=" * 60)

    # 配置多个设备
    devices = [
        {
            'device_code': 1,
            'account': 'ZSDX001',
            'password': 'password1',
            'base_lat': 23.0,
            'base_lon': 113.0,
        },
        {
            'device_code': 2,
            'account': 'ZSDX002',
            'password': 'password2',
            'base_lat': 23.001,
            'base_lon': 113.001,
        },
        {
            'device_code': 3,
            'account': 'ZSDX003',
            'password': 'password3',
            'base_lat': 23.002,
            'base_lon': 113.002,
        }
    ]

    clients = []
    threads = []

    # 创建并启动所有客户端
    for device_config in devices:
        # 补充通用配置
        device_config.update({
            'base_alt': 100.0,
            'coord_range': {
                'lat_offset': 0.001,
                'lon_offset': 0.001,
                'alt_offset': 10.0
            },
            'base_url': 'http://localhost:5001',
            'report_hz': 1.0,
            'task_hz': 0.2
        })

        client = IVASClient(**device_config)
        clients.append(client)

        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()
        threads.append(thread)

        print(f"设备 {device_config['device_code']} ({device_config['account']}) 已启动")

    print(f"\n所有 {len(clients)} 个设备已启动！按 Ctrl+C 停止运行。\n")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n正在停止所有设备...")
        for client in clients:
            client.stop()

        for thread in threads:
            thread.join(timeout=2)

        print("所有设备已停止。")


def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--multi':
        multi_device_example()
    else:
        single_device_example()


if __name__ == '__main__':
    print("\n提示: 使用 --multi 参数运行多设备示例")
    print("示例: python3 example.py --multi\n")
    main()
