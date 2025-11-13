"""
IVAS 线程函数 - 独立的后台任务

包含四个纯函数，用于 IVAS 系统的后台任务：
1. position_reporter - 位置上报线程（从真实MQTT获取数据）
2. target_reporter - 目标上报线程（固定基准点，生成假数据）
3. fake_target_reporter - 假目标上报线程（跟随无人机GPS，生成假数据）
4. task_poller - 任务轮询和分发线程

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
    stop_event: threading.Event,
    require_gps: bool = True,
    print_duration: float = 5.0
):
    """
    位置上报线程（纯函数）

    从 MQTTClient 获取真实位置数据，定时上报到 IVAS 服务器。

    Args:
        mqtt_client: DJI MQTT 客户端（用于获取位置数据）
        ivas_client: IVAS HTTP 客户端
        device_code: 设备编号（1, 2, 3）
        callsign: 设备呼号（用于日志显示）
        interval: 上报间隔（秒，推荐 1.0 即 1Hz）
        stop_event: 停止事件（用于优雅退出）
        require_gps: 是否要求GPS有效才上报（False则无GPS时lat/lon设为0）
        print_duration: 打印日志的时长（秒，前N秒打印，之后静默）
    """
    next_tick = time.perf_counter()
    start_time = time.perf_counter()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 从 MQTT 获取真实数据
            lat, lon, _ellipsoid_height = mqtt_client.get_position()
            relative_height = mqtt_client.get_relative_height()  # ✅ 使用相对高度
            heading = mqtt_client.get_attitude_head()
            h_speed, _, _, _ = mqtt_client.get_speed()

            # GPS 有效性检查
            gps_valid = (lat is not None and lon is not None)

            # 根据 require_gps 决定是否上报
            should_report = gps_valid or (not require_gps)

            if should_report:
                # 如果 GPS 无效且 require_gps=False，则使用 0
                if not gps_valid:
                    lat, lon = 0.0, 0.0

                # 判断运动状态（水平速度 > 0.5 m/s）
                motion = 1 if h_speed and h_speed > 0.5 else 0

                # 上报位置（使用相对高度）
                success = ivas_client.report_position(
                    device_code=device_code,
                    lat=lat,
                    lon=lon,
                    alt=relative_height or 0.0,  # ✅ 使用相对高度
                    azimuth=int(heading or 0),
                    motion=motion,
                    user_name=callsign  # 传入呼号作为用户名称
                )

                # 前5秒打印日志
                elapsed = current - start_time
                if success and elapsed <= print_duration:
                    gps_status = "GPS有效" if gps_valid else "无GPS"
                    height_str = f"{relative_height:.2f}m" if relative_height is not None else "N/A"
                    print(
                        f"[上报] [{callsign}] {gps_status} | 纬度:{lat:.6f} 经度:{lon:.6f} 相对高度:{height_str}")

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


def fake_target_reporter(
    mqtt_client,
    ivas_client,
    device_code: int,
    callsign: str,
    config: Dict[str, Any],
    stop_event: threading.Event
):
    """
    假目标上报线程（跟随无人机GPS位置）

    从 MQTTClient 获取真实GPS位置，在其周围10m范围内生成假目标。

    新特性（v2.0）：
    - 固定 ID 池：每个 UAV 循环使用 10 个固定 ID
    - 加权类别：90% 车，10% 人
    - 时间窗口：仅在到达航点后 20 秒内上报
    - 慢速上报：每 2 秒更新一个目标

    Args:
        mqtt_client: DJI MQTT 客户端（用于获取无人机GPS）
        ivas_client: IVAS HTTP 客户端
        device_code: 设备编号（1, 2, 3）
        callsign: 设备呼号（用于日志显示）
        config: 配置字典，包含：
            - report_hz: 上报频率（Hz）
            - lat_offset, lon_offset: 经纬度偏移
            - target_count: 每次上报的目标数量
            - altitude: 目标高度（固定值）
            - require_gps: 是否要求GPS有效
            - target_classes: 目标类别列表
            - target_class_weights: 目标类别权重
            - max_targets_per_uav: 每个 UAV 最多目标数
            - report_after_waypoint: 是否仅在航点后上报
            - report_duration: 航点后上报持续时间（秒）
            - enable_debug_log: 是否打印调试日志
        stop_event: 停止事件（用于优雅退出）
    """
    next_tick = time.perf_counter()

    # ID 管理：每个 UAV 有固定的 ID 池
    base_id = device_code * 10  # UAV1: 10, UAV2: 20, UAV3: 30
    max_targets = config.get('max_targets_per_uav', 10)
    current_index = 0  # 循环索引 0~9

    # 航点到达检测
    last_flyto_status = None
    waypoint_arrival_time = None

    # 上报间隔
    interval = 1.0 / config['report_hz']

    # 启动提示（可选）
    if config.get('enable_debug_log', False):
        id_range = f"{base_id}~{base_id + max_targets - 1}"
        print(f"[假目标] [{callsign}] 启动 - ID 池: {id_range}, 频率: {config['report_hz']}Hz, 窗口模式: {'开启' if config.get('report_after_waypoint') else '关闭'}")

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 1. 航点到达检测（如果启用窗口模式）
            if config.get('report_after_waypoint', False):
                progress = mqtt_client.get_flyto_progress()
                current_status = progress.get('status')

                # 检测到新到达航点
                if current_status == 'wayline_ok' and last_flyto_status != 'wayline_ok':
                    waypoint_arrival_time = current
                    if config.get('enable_debug_log', False):
                        way_point_index = progress.get('way_point_index', '?')
                        print(f"[假目标] [{callsign}] 🎯 航点{way_point_index}到达，开始 {config.get('report_duration', 20.0)}s 上报窗口")

                last_flyto_status = current_status

                # 检查是否在上报窗口内
                if waypoint_arrival_time is None:
                    # 还未到达任何航点
                    next_tick += interval
                    continue

                elapsed = current - waypoint_arrival_time
                report_duration = config.get('report_duration', 20.0)

                if elapsed > report_duration:
                    # 超过上报窗口，等待下一个航点
                    if waypoint_arrival_time is not None:  # 第一次超时打印提示
                        if config.get('enable_debug_log', False):
                            print(f"[假目标] [{callsign}] ⏸️  上报窗口结束，等待下一个航点...")
                        waypoint_arrival_time = None  # 清空状态
                    next_tick += interval
                    continue

            # 2. 获取无人机GPS位置
            lat, lon, _ = mqtt_client.get_position()

            # 3. GPS有效性检查
            gps_valid = (lat is not None and lon is not None)

            # 根据 require_gps 决定是否上报
            should_report = gps_valid or (not config['require_gps'])

            if not should_report:
                next_tick += interval
                continue

            # 如果GPS无效但 require_gps=False，使用 (0, 0)
            if not gps_valid:
                lat, lon = 0.0, 0.0

            # 4. 生成假目标
            target_id = base_id + current_index

            # 在 10m 范围内随机偏移
            target_lat = lat + random.uniform(-config['lat_offset'], config['lat_offset'])
            target_lon = lon + random.uniform(-config['lon_offset'], config['lon_offset'])
            target_alt = config['altitude']  # 固定高度（地面目标）

            # 加权随机选择目标类别（90% 车，10% 人）
            target_cls = random.choices(
                config['target_classes'],
                weights=config.get('target_class_weights', [0.5, 0.5]),
                k=1
            )[0]

            # 生成bbox（假设1920x1080图像）
            bbox_x = random.uniform(0, 1920 - 200)
            bbox_y = random.uniform(0, 1080 - 200)
            bbox_w = random.uniform(50, 200)
            bbox_h = random.uniform(50, 200)

            obj = {
                'id': target_id,
                'cls': target_cls,
                'gis': [target_lon, target_lat, target_alt],  # 注意：lon在前
                'bbox': [bbox_x, bbox_y, bbox_w, bbox_h],
                'obj_img': f"http://example.com/fake_target_{target_id}.jpg"
            }

            # 5. 上报目标
            success = ivas_client.report_targets(
                timestamp=int(time.time()),
                objs=[obj]
            )

            # 6. 打印日志（可选）
            if config.get('enable_debug_log', False) and success:
                gps_status = "GPS有效" if gps_valid else "无GPS"
                cls_names = {0: '人', 1: '车', 2: '飞机'}
                target_info = f"ID:{obj['id']}({cls_names[obj['cls']]})"
                print(f"[假目标] [{callsign}] {gps_status} | 基准GPS:({lat:.6f}, {lon:.6f}) | {target_info}")

            # 7. 循环更新索引（0 → 1 → ... → 9 → 0）
            current_index = (current_index + 1) % max_targets

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


def task_poller(
    ivas_client,
    uav_clients_map: Dict[int, Any],
    interval: float,
    stop_event: threading.Event,
    enable_task_execution: bool = True
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
        enable_task_execution: 是否执行任务分发（False时仅监视，不执行）
    """
    next_tick = time.perf_counter()
    executed_tasks = set()  # 任务去重集合

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 轮询任务
            result = ivas_client.poll_task()

            if result:
                # 打印任务分隔符
                print("\n" + "="*60)
                print(f"[任务] 🎯 接收到新任务 (时间: {time.strftime('%H:%M:%S')})")
                print("="*60)

                task_data = result['data']
                target_id = task_data.get('id', 0)
                mission = task_data.get('mission', 0)

                # 检查是否启用任务执行
                if not enable_task_execution:
                    print(
                        f"[任务] 👁️ 监视模式：任务已接收但不执行 (ID:{target_id}, mission={mission})")
                    print("="*60 + "\n")
                    next_tick += interval
                    continue

                # 路由分发
                if target_id == 99:
                    # 广播模式：分发给所有设备
                    _distribute_broadcast(
                        task_data, uav_clients_map, executed_tasks)
                elif target_id in uav_clients_map:
                    # 单播模式：分发给指定设备
                    print(f"[任务] 路由到设备 {target_id} (mission={mission})")
                    uav = uav_clients_map[target_id]
                    _execute_task(uav, task_data)
                else:
                    print(f"[任务] ⚠️ 未知任务 ID: {target_id} (mission={mission})")

                # 任务处理完成后打印分隔符
                print("="*60 + "\n")

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

    runner.running = True  # 设置为运行状态，供任务执行和中断检查

    uav_client['current_runner'] = runner  # 保存引用（用于中断）

    # 在后台线程执行任务
    def task_wrapper():
        try:
            execute_ivas_task(
                task_data,                          # 第1个参数：任务数据
                uav_client['mqtt'],                 # 第2个参数：mqtt_client
                uav_client['caller'],               # 第3个参数：caller
                uav_client.get('config', {}),       # 第4个参数：uav_config
                heartbeat_thread=uav_client.get(
                    'heartbeat'),  # 可选参数：heartbeat_thread
                runner=runner                       # 可选参数：runner
            )
        except Exception as e:
            # 任务失败时启用 MQTT DEBUG 输出（用于诊断后续错误）
            print(f"[任务] ❌ 执行异常: {e}")
            print(f"[DEBUG] 已自动启用 MQTT 服务响应调试 - 后续任务将打印详细 JSON")
            uav_client['mqtt'].enable_service_debug = True
        finally:
            uav_client['current_runner'] = None

    thread = threading.Thread(target=task_wrapper, daemon=True)
    thread.start()


