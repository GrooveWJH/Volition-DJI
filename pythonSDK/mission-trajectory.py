#!/usr/bin/env python3
"""
轨迹飞行任务 - 多机版本

支持多架无人机同时执行不同的轨迹文件。
每架无人机可以指定独立的轨迹文件、飞行参数和相机设置。
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
import concurrent.futures

# ========== 配置 ==========

# 无人机配置（每架无人机可以有独立的轨迹文件和飞行参数）
UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot1',
        'callsign': 'Alpha',
        'trajectory_file': 'Trajectory/uav1.json',  # 独立轨迹文件
        'flight_height': 100.0,  # 飞行高度（米）
        'max_speed': 15,  # 最大速度（m/s）
        'hover_time': 20.0,  # 航点间悬停时间（秒）- 悬停时云台朝下
        'camera': {
            'gimbal_mode': 1,  # 0=回中, 1=向下, 2=偏航回中, 3=俯仰向下
            'zoom_factor': 7,  # 变焦倍数（2-200）
        }
    },
    # {
    #     'sn': '9N9CN8400164WH',
    #     'user_id': 'pilot2',
    #     'callsign': 'Bravo',
    #     'trajectory_file': 'Trajectory/uav2.json',  # 不同的轨迹
    #     'flight_height': 120.0,
    #     'max_speed': 12,
    #     'hover_time': 3.0,
    #     'camera': {
    #         'gimbal_mode': 1,
    #         'zoom_factor': 5,
    #     }
    # },
    # {
    #     'sn': '9N9CN180011TJN',
    #     'user_id': 'pilot3',
    #     'callsign': 'Charlie',
    #     'trajectory_file': 'Trajectory/uav3.json',
    #     'flight_height': 80.0,
    #     'max_speed': 10,
    #     'hover_time': 4.0,
    #     'camera': {
    #         'gimbal_mode': 1,
    #         'zoom_factor': 10,
    #     }
    # },
]

MQTT_CONFIG = {
    'host': 'grve.me',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# 起飞参数（所有无人机共用）
TAKEOFF_HEIGHT = 20.0  # 起飞高度（米）
TAKEOFF_TOLERANCE = 0.5  # 高度容差（米）
TAKEOFF_THROTTLE = 500  # 油门偏移量

# 调试选项
DEBUG_MODE = True  # 是否打印详细的 event 数据
SHOW_PROGRESS = True  # 是否显示飞行进度

# ========== 辅助函数 ==========


def execute_single_trajectory(runner, config):
    """
    执行单架无人机的轨迹飞行任务（在独立线程中运行）

    Args:
        runner: MissionRunner 对象
        config: 无人机配置（包含 trajectory_file, flight_height 等）
    """
    callsign = config.get('callsign', 'UAV')

    try:
        # 1. 加载该无人机的轨迹文件
        trajectory_file = config.get('trajectory_file')
        if not trajectory_file:
            print(f"[{callsign}] 警告：未指定轨迹文件，跳过")
            return False

        waypoints = load_trajectory(trajectory_file)
        if SHOW_PROGRESS:
            print(f"[{callsign}] 加载了 {len(waypoints)} 个航点 (来自 {trajectory_file})")

        # 2. 初始化相机设置
        mqtt = runner.mqtt
        camera_config = config.get('camera', {})
        payload_index = mqtt.get_payload_index() or "88-0-0"

        gimbal_mode = camera_config.get('gimbal_mode', 1)
        zoom_factor = camera_config.get('zoom_factor', 7)

        if SHOW_PROGRESS:
            print(f"[{callsign}] 设置云台模式 {gimbal_mode}，变焦 {zoom_factor}x")

        reset_gimbal(mqtt, payload_index=payload_index, reset_mode=gimbal_mode)
        set_camera_zoom(mqtt, payload_index=payload_index, zoom_factor=zoom_factor, camera_type="zoom")
        time.sleep(1)  # 等待相机设置生效

        # 3. 执行轨迹飞行
        flight_height = config.get('flight_height', 100.0)
        max_speed = config.get('max_speed', 12)
        hover_time = config.get('hover_time', 5.0)

        success = fly_trajectory_sequence(
            runners=[runner],
            waypoints=waypoints,
            height=flight_height,
            max_speed=max_speed,
            hover_between_waypoints=hover_time,
            show_progress=SHOW_PROGRESS,
            debug=DEBUG_MODE
        )

        if success:
            print(f"[{callsign}] ✓ 完成所有 {len(waypoints)} 个航点！")
        else:
            print(f"[{callsign}] ✗ 轨迹飞行失败")

        return success

    except Exception as e:
        print(f"[{callsign}] ✗ 轨迹飞行异常: {e}")
        return False


# ========== 主流程 ==========


def main():
    print("=" * 60)
    print("多无人机轨迹飞行任务")
    print("=" * 60)
    print(f"将启动 {len(UAV_CONFIGS)} 架无人机\n")

    # 1. 连接所有无人机
    print("[1/4] 连接无人机...")
    connections = setup_multiple_drc_connections(
        uav_configs=UAV_CONFIGS,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=100,
        hsi_frequency=10,
        skip_drc_setup=True,
    )
    print(f"✓ 已连接 {len(connections)} 架无人机\n")

    runners = None

    try:
        # 2. 统一起飞
        print(f"[2/4] 起飞到 {TAKEOFF_HEIGHT}m...")
        takeoff_mission = create_takeoff_mission(
            target_height=TAKEOFF_HEIGHT,
            height_tolerance=TAKEOFF_TOLERANCE,
            throttle_offset=TAKEOFF_THROTTLE
        )
        runners = run_parallel_missions(connections, takeoff_mission, UAV_CONFIGS)
        print("✓ 起飞完成\n")

        # 3. 并行执行各自的轨迹飞行（真正的并发）
        print(f"[3/4] 开始轨迹飞行（{len(runners)} 架并行）...")
        print("-" * 60)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runners)) as executor:
            futures = {
                executor.submit(execute_single_trajectory, runner, config): config
                for runner, config in zip(runners, UAV_CONFIGS)
            }

            # 等待所有轨迹飞行完成
            all_success = True
            for future in concurrent.futures.as_completed(futures):
                config = futures[future]
                callsign = config.get('callsign', 'UAV')
                try:
                    success = future.result()
                    if not success:
                        all_success = False
                except Exception as e:
                    print(f"[{callsign}] ✗ 线程异常: {e}")
                    all_success = False

        print("-" * 60)
        if all_success:
            print("✓ 所有无人机轨迹飞行完成\n")
        else:
            print("⚠ 部分无人机轨迹飞行失败\n")

        # 4. 统一返航
        print("[4/4] 返航...")
        for runner in runners:
            callsign = runner.config.get('callsign', 'UAV')
            return_home(runner.caller)
            print(f"[{callsign}] 返航指令已发送")
        print("✓ 所有返航指令已发送\n")

        # 5. 悬停监控
        print("按 Ctrl+C 退出...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n中断退出")
    finally:
        if runners:
            cleanup_missions(runners)


if __name__ == '__main__':
    main()
