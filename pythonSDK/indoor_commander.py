#!/usr/bin/env python3
"""
室内指挥端程序

功能：
1. 订阅 UWB MQTT 主题（uwb/position）
2. 上报位置到 IVAS
3. 轮询 IVAS 任务
4. 转发 mission=1 任务到 MQTT（ivas/task/command）

使用方法：
    python indoor_commander.py
"""

import json
import time
import random
import threading
from rich.console import Console

import paho.mqtt.client as mqtt
from ivas import IVASClient

# 加载配置
from dashboard.config import UAV_CONFIGS, IVAS_SERVER

console = Console()

# ========== 配置段 ==========

# IVAS 功能开关
ENABLE_IVAS = True  # False 为 Dry-run 模式（仅打印，不连接 IVAS）

# MQTT 配置
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# UWB 订阅配置
UWB_SUBSCRIBE_TOPIC = 'uwb/position'    # UWB 主题订阅主题

# 任务发布配置
TASK_PUBLISH_TOPIC = 'ivas/task/command'  # 任务转发主题

# IVAS 配置
IVAS_REPORT_HZ = 1.0        # 位置上报频率（Hz）
IVAS_TASK_HZ = 2.0          # 任务轮询频率（Hz）
POSITION_LOG_DURATION = 5.0 # 位置上报日志打印时长（秒）

# 假目标上报配置
ENABLE_FAKE_TARGETS = True  # 是否启用假目标上报
FAKE_TARGET_HZ = 2.0        # 假目标上报频率（Hz）
FAKE_TARGET_LOG_DURATION = 5.0  # 假目标上报日志打印时长（秒）

# 假目标触发区域（基于无人机 UWB 位置）
# 目标1触发区域：矩形对角顶点 (x_a, y_a) - (x_b, y_b)
TARGET1_TRIGGER_AREA = {
    'x_min': -5.0,  # x_a
    'y_min': -5.0,  # y_a
    'x_max': 5.0,   # x_b
    'y_max': 5.0    # y_b
}

# 目标2触发区域：矩形对角顶点 (x_c, y_c) - (x_d, y_d)
TARGET2_TRIGGER_AREA = {
    'x_min': -10.0,  # x_c
    'y_min': -10.0,  # y_c
    'x_max': 10.0,   # x_d
    'y_max': 10.0    # y_d
}

# UWB 坐标系转换超参数
UWB_TRANSFORM = {
    'x_offset': -3.13,    # x 平移（米）
    'y_offset': +0.04,    # y 平移（米）
    'x_scale': 0.90,     # x 缩放
    'y_scale': 1.0,     # y 缩放
}

# 高度控制配置
USE_UWB_ALTITUDE = False         # 是否使用 UWB 高度（False 则使用固定高度）
FIXED_ALTITUDE_BASE = 1.3       # 固定高度基础值（米）
FIXED_ALTITUDE_RANGE = 0.05      # 固定高度波动范围（米，±range）

# 使用配置（这里使用 IVAS 第一台设备的 device_code）
UAV_CONFIG = UAV_CONFIGS[0]
DEVICE_CODE = UAV_CONFIG['ivas']['device_code']
CALLSIGN = UAV_CONFIG['callsign']

# 固定参数（无人机数据）：
DEFAULT_HEADING = 0         # 默认航向（度）
DEFAULT_MOTION = 1          # 默认运动状态（0:静止, 1:运动）

# MQTT 客户端 ID
CLIENT_ID = f'commander-{int(time.time())}'

# ========== UWB 主题数据缓存 ==========

uwb_data = {
    'x': None,
    'y': None,
    'z': None,
    'timestamp': None
}
uwb_lock = threading.Lock()


def on_connect(client, userdata, flags, rc):
    """连接回调"""
    if rc == 0:
        console.print(f"[green]✓ 已连接到 MQTT Broker[/green]")
        # 订阅 UWB 主题
        client.subscribe(UWB_SUBSCRIBE_TOPIC, qos=0)
        console.print(f"[green]✓ 已订阅 UWB 主题: {UWB_SUBSCRIBE_TOPIC}[/green]")
    else:
        console.print(f"[red]✗ 连接失败，错误码: {rc}[/red]")


