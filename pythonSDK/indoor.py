#!/usr/bin/env python3
"""
室内 IVAS 程序（极简版）

专注于：
1. UWB 位置上报（替代 GPS，直接用 xy 作为 lat/lon）
2. 任务轮询（仅打印，不执行）

不需要：
- ❌ 无人机连接（不控制无人机）
- ❌ DRC 模式
- ❌ 任务执行

使用方法：
    python indoor.py
"""

import json
import time
import threading
from rich.console import Console

import paho.mqtt.client as mqtt
from ivas import IVASClient

# 导入配置
from dashboard.config import UAV_CONFIGS, IVAS_SERVER

console = Console()

# ========== 配置段 ==========

# UWB MQTT 配置（与 uwb2mqtt.py 相同）
UWB_MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605',
    'topic': 'uwb/position',
    'client_id': f'indoor-uwb-{int(time.time())}'
}

# UWB 坐标处理超参数（xy 平移和缩放）
UWB_TRANSFORM = {
    'x_offset': 0.0,    # x 平移（米）
    'y_offset': 0.0,    # y 平移（米）
    'x_scale': 1.0,     # x 缩放
    'y_scale': 1.0,     # y 缩放
}

# IVAS 配置
IVAS_REPORT_HZ = 1.0        # 位置上报频率（Hz）
IVAS_TASK_HZ = 2.0          # 任务轮询频率（Hz）
POSITION_LOG_DURATION = 5.0 # 位置上报日志打印时长（秒）

# 一号机配置（只用于 IVAS 账号和 device_code）
UAV_CONFIG = UAV_CONFIGS[0]
DEVICE_CODE = UAV_CONFIG['ivas']['device_code']
CALLSIGN = UAV_CONFIG['callsign']

# 固定参数（不依赖无人机）
DEFAULT_HEADING = 0         # 固定航向角（度）
DEFAULT_MOTION = 0          # 固定运动状态（0:静止, 1:移动）

# ========== UWB 数据管理（线程安全）==========

uwb_data = {
    'x': None,
    'y': None,
    'z': None,
    'timestamp': None
}
uwb_lock = threading.Lock()


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
        print(f"[UWB] 数据解析失败: {e}")


def setup_uwb_mqtt():
    """
    启动 UWB MQTT 订阅

    Returns:
        mqtt.Client: UWB MQTT 客户端
    """
    console.print(f"[bold cyan]📡 连接 UWB MQTT: {UWB_MQTT_CONFIG['host']}...[/bold cyan]")

    client = mqtt.Client(client_id=UWB_MQTT_CONFIG['client_id'])
    client.username_pw_set(UWB_MQTT_CONFIG['username'], UWB_MQTT_CONFIG['password'])
    client.on_message = on_uwb_message

    try:
        client.connect(UWB_MQTT_CONFIG['host'], UWB_MQTT_CONFIG['port'], 60)
        client.subscribe(UWB_MQTT_CONFIG['topic'], qos=0)
        client.loop_start()
        console.print(f"[bright_green]✓ UWB MQTT 已连接，订阅主题: {UWB_MQTT_CONFIG['topic']}[/bright_green]")
        return client
    except Exception as e:
        console.print(f"[bright_red]✗ UWB MQTT 连接失败: {e}[/bright_red]")
        return None


# ========== 线程函数 ==========

def uwb_position_reporter(
    ivas_client,
    device_code: int,
    callsign: str,
    interval: float,
    stop_event: threading.Event,
    print_duration: float = 5.0
):
    """
    UWB 位置上报线程（不依赖无人机）

    从 UWB 全局变量获取 xy，直接作为 lat/lon 上报到 IVAS。

    Args:
        ivas_client: IVAS HTTP 客户端
        device_code: 设备编号
        callsign: 设备呼号
        interval: 上报间隔（秒）
        stop_event: 停止事件
        print_duration: 打印日志的时长（秒）
    """
    next_tick = time.perf_counter()
    start_time = time.perf_counter()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 1. 读取 UWB 数据（线程安全）
            with uwb_lock:
                x = uwb_data['x']
                y = uwb_data['y']
                z = uwb_data['z']

            # 检查数据有效性
            if x is None or y is None or z is None:
                next_tick += interval
                continue

            # 2. 应用超参数（平移 + 缩放）
            lat = (x + UWB_TRANSFORM['x_offset']) * UWB_TRANSFORM['x_scale']
            lon = (y + UWB_TRANSFORM['y_offset']) * UWB_TRANSFORM['y_scale']
            alt = z

            # 3. 使用固定参数（不依赖无人机）
            heading = DEFAULT_HEADING
            motion = DEFAULT_MOTION

            # 4. 上报位置到 IVAS
            success = ivas_client.report_position(
                device_code=device_code,
                lat=lat,  # 实际是 UWB x
                lon=lon,  # 实际是 UWB y
                alt=alt,
                azimuth=heading,
                motion=motion,
                user_name=callsign
            )

            # 5. 打印日志（前 N 秒）
            elapsed = current - start_time
            if success and elapsed <= print_duration:
                print(
                    f"[上报] [{callsign}] UWB 位置 | "
                    f"x(lat):{lat:.4f} y(lon):{lon:.4f} z(alt):{alt:.4f}m | "
                    f"heading:{heading}° motion:{motion}"
                )

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


