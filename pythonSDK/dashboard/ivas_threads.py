"""
IVAS 线程函数 - 独立的后台任务

包含三个纯函数，用于 IVAS 系统的后台任务：
1. position_reporter - 位置上报线程
2. target_reporter - 目标上报线程
3. task_poller - 任务轮询和分发线程

设计原则：
- 纯函数，无状态
- 精确定时（使用 perf_counter）
- 通过 stop_event 优雅退出
"""

import time
import threading
import random
from typing import Dict, Any


def position_reporter(
    mqtt_client,
    ivas_client,
    device_code: int,
    callsign: str,
    interval: float,
    stop_event: threading.Event
):
    """
    位置上报线程（纯函数）

    从 MQTTClient 获取真实位置数据，定时上报到 IVAS 服务器。

    Args:
        mqtt_client: DJI MQTT 客户端（用于获取位置数据）
        ivas_client: IVAS HTTP 客户端
        device_code: 设备编号（1, 2, 3）
        callsign: 设备呼号（用于日志显示）
        interval: 上报间隔（秒）
        stop_event: 停止事件（用于优雅退出）
    """
    next_tick = time.perf_counter()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 从 MQTT 获取真实数据
            lat, lon, height = mqtt_client.get_position()
            heading = mqtt_client.get_attitude_head()
            h_speed, _, _, _ = mqtt_client.get_speed()

            # 检查 GPS 是否有效
            if lat is not None and lon is not None:
                # 判断运动状态（水平速度 > 0.5 m/s）
                motion = 1 if h_speed and h_speed > 0.5 else 0

                # 上报位置
                success = ivas_client.report_position(
                    device_code=device_code,
                    lat=lat,
                    lon=lon,
                    alt=height or 0.0,
                    azimuth=int(heading or 0),
                    motion=motion
                )

                if success:
                    print(f"[上报] [{callsign}] 纬度:{lat:.6f} 经度:{lon:.6f} 高度:{height:.2f}m")

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


def target_reporter(
    ivas_client,
    base_lat: float,
    base_lon: float,
    base_alt: float,
    coord_range: Dict[str, float],
    interval: float,
    stop_event: threading.Event
):
    """
    目标上报线程（纯函数）

    生成随机目标数据，定时上报到 IVAS 服务器。

    Args:
        ivas_client: IVAS HTTP 客户端
        base_lat: 基准纬度
        base_lon: 基准经度
        base_alt: 基准海拔
        coord_range: 坐标随机范围（lat_offset, lon_offset, alt_offset）
        interval: 上报间隔（秒）
        stop_event: 停止事件
    """
    next_tick = time.perf_counter()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 生成随机目标数据
            obj_cnt = random.randint(0, 3)
            objs = []

            lat_offset = coord_range['lat_offset']
            lon_offset = coord_range['lon_offset']

            for _ in range(obj_cnt):
                target_lat = base_lat + random.uniform(-lat_offset, lat_offset)
                target_lon = base_lon + random.uniform(-lon_offset, lon_offset)
                target_alt = base_alt + random.uniform(-10, 10)

                objs.append({
                    'id': random.randint(1000, 9999),
                    'cls': random.randint(0, 2),  # 0:人, 1:车, 2:飞机
                    'gis': [target_lon, target_lat, target_alt],
                    'bbox': [
                        random.uniform(0, 1920),
                        random.uniform(0, 1080),
                        random.uniform(50, 200),
                        random.uniform(50, 200)
                    ],
                    'obj_img': f"http://example.com/img/{random.randint(1, 100)}.jpg"
                })

            # 上报目标
            ivas_client.report_targets(
                timestamp=int(time.time()),
                objs=objs
            )

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