def on_uwb_message(client, userdata, msg):
    """UWB MQTT 消息回调"""
    global uwb_data
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        pos = payload['position']

        with uwb_lock:
            uwb_data['x'] = pos['x']
            uwb_data['y'] = pos['y']
            uwb_data['z'] = pos['z']
            uwb_data['timestamp'] = payload['timestamp']
    except Exception as e:
        print(f"[UWB] 主题解析失败: {e}")


# ========== 辅助函数 ==========

def build_report_url(device_code: int, lat: float, lon: float, alt: float,
                     azimuth: int, motion: int, user_name: str) -> str:
    """
    构建 IVAS 位置上报的完整 URL（用于调试）

    Args:
        device_code: 设备编号
        lat: 纬度
        lon: 经度
        alt: 高度（米）
        azimuth: 航向角（度）
        motion: 运动状态（0:静止, 1:运动）
        user_name: 用户名称

    Returns:
        完整的 HTTP GET 请求 URL（带所有参数）
    """
    base_url = IVAS_SERVER['base_url']
    ivas_user_info_id = UAV_CONFIG['ivas']['account']
    room_id = 22
    local_time = int(time.time() * 1000)

    return (
        f"{base_url}/jk-ivas/third/controller/reportUserData?"
        f"ivasUserInfoId={ivas_user_info_id}&"
        f"deviceCode={device_code}&"
        f"userX={lat:.6f}&"
        f"userY={lon:.6f}&"
        f"userZ={alt:.4f}&"
        f"azimuth={azimuth}&"
        f"localTime={local_time}&"
        f"motion={motion}&"
        f"validCount=10&"
        f"roomId={room_id}&"
        f"refPositionType=0&"
        f"userName={user_name}"
    )


# ========== Dry-Run 模拟器 ==========

class DryRunReporter:
    """
    Dry-run 模式：模拟 IVAS 客户端接口

    用途：在无 IVAS 服务器环境下调试 UWB 数据流和坐标转换逻辑
    - report_position(): 打印到控制台而不实际上报
    - report_targets(): 打印假目标数据
    - poll_task(): 返回 None（不轮询任务）
    """

    def report_position(self, device_code, lat, lon, alt, azimuth, motion, user_name):
        """打印位置数据（模拟上报）"""
        report_url = build_report_url(device_code, lat, lon, alt, azimuth, motion, user_name)

        print(
            f"[DRY-RUN] 上报位置 | "
            f"device={device_code} user={user_name} | "
            f"lat={lat:.6f} lon={lon:.6f} alt={alt:.4f}m | "
            f"heading={azimuth}° motion={motion}"
        )
        print(f"[URL] {report_url}")
        print()  # 空行分隔
        return True  # 模拟成功

    def report_targets(self, timestamp: int, objs: list) -> bool:
        """打印假目标数据（模拟上报）"""
        print(f"[DRY-RUN] 上报假目标 | timestamp={timestamp} | 目标数={len(objs)}")
        for obj in objs:
            print(f"  - ID:{obj['id']} 类别:{obj['cls']} 位置:{obj['gis']}")
        print()  # 空行分隔
        return True  # 模拟成功

    def poll_task(self):
        """Dry-run 模式下不轮询任务"""
        return None


# ========== 主函数 ==========

