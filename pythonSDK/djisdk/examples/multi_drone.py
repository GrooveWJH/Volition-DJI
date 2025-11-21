#!/usr/bin/env python3
"""
多机并行控制示例

演示如何同时控制多架无人机，展示并行连接的性能优势。
"""
import time
from djisdk import setup_multiple_drc_connections, fly_to_point, return_home, stop_heartbeat

def main():
    # 多机配置（请根据实际情况修改）
    UAV_CONFIGS = [
        {'sn': '1ZNDH800017VMA', 'callsign': 'Alpha-Leader'},
        {'sn': '1ZNDH800017VMB', 'callsign': 'Bravo-Wing'},
        {'sn': '1ZNDH800017VMC', 'callsign': 'Charlie-Wing'},
    ]

    MQTT_CONFIG = {
        'host': '192.168.31.73',
        'port': 1883,
        'username': 'dji',
        'password': 'lab605605'
    }

    connections = []

    try:
        print(f"🚁 并行建立 {len(UAV_CONFIGS)} 架无人机的DRC连接...")
        start_time = time.time()

        # 并行连接多架无人机（性能提升3倍）
        connections = setup_multiple_drc_connections(
            uav_configs=UAV_CONFIGS,
            mqtt_config=MQTT_CONFIG,
            heartbeat_interval=0.2
        )

        connection_time = time.time() - start_time
        print(f"✅ 所有连接建立完成，耗时: {connection_time:.1f}秒")

        # 显示所有无人机状态
        print("\n📊 无人机状态概览:")
        for i, (mqtt, caller, heartbeat) in enumerate(connections):
            config = UAV_CONFIGS[i]
            print(f"\n🛩️  {config['callsign']} ({config['sn']}):")
            print(f"   📍 位置: ({mqtt.osd_data['latitude']:.6f}, {mqtt.osd_data['longitude']:.6f})")
            print(f"   📏 高度: {mqtt.osd_data['height']:.1f}m")
            print(f"   🔋 电量: {mqtt.osd_data['battery_percent']}%")

        # 检查所有无人机电量
        low_battery_uavs = []
        for i, (mqtt, caller, heartbeat) in enumerate(connections):
            if mqtt.osd_data['battery_percent'] < 30:
                low_battery_uavs.append(UAV_CONFIGS[i]['callsign'])

        if low_battery_uavs:
            print(f"\n⚠️  以下无人机电量不足: {', '.join(low_battery_uavs)}")
            print("建议充电后再进行飞行测试")
            return

        # 用户确认
        user_input = input(f"\n是否进行 {len(connections)} 架无人机的编队飞行测试？(y/N): ")
        if user_input.lower() != 'y':
            print("取消飞行测试")
            return

        print("\n🛫 开始编队飞行测试...")

        # 为每架无人机分配不同的目标点（简单的直线编队）
        base_lat = connections[0][0].osd_data['latitude']
        base_lon = connections[0][0].osd_data['longitude']

        formation_positions = [
            (base_lat + 0.0003, base_lon, 50.0),        # 领机：北30米
            (base_lat + 0.0003, base_lon + 0.0003, 55.0),  # 僚机1：东北30米
            (base_lat + 0.0003, base_lon - 0.0003, 55.0),  # 僚机2：西北30米
        ]

        # 同时发送所有飞行指令
        fly_to_ids = []
        for i, (mqtt, caller, heartbeat) in enumerate(connections):
            if i < len(formation_positions):
                lat, lon, height = formation_positions[i]
                config = UAV_CONFIGS[i]

                print(f"🎯 {config['callsign']} 飞向: ({lat:.6f}, {lon:.6f}), 高度: {height}m")

                fly_to_id = fly_to_point(
                    caller,
                    latitude=lat,
                    longitude=lon,
                    height=height,
                    max_speed=6
                )
                fly_to_ids.append((fly_to_id, config['callsign']))

        # 监控所有无人机的飞行进度
        print("\n📊 监控编队飞行进度...")
        completed_uavs = set()

        for _ in range(120):  # 最多等待2分钟
            print(f"\n--- 时间: {_+1}秒 ---")

            all_completed = True
            for i, (mqtt, caller, heartbeat) in enumerate(connections):
                if i < len(fly_to_ids):
                    fly_to_id, callsign = fly_to_ids[i]
                    progress = mqtt.flyto_progress

                    if progress['fly_to_id'] == fly_to_id:
                        status = progress['status']
                        remaining_dist = progress.get('remaining_distance', 0)

                        if callsign not in completed_uavs:
                            print(f"🛩️  {callsign}: {status}, 剩余距离: {remaining_dist:.1f}m")

                        if status in ['wayline_ok', 'wayline_failed']:
                            if callsign not in completed_uavs:
                                print(f"✅ {callsign} 飞行完成: {status}")
                                completed_uavs.add(callsign)
                        else:
                            all_completed = False

            if all_completed and len(completed_uavs) == len(fly_to_ids):
                print("\n🎉 所有无人机编队就位完成!")
                break

            time.sleep(1)

        # 编队悬停
        print("\n⏰ 编队悬停10秒...")
        time.sleep(10)

        # 所有无人机同时返航
        print("\n🏠 编队返航...")
        for i, (mqtt, caller, heartbeat) in enumerate(connections):
            callsign = UAV_CONFIGS[i]['callsign']
            print(f"🏠 {callsign} 执行返航")
            return_home(caller)

        print("✅ 所有返航指令已发送")

        # 监控返航状态
        print("\n📊 监控返航状态...")
        time.sleep(15)

        print("🎉 编队飞行演示完成!")

    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        # 清理所有资源
        print("\n🧹 清理资源...")
        for mqtt, caller, heartbeat in connections:
            try:
                stop_heartbeat(heartbeat)
                mqtt.disconnect()
            except:
                pass
        print("👋 程序结束")

if __name__ == "__main__":
    main()