def task_poller(
    ivas_client,
    uav_clients_map: Dict[int, Any],
    interval: float,
    stop_event: threading.Event
):
    """
    任务轮询和分发线程（纯函数）

    单点轮询 IVAS 服务器的任务队列，根据任务 ID 路由分发。

    核心功能（保留 TaskDistributor 的逻辑）：
    - 单点轮询（避免任务被重复消费）
    - 智能路由（id=99 广播，id=1/2/3 单播）
    - 任务去重（避免重复执行）

    Args:
        ivas_client: IVAS HTTP 客户端
        uav_clients_map: 设备映射 {device_code: uav_client_dict}
        interval: 轮询间隔（秒）
        stop_event: 停止事件
    """
    next_tick = time.perf_counter()
    executed_tasks = set()  # 任务去重集合

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 轮询任务
            result = ivas_client.poll_task()

            if result:
                task_data = result['data']
                target_id = task_data.get('id', 0)
                mission = task_data.get('mission', 0)

                # 路由分发
                if target_id == 99:
                    # 广播模式：分发给所有设备
                    _distribute_broadcast(task_data, uav_clients_map, executed_tasks)
                elif target_id in uav_clients_map:
                    # 单播模式：分发给指定设备
                    print(f"[任务] 路由到设备 {target_id} (mission={mission})")
                    uav = uav_clients_map[target_id]
                    _execute_task(uav, task_data)
                else:
                    print(f"[任务] ⚠️ 未知任务 ID: {target_id} (mission={mission})")

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


def _distribute_broadcast(
    task_data: Dict[str, Any],
    uav_clients_map: Dict[int, Any],
    executed_tasks: set
):
    """
    广播分发（纯函数）

    将任务广播到所有设备，带任务去重和类型验证。

    Args:
        task_data: IVAS 任务数据
        uav_clients_map: 设备映射
        executed_tasks: 已执行任务集合（用于去重）
    """
    mission = task_data.get('mission', 0)
    mission_names = {1: "起飞", 2: "降落", 3: "返航"}

    # 1. 类型验证：只有 1/2/3 支持广播
    if mission not in [1, 2, 3]:
        print(f"[任务] ❌ 任务 {mission} 不支持广播，仅支持起飞/降落/返航")
        return

    # 2. 任务去重（使用 mission+timestamp 作为唯一标识）
    task_signature = f"{mission}_{task_data.get('timestamp', int(time.time()))}"

    if task_signature in executed_tasks:
        print(f"[任务] ⏭️ 任务 {task_signature} 已执行过，跳过")
        return

    executed_tasks.add(task_signature)

    # 清理旧记录（保留最近 100 条）
    if len(executed_tasks) > 100:
        old_tasks = list(executed_tasks)[:50]
        for old_task in old_tasks:
            executed_tasks.discard(old_task)

    # 3. 广播分发
    mission_name = mission_names.get(mission, f"任务{mission}")
    print(f"[任务] 📢 广播: {mission_name} (ID:99) → {len(uav_clients_map)} 个设备")

    success_count = 0
    for device_code, uav in uav_clients_map.items():
        try:
            _execute_task(uav, task_data)
            success_count += 1
            print(f"[任务]   ✓ 设备 {device_code} 已接收")
        except Exception as e:
            print(f"[任务]   ✗ 设备 {device_code} 失败: {e}")

    print(f"[任务] ✅ 广播完成: {success_count}/{len(uav_clients_map)} 个设备成功")


def _execute_task(uav_client: Dict[str, Any], task_data: Dict[str, Any]):
    """
    执行任务（纯函数）

    调用 djisdk 的 ivas_executor 执行任务。

    Args:
        uav_client: UAV 客户端字典（包含 mqtt, caller, heartbeat 等）
        task_data: IVAS 任务数据
    """
    from djisdk.tasks.ivas_executor import execute_ivas_task
    from djisdk.tasks.runner import MissionRunner

    # 停止旧任务（如果存在）
    if 'current_runner' in uav_client and uav_client['current_runner']:
        runner = uav_client['current_runner']
        if hasattr(runner, 'running') and runner.running:
            runner.stop()

    # 创建新的 runner
    runner_config = {
        'callsign': uav_client.get('callsign', 'Unknown'),
        'sn': uav_client['mqtt'].gateway_sn,
        'flight_height': uav_client.get('flight_height', 100.0)
    }

    runner = MissionRunner(
        uav_client['mqtt'],
        uav_client['caller'],
        uav_client['heartbeat'],
        runner_config
    )

    uav_client['current_runner'] = runner  # 保存引用（用于中断）

    # 在后台线程执行任务
    def task_wrapper():
        try:
            execute_ivas_task(
                mqtt=uav_client['mqtt'],
                caller=uav_client['caller'],
                task_data=task_data,
                uav_config=uav_client.get('config', {}),
                runner=runner
            )
        except Exception as e:
            print(f"[任务] ❌ 执行异常: {e}")
        finally:
            uav_client['current_runner'] = None

    thread = threading.Thread(target=task_wrapper, daemon=True)
    thread.start()