def uwb_position_reporter(
    ivas_client,
    device_code: int,
    callsign: str,
    interval: float,
    stop_event: threading.Event,
    print_duration: float = 5.0
):
    """
    UWB 位置上报线程

    读取 UWB 缓存数据，将 xy转换为 lat/lon 上报到 IVAS。
    """
    next_tick = time.perf_counter()
    start_time = time.perf_counter()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 读取 UWB 主题数据（缓存）
            with uwb_lock:
                x = uwb_data['x']
                y = uwb_data['y']
                z = uwb_data['z']

            # 检查数据有效性
            if x is None or y is None or z is None:
                next_tick += interval
                continue

            # 应用超参数（平移 + 缩放）
            lat = (x + UWB_TRANSFORM['x_offset']) * UWB_TRANSFORM['x_scale']
            lon = (y + UWB_TRANSFORM['y_offset']) * UWB_TRANSFORM['y_scale']

            # 高度处理：根据配置选择 UWB 高度或固定高度
            if USE_UWB_ALTITUDE:
                alt = z
            else:
                # 固定高度 + 随机波动
                alt = FIXED_ALTITUDE_BASE + random.uniform(-FIXED_ALTITUDE_RANGE, FIXED_ALTITUDE_RANGE)

            # 使用固参数
            heading = DEFAULT_HEADING
            motion = DEFAULT_MOTION

            # 上报位置到 IVAS
            success = ivas_client.report_position(
                device_code=device_code,
                lat=lat,
                lon=lon,
                alt=alt,
                azimuth=heading,
                motion=motion,
                # user_name=callsign
                user_name="indoor"
            )

            # 打印日志（前 N 秒）
            elapsed = current - start_time
            if success and elapsed <= print_duration:
                report_url = build_report_url(device_code, lat, lon, alt, heading, motion, "indoor")

                print(
                    f"[上报] [{callsign}] UWB 位置 | "
                    f"x(lat):{lat:.4f} y(lon):{lon:.4f} z(alt):{alt:.4f}m | "
                    f"heading:{heading}° motion:{motion}"
                )
                print(f"[URL] {report_url}")
                print()  # 空行分隔

            next_tick += interval

        time.sleep(0.001)


def fixed_target_reporter(
    ivas_client,
    interval: float,
    stop_event: threading.Event,
    print_duration: float = 5.0
):
    """
    固定假目标上报线程（基于无人机位置触发）

    根据无人机当前 UWB 位置动态上报假目标：
    - 目标1：仅在 TARGET1_TRIGGER_AREA 矩形范围内触发
    - 目标2：仅在 TARGET2_TRIGGER_AREA 矩形范围内触发

    Args:
        ivas_client: IVAS HTTP 客户端
        interval: 上报间隔（秒）
        stop_event: 停止事件
        print_duration: 日志打印时长（秒）
    """
    next_tick = time.perf_counter()
    start_time = time.perf_counter()

    # 目标配置（固定位置）
    target1_config = {'id': 1, 'cls': 0, 'gis': [-168, 170, 10000]}
    target2_config = {'id': 2, 'cls': 0, 'gis': [-237, 1703, 10000]}

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 读取无人机当前 UWB 位置（使用共享数据）
            with uwb_lock:
                uav_x = uwb_data['x']
                uav_y = uwb_data['y']

            # 检查 UWB 数据有效性
            if uav_x is None or uav_y is None:
                next_tick += interval
                continue

            # 动态构建上报目标列表（基于触发区域）
            active_targets = []

            # 检查目标1触发条件
            area1 = TARGET1_TRIGGER_AREA
            if (area1['x_min'] <= uav_x <= area1['x_max'] and
                area1['y_min'] <= uav_y <= area1['y_max']):
                target1 = target1_config.copy()
                target1['bbox'] = [100, 100, 50, 50]
                target1['obj_img'] = f"http://example.com/target_{target1['id']}.jpg"
                active_targets.append(target1)

            # 检查目标2触发条件
            area2 = TARGET2_TRIGGER_AREA
            if (area2['x_min'] <= uav_x <= area2['x_max'] and
                area2['y_min'] <= uav_y <= area2['y_max']):
                target2 = target2_config.copy()
                target2['bbox'] = [100, 100, 50, 50]
                target2['obj_img'] = f"http://example.com/target_{target2['id']}.jpg"
                active_targets.append(target2)

            # 仅在有激活目标时上报
            if active_targets:
                timestamp = int(time.time())
                success = ivas_client.report_targets(timestamp=timestamp, objs=active_targets)

                # 打印日志（前 N 秒）
                elapsed = current - start_time
                if success and elapsed <= print_duration:
                    target_ids = [t['id'] for t in active_targets]
                    print(
                        f"[假目标] UAV位置:({uav_x:.2f},{uav_y:.2f}) | "
                        f"上报 {len(active_targets)} 个目标 (ID: {target_ids})"
                    )

            next_tick += interval

        time.sleep(0.001)


