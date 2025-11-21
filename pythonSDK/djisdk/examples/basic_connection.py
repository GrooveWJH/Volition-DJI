#!/usr/bin/env python3
"""
基础DRC连接示例

演示如何建立DRC连接并进行基本的飞行控制。
"""
import time
from djisdk import setup_drc_connection, fly_to_point, return_home, stop_heartbeat

def main():
    # 配置参数（请根据实际情况修改）
    GATEWAY_SN = '1ZNDH800017VMA'  # 修改为您的无人机SN
    MQTT_CONFIG = {
        'host': '192.168.31.73',   # 修改为您的MQTT服务器
        'port': 1883,
        'username': 'dji',
        'password': 'lab605605'
    }

    try:
        print("🚁 建立DRC连接...")

        # 一键建立DRC连接
        mqtt, caller, heartbeat = setup_drc_connection(
            gateway_sn=GATEWAY_SN,
            mqtt_config=MQTT_CONFIG,
            user_callsign='测试飞行器'
        )

        print("✅ DRC连接建立成功")

        # 等待一段时间让数据稳定
        print("⏰ 等待数据稳定...")
        time.sleep(3)

        # 显示当前状态
        print(f"📍 当前位置: ({mqtt.osd_data['latitude']:.6f}, {mqtt.osd_data['longitude']:.6f})")
        print(f"📏 当前高度: {mqtt.osd_data['height']:.1f}m")
        print(f"🔋 电池电量: {mqtt.osd_data['battery_percent']}%")
        print(f"🧭 航向角度: {mqtt.osd_data['attitude_head']:.1f}°")

        # 检查电量
        if mqtt.osd_data['battery_percent'] < 30:
            print("⚠️  电量不足，建议充电后再进行飞行测试")
            return

        # 用户确认
        user_input = input("\n是否进行飞行测试？(y/N): ")
        if user_input.lower() != 'y':
            print("取消飞行测试")
            return

        print("\n🛫 开始飞行测试...")

        # 飞向一个相对安全的位置（当前位置附近）
        current_lat = mqtt.osd_data['latitude']
        current_lon = mqtt.osd_data['longitude']

        # 向北移动50米，高度50米（相对安全的测试参数）
        target_lat = current_lat + 0.00045  # 约50米
        target_height = 50.0

        print(f"🎯 飞向目标点: ({target_lat:.6f}, {current_lon:.6f}), 高度: {target_height}m")

        fly_to_id = fly_to_point(
            caller,
            latitude=target_lat,
            longitude=current_lon,
            height=target_height,
            max_speed=5  # 较慢的安全速度
        )

        # 监控飞行进度
        print("📊 监控飞行进度...")
        for _ in range(60):  # 最多等待60秒
            progress = mqtt.flyto_progress
            if progress['fly_to_id'] == fly_to_id:
                status = progress['status']
                remaining_dist = progress.get('remaining_distance', 0)
                remaining_time = progress.get('remaining_time', 0)

                print(f"状态: {status}, 剩余距离: {remaining_dist:.1f}m, 剩余时间: {remaining_time:.1f}s")

                if status in ['wayline_ok', 'wayline_failed']:
                    print(f"✅ 飞行完成，最终状态: {status}")
                    break

            time.sleep(1)

        # 等待几秒钟
        print("⏰ 悬停5秒...")
        time.sleep(5)

        # 返航
        print("🏠 执行返航...")
        return_home(caller)

        print("✅ 返航指令已发送")

        # 继续监控一段时间
        print("📊 监控返航状态...")
        time.sleep(10)

    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        # 清理资源
        print("🧹 清理资源...")
        if 'heartbeat' in locals():
            stop_heartbeat(heartbeat)
        if 'mqtt' in locals():
            mqtt.disconnect()
        print("👋 程序结束")

if __name__ == "__main__":
    main()