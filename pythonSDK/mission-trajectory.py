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
    send_stick_control,
)

# ========== 配置 ==========
UAV_CONFIGS = [
    {'sn': '9N9CN2J0012CXY', 'user_id': 'pilot1', 'callsign': 'Alpha'},
    {'sn': '9N9CN8400164WH', 'user_id': 'pilot2', 'callsign': 'Bravo'},
    {'sn': '9N9CN180011TJN', 'user_id': 'pilot3', 'callsign': 'Charlie'},
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
        takeoff_mission = create_takeoff_mission(target_height=30.0)
        runners = run_parallel_missions(
            connections, takeoff_mission, UAV_CONFIGS)
        print("✓ 起飞完成")

        # 4. 飞行轨迹（这是关键函数！）
        success = fly_trajectory_sequence(
            runners=runners,
            waypoints=waypoints,
            height=100.0,
            max_speed=12,
            hover_between_waypoints=5.0
        )

        if success:
            print(f"✓ 完成所有 {len(waypoints)} 个航点！")

        # 5. 返航
        for runner in runners:
            return_home(runner.caller)
        print("✓ 返航指令已发送")

        # 6. 悬停监控
        print("按 Ctrl+C 退出...")
        while True:
            for runner in runners:
                send_stick_control(runner.mqtt)
            import time
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n中断退出")
    finally:
        cleanup_missions(runners)


if __name__ == '__main__':
    main()