def task_poller_and_publisher(
    ivas_client,
    mqtt_client,
    interval: float,
    stop_event: threading.Event
):
    """
    任务轮询与发布线程

    轮询 mission=1（起飞）任务，转发到 MQTT。
    """
    next_tick = time.perf_counter()
    task_count = 0

    # 任务字典 映射
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
                should_publish = (mission == 1)

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
                        mqtt_result = mqtt_client.publish(TASK_PUBLISH_TOPIC, payload, qos=1)

                        if mqtt_result.rc == mqtt.MQTT_ERR_SUCCESS:
                            print(f"[任务] ✓ 已转发到 MQTT (topic: {TASK_PUBLISH_TOPIC})")
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


# ========== 主程序 ==========

def main():
    """主函数"""
    console.print("\n[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]")
    console.print("[bold bright_cyan]       室内指挥端程序[/bold bright_cyan]")
    console.print("[bold bright_cyan]       UWB 订阅 + IVAS 交互 + 任务转发[/bold bright_cyan]")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    # 打印配置信息
    console.print(f"[bold]📋 配置信息[/bold]")
    console.print(f"  呼号: {CALLSIGN} (device_code={DEVICE_CODE})")

    # IVAS 模式状态
    if ENABLE_IVAS:
        console.print(f"  IVAS 模式: [green]已启用[/green] ({IVAS_SERVER['base_url']})")
    else:
        console.print(f"  IVAS 模式: [yellow]Dry-run（仅打印，不连接服务器）[/yellow]")

    console.print(f"  UWB 订阅主题: {UWB_SUBSCRIBE_TOPIC}")
    console.print(f"  任务转发主题: {TASK_PUBLISH_TOPIC}")
    console.print(f"  位置上报频率: {IVAS_REPORT_HZ} Hz")
    console.print(f"  任务轮询频率: {IVAS_TASK_HZ} Hz")

    # 假目标配置状态
    if ENABLE_FAKE_TARGETS:
        console.print(f"  假目标上报: [green]已启用[/green] (频率: {FAKE_TARGET_HZ}Hz, 目标数: 2)")
    else:
        console.print(f"  假目标上报: [yellow]已禁用[/yellow]")

    # 高度配置状态
    if USE_UWB_ALTITUDE:
        console.print(f"  高度来源: [cyan]UWB 实时高度[/cyan]")
    else:
        console.print(f"  高度来源: [yellow]固定高度 {FIXED_ALTITUDE_BASE:.2f}m (±{FIXED_ALTITUDE_RANGE:.2f}m)[/yellow]")

    console.print()

    # 1. 初始化 IVAS（或 Dry-run 模式）
    console.print("[bold]📡 步骤 1: 初始化 IVAS[/bold]")

    if ENABLE_IVAS:
        # 真实 IVAS 连接
        ivas_config = UAV_CONFIG['ivas']
        ivas_client = IVASClient(
            base_url=IVAS_SERVER['base_url'],
            account=ivas_config['account'],
            password=ivas_config['password']
        )

        if not ivas_client.login():
            console.print(f"[red]✗ IVAS 初始化失败 (账户: {ivas_config['account']})[/red]")
            return

        console.print(f"[bright_green]✓ IVAS 客户端初始化 (账户: {ivas_config['account']})[/bright_green]")
    else:
        # Dry-run 模式
        ivas_client = DryRunReporter()
        console.print(f"[yellow]⚠️  Dry-run 模式已启用（不连接 IVAS 服务器）[/yellow]")

    console.print()

    # 2. 连接 MQTT
    console.print("[bold]🔌 步骤 2: 连接 MQTT Broker[/bold]")
    mqtt_client = mqtt.Client(client_id=CLIENT_ID)
    mqtt_client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_uwb_message

    try:
        mqtt_client.connect(MQTT_CONFIG['host'], MQTT_CONFIG['port'], 60)
    except Exception as e:
        console.print(f"[red]✗ MQTT 连接失败: {e}[/red]")
        return

    mqtt_client.loop_start()
    time.sleep(0.5)
    console.print()

    # 3. 启动位置上报线程
    console.print("[bold]📍 步骤 3: 启动位置上报线程[/bold]")
    position_stop_event = threading.Event()
    position_thread = threading.Thread(
        target=uwb_position_reporter,
        args=(
            ivas_client,
            DEVICE_CODE,
            CALLSIGN,
            1.0 / IVAS_REPORT_HZ,
            position_stop_event,
            POSITION_LOG_DURATION
        ),
        daemon=True,
        name=f"uwb-position-{DEVICE_CODE}"
    )
    position_thread.start()
    console.print(f"[bright_green]✓ 位置上报线程已启动[/bright_green]")
    console.print()

    # 4. 启动假目标上报线程（可选）
    fake_target_thread = None
    if ENABLE_FAKE_TARGETS:
        console.print("[bold]🎯 步骤 4: 启动假目标上报线程[/bold]")
        fake_target_stop_event = threading.Event()
        fake_target_thread = threading.Thread(
            target=fixed_target_reporter,
            args=(
                ivas_client,
                1.0 / FAKE_TARGET_HZ,
                fake_target_stop_event,
                FAKE_TARGET_LOG_DURATION
            ),
            daemon=True,
            name="fake-target-reporter"
        )
        fake_target_thread.start()
        console.print(f"[bright_green]✓ 假目标上报线程已启动 (频率: {FAKE_TARGET_HZ}Hz)[/bright_green]")
        console.print()

    # 5. 启动任务轮询与发布线程
    console.print("[bold]🎯 步骤 5: 启动任务轮询与发布线程[/bold]")
    task_stop_event = threading.Event()
    task_thread = threading.Thread(
        target=task_poller_and_publisher,
        args=(
            ivas_client,
            mqtt_client,
            1.0 / IVAS_TASK_HZ,
            task_stop_event
        ),
        daemon=True,
        name="task-poller"
    )
    task_thread.start()
    console.print(f"[bright_green]✓ 任务轮询线程已启动（转发主题 {TASK_PUBLISH_TOPIC}）[/bright_green]")
    console.print()

    # 6. 主循环
    console.print("[bold green]✅ 系统就绪！正在监听 UWB 主题和 IVAS 任务...[/bold green]")
    console.print("[dim]按 Ctrl+C 退出[/dim]\n")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  接收到中断信号，正在退出...[/yellow]")

    finally:
        console.print("\n[bold]🧹 清理资源...[/bold]")

        # 停止位置上报线程
        console.print("[bright_cyan]停止位置上报线程...[/bright_cyan]")
        position_stop_event.set()
        position_thread.join(timeout=2.0)
        console.print(f"[bright_green]✓ 位置上报线程已停止[/bright_green]")

        # 停止假目标上报线程（如果存在）
        if fake_target_thread is not None:
            console.print("[bright_cyan]停止假目标上报线程...[/bright_cyan]")
            fake_target_stop_event.set()
            fake_target_thread.join(timeout=2.0)
            console.print(f"[bright_green]✓ 假目标上报线程已停止[/bright_green]")

        # 停止任务轮询线程
        console.print("[bright_cyan]停止任务轮询线程...[/bright_cyan]")
        task_stop_event.set()
        task_thread.join(timeout=2.0)
        console.print("[bright_green]✓ 任务轮询线程已停止[/bright_green]")

        # 停止 MQTT
        console.print("[bright_cyan]停止 MQTT...[/bright_cyan]")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        console.print("[bright_green]✓ MQTT 已断开[/bright_green]")

        console.print("[bold green]✅ 程序已退出[/bold green]\n")


if __name__ == '__main__':
    main()
