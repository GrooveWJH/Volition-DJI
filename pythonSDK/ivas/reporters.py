"""
IVAS 上报线程模块 - 数据上报功能

包含户外和室内系统的所有上报线程：
- 户外系统：位置上报、目标上报、spuriou目标上报
- 室内系统：UWB位置上报、触发区域目标上报

所有函数都是纯函数，使用 perf_counter 精确定时。
"""

import time
import threading
import random
from typing import Dict, Any, TYPE_CHECKING

# 类型导入（仅用于静态类型检查，避免运行时循环导入）
if TYPE_CHECKING:
    from .data_models import UWBPosition


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
                    'gis': [target_lat, target_lon, target_alt],  # 纬度在前，经度在后
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
    spuriou目标上报线程（跟随无人机GPS位置）

    从 MQTTClient 获取真实GPS位置，在其周围10m范围内生成 spuriou目标。

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
    last_waypoint_index = None  # 跟踪航点索引，支持快速连续到达
    waypoint_arrival_time = None

    # 上报间隔
    interval = 1.0 / config['report_hz']

    # 启动提示（可选）
    if config.get('enable_debug_log', False):
        id_range = f"{base_id}~{base_id + max_targets - 1}"
        print(f"[spuriou目标] [{callsign}] 启动 - ID 池: {id_range}, 频率: {config['report_hz']}Hz, 窗口模式: {'开启' if config.get('report_after_waypoint') else '关闭'}")

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 1. 航点到达检测（如果启用窗口模式）
            if config.get('report_after_waypoint', False):
                progress = mqtt_client.get_flyto_progress()
                current_status = progress.get('status')
                current_waypoint_index = progress.get('way_point_index')

                # 检测到新到达航点（状态变化 OR 航点索引变化）
                # 修复：支持快速连续到达航点（间隔 < 20s）
                if current_status == 'wayline_ok' and (
                    last_flyto_status != 'wayline_ok' or
                    (current_waypoint_index is not None and
                     current_waypoint_index != last_waypoint_index)
                ):
                    waypoint_arrival_time = current
                    if config.get('enable_debug_log', False):
                        way_point_index = progress.get('way_point_index', '?')
                        print(f"[spuriou目标] [{callsign}] 🎯 航点{way_point_index}到达，开始 {config.get('report_duration', 20.0)}s 上报窗口")
                    last_waypoint_index = current_waypoint_index  # 更新航点索引

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
                            print(f"[spuriou目标] [{callsign}] ⏸️  上报窗口结束，等待下一个航点...")
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

            # 4. 生成 spuriou目标
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
                'gis': [target_lat, target_lon, target_alt],  # 纬度在前，经度在后
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
                print(f"[spuriou目标] [{callsign}] {gps_status} | 基准GPS:({lat:.6f}, {lon:.6f}) | {target_info}")

            # 7. 循环更新索引（0 → 1 → ... → 9 → 0）
            current_index = (current_index + 1) % max_targets

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


# ========== UWB 室内系统专用上报线程 ==========


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
    detection_event: threading.Event,  # 检测事件（用于激活上报）
    reset_targets_event: threading.Event,  # 重置事件（用于清空已激活目标）
    stop_event: threading.Event,
    print_duration: float = 5.0
):
    """
    UWB 触发区域目标上报线程（室内系统专用）

    根据无人机进入的触发区域 + 收到检测消息，永久激活对应目标并持续上报。

    特性：
    - 双重激活条件：进入触发区域 + 收到检测消息
    - 永久激活：一旦激活即持续上报（即使离开区域）
    - 多目标累积：可同时上报多个已激活目标
    - 手动重置：支持通过 reset_targets_event 清空所有已激活目标
    - 坐标变换：使用与位置上报相同的坐标变换

    Args:
        uwb_position: UWBPosition 对象（内置线程安全）
        ivas_client: IVAS HTTP 客户端
        transform_config: 坐标变换配置 {'x_offset', 'y_offset', 'x_scale', 'y_scale'}
        trigger_areas: 触发区域配置 {target_id: {'x_min', 'x_max', 'y_min', 'y_max'}}
        target_configs: 目标配置 {target_id: {'id', 'cls', 'gis'}}
        interval: 上报间隔（秒）
        detection_event: 检测事件（收到 MQTT 检测消息时触发）
        reset_targets_event: 重置事件（收到重置信号时清空已激活目标）
        stop_event: 停止事件
        print_duration: 打印日志时长（秒）
    """
    next_tick = time.perf_counter()
    start_time = time.perf_counter()

    # 永久激活状态跟踪
    activated_targets = set()

    while not stop_event.is_set():
        current = time.perf_counter()

        # 检查重置事件
        if reset_targets_event.is_set():
            if activated_targets:
                print(f"[重置] 清空 {len(activated_targets)} 个已激活目标: {activated_targets}")
                activated_targets.clear()
            reset_targets_event.clear()

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

            # 1. 检测当前在哪些触发区域内
            current_areas = set()
            for target_id, area in trigger_areas.items():
                if (area['x_min'] <= transformed_lat <= area['x_max'] and
                    area['y_min'] <= transformed_lon <= area['y_max']):
                    current_areas.add(target_id)

            # 2. 如果收到检测消息，激活当前区域的所有目标
            if detection_event.is_set():
                for target_id in current_areas:
                    if target_id not in activated_targets:
                        activated_targets.add(target_id)
                        print(f"[检测确认] 检测消息 + 触发区域 → 激活目标{target_id}")
                detection_event.clear()  # 清除标志

            # 3. 构建所有已激活的目标列表
            active_targets = []
            for target_id in activated_targets:
                if target_id in target_configs:
                    target = target_configs[target_id].copy()
                    target['bbox'] = [100, 100, 50, 50]
                    target['obj_img'] = f"http://example.com/target_{target['id']}.jpg"
                    active_targets.append(target)

            # 4. 上报目标（只有列表非空才上报）
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
