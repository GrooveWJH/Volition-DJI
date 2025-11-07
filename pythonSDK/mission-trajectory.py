#!/usr/bin/env python3
"""
轨迹飞行任务 - 简化版示例

展示如何使用 djisdk 的轨迹任务模块快速实现多航点飞行。
"""
from djisdk import (
    setup_multiple_drc_connections,
    run_parallel_missions,
    cleanup_missions,
    create_takeoff_mission,
    load_trajectory,
    fly_trajectory_sequence,
    return_home,
)
from djisdk.services import reset_gimbal
from djisdk.services.drc_commands import set_camera_zoom
import time

# ========== 配置 ==========
UAV_CONFIGS = [
    {'sn': '9N9CN2J0012CXY', 'user_id': 'pilot1', 'callsign': 'Alpha'},
    # {'sn': '9N9CN8400164WH', 'user_id': 'pilot2', 'callsign': 'Bravo'},
    # {'sn': '9N9CN180011TJN', 'user_id': 'pilot3', 'callsign': 'Charlie'},
]

MQTT_CONFIG = {
    'host': 'grve.me',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# ========== 主流程 ==========


def main():
    # 1. 加载航点
    waypoints = load_trajectory('Trajectory/uav1.json')
    print(f"✓ 加载了 {len(waypoints)} 个航点")

    # 2. 连接无人机
    connections = setup_multiple_drc_connections(
        uav_configs=UAV_CONFIGS,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=100,
        hsi_frequency=10,
        skip_drc_setup=True,
    )

    try:
        # 3. 起飞到 30m
        takeoff_mission = create_takeoff_mission(
            target_height=20.0, height_tolerance=0.5, throttle_offset=500)
        runners = run_parallel_missions(
            connections, takeoff_mission, UAV_CONFIGS)
        print("✓ 起飞完成")

        # 4. 初始化相机设置（云台向下 + 变焦 7x）
        print("\n[相机初始化]")
        for runner in runners:
            mqtt = runner.mqtt
            callsign = runner.config.get('callsign', 'UAV')

            # 获取 payload_index
            payload_index = mqtt.get_payload_index() or "88-0-0"

            print(f"  [{callsign}] 设置云台向下...")
            reset_gimbal(mqtt, payload_index=payload_index,
                         reset_mode=1)  # 1 = 向下

            print(f"  [{callsign}] 设置变焦 7x...")
            set_camera_zoom(mqtt, payload_index=payload_index,
                            zoom_factor=7, camera_type="zoom")

        print("✓ 相机初始化完成\n")
        time.sleep(2)  # 等待相机设置生效

        # 5. 飞行轨迹
        success = fly_trajectory_sequence(
            runners=runners,
            waypoints=waypoints,
            height=100.0,
            max_speed=15,
            hover_between_waypoints=5.0,
            debug=True  # 启用调试模式，打印详细的 event 数据
        )

        if success:
            print(f"✓ 完成所有 {len(waypoints)} 个航点！")

        # 6. 返航
        for runner in runners:
            return_home(runner.caller)
        print("✓ 返航指令已发送")

        # 7. 悬停监控
        print("按 Ctrl+C 退出...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n中断退出")
    finally:
        cleanup_missions(runners)


if __name__ == '__main__':
    main()