# ========== UWB 室内系统专用线程函数 ==========


def uwb_position_reporter(
    uwb_position: 'UWBPosition',  # 改用 UWBPosition 对象（类型安全）
    ivas_client,
    device_code: int,
    callsign: str,
    transform_config: Dict[str, float],
    interval: float,
    stop_event: threading.Event,
    use_uwb_altitude: bool = False,
    fixed_altitude_base: float = 1.0,
    fixed_altitude_range: float = 0.05,
    default_heading: int = 0,
    default_motion: int = 1,
    user_name: str = "indoor",
    print_duration: float = 5.0
):
    """
    UWB 位置上报线程（室内系统专用）

    从 UWBPosition 对象读取位置，应用坐标变换后上报到 IVAS。

    Args:
        uwb_position: UWBPosition 对象（内置线程安全）
        ivas_client: IVAS HTTP 客户端
        device_code: 设备编号
        callsign: 呼号
        transform_config: 坐标变换配置 {'x_offset', 'y_offset', 'x_scale', 'y_scale'}
        interval: 上报间隔（秒）
        stop_event: 停止事件
        use_uwb_altitude: 是否使用 UWB 高度
        fixed_altitude_base: 固定高度基础值（米）
        fixed_altitude_range: 固定高度波动范围（米）
        default_heading: 默认航向角（度）
        default_motion: 默认运动状态
        user_name: 用户名称
        print_duration: 打印日志时长（秒）
    """
    next_tick = time.perf_counter()
    start_time = time.perf_counter()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 读取 UWB 数据（线程安全）
            x, y, z, ts = uwb_position.get()

            # 检查数据有效性
            if not uwb_position.is_valid():
                next_tick += interval
                continue

            # 应用坐标变换（平移 + 缩放）
            lat = (x + transform_config['x_offset']) * transform_config['x_scale']
            lon = (y + transform_config['y_offset']) * transform_config['y_scale']

            # 高度处理
            if use_uwb_altitude:
                alt = z
            else:
                # 固定高度 + 随机波动
                alt = fixed_altitude_base + random.uniform(-fixed_altitude_range, fixed_altitude_range)

            # 上报位置
            success = ivas_client.report_position(
                device_code=device_code,
                lat=lat,
                lon=lon,
                alt=alt,
                azimuth=default_heading,
                motion=default_motion,
                user_name=user_name
            )

            # 打印日志（前 N 秒）
            elapsed = current - start_time
            if success and elapsed <= print_duration:
                print(
                    f"[上报] [{callsign}] UWB 位置 | "
                    f"x(lat):{lat:.4f} y(lon):{lon:.4f} z(alt):{alt:.4f}m | "
                    f"heading:{default_heading}° motion:{default_motion}"
                )

            next_tick += interval

        time.sleep(0.001)