def task_poller_print_only(
    ivas_client,
    interval: float,
    stop_event: threading.Event
):
    """
    任务轮询线程（仅打印，不执行）

    Args:
        ivas_client: IVAS HTTP 客户端
        interval: 轮询间隔（秒）
        stop_event: 停止事件
    """
    next_tick = time.perf_counter()

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 轮询任务
            result = ivas_client.poll_task()

            if result:
                # 打印任务分隔符
                print("\n" + "="*60)
                print(f"[任务] 🎯 接收到新任务 (时间: {time.strftime('%H:%M:%S')})")
                print("[任务] ⚠️  仅打印模式，不执行任务")
                print("="*60)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("="*60 + "\n")

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


# ========== 主程序 ==========

def main():
    """主函数"""
    console.print("\n[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]")
    console.print("[bold bright_cyan]       室内 IVAS 程序（UWB 位置上报）[/bold bright_cyan]")
    console.print("[bold bright_cyan]       无需连接无人机[/bold bright_cyan]")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    # 打印配置信息
    console.print(f"[bold]📋 配置信息[/bold]")
    console.print(f"  设备: {CALLSIGN} (device_code={DEVICE_CODE})")
    console.print(f"  IVAS 服务器: {IVAS_SERVER['base_url']}")
    console.print(f"  UWB 主题: {UWB_MQTT_CONFIG['topic']}")
    console.print(f"  位置上报频率: {IVAS_REPORT_HZ} Hz")
    console.print(f"  任务轮询频率: {IVAS_TASK_HZ} Hz")
    console.print(f"  坐标变换: x_offset={UWB_TRANSFORM['x_offset']}, y_offset={UWB_TRANSFORM['y_offset']}, "
                  f"x_scale={UWB_TRANSFORM['x_scale']}, y_scale={UWB_TRANSFORM['y_scale']}")
    console.print()

    # 1. 登录 IVAS
    console.print("[bold]🔐 步骤 1: 登录 IVAS[/bold]")
    ivas_config = UAV_CONFIG['ivas']
    ivas_client = IVASClient(
        base_url=IVAS_SERVER['base_url'],
        account=ivas_config['account'],
        password=ivas_config['password']
    )

    if not ivas_client.login():
        console.print(f"[red]❌ IVAS 登录失败 (账号: {ivas_config['account']})[/red]")
        return

    console.print(f"[bright_green]✓ IVAS 客户端已登录 (账号: {ivas_config['account']})[/bright_green]")
    console.print()

    # 2. 启动 UWB MQTT 订阅
    console.print("[bold]📍 步骤 2: 启动 UWB MQTT 订阅[/bold]")
    uwb_mqtt_client = setup_uwb_mqtt()

    if not uwb_mqtt_client:
        console.print("[red]❌ UWB MQTT 连接失败[/red]")
        return

    console.print()

    # 3. 启动位置上报线程
    console.print("[bold]🚀 步骤 3: 启动位置上报线程[/bold]")
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

    # 4. 启动任务轮询线程
    console.print("[bold]🎯 步骤 4: 启动任务轮询线程（仅打印）[/bold]")
    task_stop_event = threading.Event()
    task_thread = threading.Thread(
        target=task_poller_print_only,
        args=(
            ivas_client,
            1.0 / IVAS_TASK_HZ,
            task_stop_event
        ),
        daemon=True,
        name="task-poller"
    )
    task_thread.start()
    console.print(f"[bright_green]✓ 任务轮询线程已启动[/bright_green]")
    console.print()

    # 5. 运行
    console.print("[bold green]✅ 系统就绪，等待 UWB 数据和 IVAS 任务...[/bold green]")
    console.print("[dim]按 Ctrl+C 退出[/dim]\n")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    try:
        # 主线程等待
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  接收到中断信号，正在退出...[/yellow]")

    finally:
        # 6. 清理资源
        console.print("\n[bold]🧹 清理资源...[/bold]")

        # 停止位置上报线程
        console.print("[bright_cyan]停止位置上报线程...[/bright_cyan]")
        position_stop_event.set()
        position_thread.join(timeout=2.0)
        if position_thread.is_alive():
            console.print(f"[yellow]⚠️  {position_thread.name} 未在超时时间内结束[/yellow]")
        else:
            console.print(f"[bright_green]✓ {position_thread.name} 已停止[/bright_green]")

        # 停止任务轮询线程
        console.print("[bright_cyan]停止任务轮询线程...[/bright_cyan]")
        task_stop_event.set()
        task_thread.join(timeout=2.0)
        if task_thread.is_alive():
            console.print("[yellow]⚠️  任务轮询线程未在超时时间内结束[/yellow]")
        else:
            console.print("[bright_green]✓ 任务轮询线程已停止[/bright_green]")

        # 停止 UWB MQTT
        console.print("[bright_cyan]停止 UWB MQTT...[/bright_cyan]")
        uwb_mqtt_client.loop_stop()
        uwb_mqtt_client.disconnect()
        console.print("[bright_green]✓ UWB MQTT 已断开[/bright_green]")

        console.print("[bold green]✅ 程序已退出[/bold green]\n")


if __name__ == '__main__':
    main()
