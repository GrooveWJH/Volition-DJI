#!/usr/bin/env python3
"""
相机变焦功能演示脚本

这是一个独立的演示脚本，展示如何使用 set_camera_zoom() 函数。
适合快速测试和集成到其他项目。
"""

from djisdk import MQTTClient, ServiceCaller, set_camera_zoom
import time

# 配置
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

GATEWAY_SN = '9N9CN2J0012CXY'  # 替换为你的无人机序列号
PAYLOAD_INDEX = '88-0-0'       # 替换为你的相机负载索引


def demo_zoom_control():
    """演示变焦控制功能"""
    print("=" * 60)
    print("DJI 相机变焦功能演示")
    print("=" * 60)

    # 1. 连接 MQTT
    print("\n[1/4] 连接 MQTT...")
    mqtt = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
    mqtt.connect()
    time.sleep(1)

    try:
        # 2. 演示基本变焦
        print("\n[2/4] 演示基本变焦...")
        print("  → 设置变焦倍数为 2x")
        set_camera_zoom(mqtt, PAYLOAD_INDEX, 2.0)
        time.sleep(2)

        print("  → 设置变焦倍数为 5x")
        set_camera_zoom(mqtt, PAYLOAD_INDEX, 5.0)
        time.sleep(2)

        print("  → 设置变焦倍数为 10x")
        set_camera_zoom(mqtt, PAYLOAD_INDEX, 10.0)
        time.sleep(2)

        # 3. 演示渐进式变焦
        print("\n[3/4] 演示渐进式变焦（10x → 20x）...")
        for zoom in range(10, 21, 2):
            print(f"  → 变焦: {zoom}x")
            set_camera_zoom(mqtt, PAYLOAD_INDEX, float(zoom))
            time.sleep(1)

        # 4. 回到初始状态
        print("\n[4/4] 恢复初始变焦...")
        print("  → 设置变焦倍数为 2x")
        set_camera_zoom(mqtt, PAYLOAD_INDEX, 2.0)
        time.sleep(1)

        print("\n✓ 演示完成！")

    except Exception as e:
        print(f"\n✗ 演示失败: {e}")

    finally:
        print("\n断开连接...")
        mqtt.disconnect()


if __name__ == "__main__":
    print("\n⚠️  注意：")
    print("  1. 确保无人机已开机并连接")
    print("  2. 确保已进入 DRC 模式")
    print("  3. 修改脚本中的 GATEWAY_SN 和 PAYLOAD_INDEX")
    print("\n按 Enter 键开始演示...")
    input()

    demo_zoom_control()