def uwb_trigger_target_reporter(
    uwb_position: 'UWBPosition',  # 改用 UWBPosition 对象（类型安全）
    ivas_client,
    transform_config: Dict[str, float],
    trigger_areas: Dict[int, Dict[str, float]],
    target_configs: Dict[int, Dict[str, Any]],
    interval: float,
    stop_event: threading.Event,
    print_duration: float = 5.0
):
    """
    UWB 触发区域目标上报线程（室内系统专用）

    根据无人机进入的触发区域，永久激活对应目标并持续上报。

    特性：
    - 永久激活：进入区域后即使离开也持续上报
    - 多目标累积：可同时上报多个已激活目标
    - 坐标变换：使用与位置上报相同的坐标变换

    Args:
        uwb_position: UWBPosition 对象（内置线程安全）
        ivas_client: IVAS HTTP 客户端
        transform_config: 坐标变换配置 {'x_offset', 'y_offset', 'x_scale', 'y_scale'}
        trigger_areas: 触发区域配置 {target_id: {'x_min', 'x_max', 'y_min', 'y_max'}}
        target_configs: 目标配置 {target_id: {'id', 'cls', 'gis'}}
        interval: 上报间隔（秒）
        stop_event: 停止事件
        print_duration: 打印日志时长（秒）
    """
    next_tick = time.perf_counter()
    start_time = time.perf_counter()

    # 永久激活状态跟踪
    activated_targets = set()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 读取 UWB 数据（线程安全）
            raw_x, raw_y, _, _ = uwb_position.get()

            # 检查数据有效性
            if not uwb_position.is_valid():
                next_tick += interval
                continue

            # 应用坐标变换
            transformed_lat = (raw_x + transform_config['x_offset']) * transform_config['x_scale']
            transformed_lon = (raw_y + transform_config['y_offset']) * transform_config['y_scale']

            # 检查各个触发区域
            for target_id, area in trigger_areas.items():
                if (area['x_min'] <= transformed_lat <= area['x_max'] and
                    area['y_min'] <= transformed_lon <= area['y_max']):
                    if target_id not in activated_targets:
                        activated_targets.add(target_id)
                        print(f"[目标触发] 目标{target_id}已激活 (区域: x=[{area['x_min']},{area['x_max']}], y=[{area['y_min']},{area['y_max']}])")

            # 构建所有已激活的目标列表
            active_targets = []
            for target_id in activated_targets:
                if target_id in target_configs:
                    target = target_configs[target_id].copy()
                    target['bbox'] = [100, 100, 50, 50]
                    target['obj_img'] = f"http://example.com/target_{target['id']}.jpg"
                    active_targets.append(target)

            # 上报目标
            if active_targets:
                timestamp = int(time.time())
                success = ivas_client.report_targets(timestamp=timestamp, objs=active_targets)

                # 打印日志（前 N 秒）
                elapsed = current - start_time
                if success and elapsed <= print_duration:
                    target_ids = [t['id'] for t in active_targets]
                    print(
                        f"[上报] UAV原始:({raw_x:.2f},{raw_y:.2f}) "
                        f"变换后:({transformed_lat:.2f},{transformed_lon:.2f}) | "
                        f"上报 {len(active_targets)} 个目标 (ID: {target_ids})"
                    )

            next_tick += interval

        time.sleep(0.001)


