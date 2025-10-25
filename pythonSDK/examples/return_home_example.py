#!/usr/bin/env python3
"""
一键返航示例

演示如何使用 return_home 函数控制无人机返航。
"""
from djisdk import setup_drc_connection, return_home, stop_heartbeat

# 配置
GATEWAY_SN = "9N9CN2J0012CXY"
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

def main():
    print("=" * 60)
    print("一键返航示例")
    print("=" * 60)

    # 建立 DRC 连接
    mqtt, caller, heartbeat = setup_drc_connection(
        GATEWAY_SN,
        MQTT_CONFIG,
        user_id='pilot_1',
        user_callsign='Pilot 1',
        osd_frequency=100,
        hsi_frequency=10
    )

    try:
        # 执行返航
        print("\n按 Enter 执行一键返航...")
        input()

        result = return_home(caller)
        print(f"返航结果: {result}")

        print("\n返航指令已发送！无人机正在返回起飞点...")

    except KeyboardInterrupt:
        print("\n\n操作已取消")
    finally:
        # 清理资源
        print("\n正在清理资源...")
        stop_heartbeat(heartbeat)
        mqtt.disconnect()
        print("资源清理完成")


if __name__ == "__main__":
    main()