def task_mqtt_forwarder(
    ivas_client,
    mqtt_client,
    publish_topic: str,
    mission_filter: int,
    interval: float,
    stop_event: threading.Event
):
    """
    任务轮询与 MQTT 转发线程（室内系统专用）

    轮询 IVAS 任务，并将特定 mission 类型转发到 MQTT 主题。

    Args:
        ivas_client: IVAS HTTP 客户端
        mqtt_client: Paho MQTT 客户端
        publish_topic: MQTT 发布主题
        mission_filter: 需要转发的 mission 类型（例如 1 表示起飞）
        interval: 轮询间隔（秒）
        stop_event: 停止事件
    """
    import json
    import paho.mqtt.client as mqtt

    next_tick = time.perf_counter()
    task_count = 0

    # 任务字典映射
    mission_names = {
        1: "任务开始 - 原地起飞",
        2: "原地降落",
        3: "返航",
        4: "前往指定点",
        5: "执行预设多航点任务1",
        6: "执行预设多航点任务2",
        7: "执行预设多航点任务3"
    }

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 轮询任务
            result = ivas_client.poll_task()

            if result:
                task_count += 1
                task_data = result.get('data', {})
                mission = task_data.get('mission', 0)
                target_id = task_data.get('id', 0)
                mission_name = mission_names.get(mission, f"未知任务({mission})")

                # 打印日志信息
                print("\n" + "="*60)
                print(f"[任务] 🎯 接收到任务 #{task_count} (时间: {time.strftime('%H:%M:%S')})")
                print(f"[任务] 类型: mission={mission} ({mission_name})")
                print(f"[任务] 目标: ID={target_id}")
                print("="*60)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("="*60)

                # 判断是否需要转发到 MQTT
                should_publish = (mission == mission_filter)

                if should_publish:
                    # 转发到 MQTT
                    try:
                        task_message = {
                            'task_id': task_count,
                            'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'timestamp': int(time.time()),
                            'mission_type': mission,
                            'mission_name': mission_name,
                            'data': result
                        }

                        payload = json.dumps(task_message, ensure_ascii=False)
                        mqtt_result = mqtt_client.publish(publish_topic, payload, qos=1)

                        if mqtt_result.rc == mqtt.MQTT_ERR_SUCCESS:
                            print(f"[任务] ✓ 已转发到 MQTT (topic: {publish_topic})")
                        else:
                            print(f"[任务] ✗ MQTT 转发失败 (rc={mqtt_result.rc})")

                    except Exception as e:
                        print(f"[任务] ✗ MQTT 转发异常: {e}")
                else:
                    # 不转发
                    print(f"[任务] ⚠️  仅打印模式（mission={mission} 不转发 MQTT）")

                print("="*60 + "\n")

            next_tick += interval

        time.sleep(0.001)

