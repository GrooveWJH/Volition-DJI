"""
Dashboard 监控循环模块

使用上下文管理器管理资源，消除重复的清理代码。
新增：IVAS 系统集成（位置上报、任务接收）。
"""
import os
import time
import threading
from contextlib import contextmanager
from rich.console import Console
from rich.live import Live

from djisdk import setup_multiple_drc_connections, stop_heartbeat, DRCConnectionManager
from vrpn import VRPNClient

# 导入新的 IVAS 实现
from ivas import IVASClient
from .ivas_threads import position_reporter, target_reporter, task_poller

from .config import (
    MQTT_CONFIG,
    UAV_CONFIGS,
    OSD_FREQUENCY,
    HSI_FREQUENCY,
    GUI_REFRESH_RATE,
    OFFLINE_TIMEOUT,
    ENABLE_VRPN,
    SKIP_DRC_SETUP,
    HEARTBEAT_INTERVAL,
    # IVAS 配置
    ENABLE_IVAS,
    IVAS_FEATURES,
    IVAS_SERVER,
)
from .panels import create_dashboard_layout


@contextmanager
def setup_connections(console: Console):
    """
    上下文管理器：建立所有连接并自动清理资源

    这是 Linus "好品味"设计的体现：
    - 消除了 try/finally 重复代码
    - 不需要区分 VRPN/IVAS 启用/禁用的清理逻辑
    - 资源管理完全自动化

    Args:
        console: Rich Console 实例

    Yields:
        (uav_clients, vrpn_clients, ivas_threads) 元组
    """
    uav_clients = []
    vrpn_clients = []
    conn_managers = []

    # IVAS 相关资源
    ivas_client = None
    ivas_threads = []
    ivas_stop_events = []

    try:
        # === 阶段 1: 建立 DJI 无人机连接 ===
        console.rule("[bold bright_magenta]建立多机连接[/bold bright_magenta]")

        USE_MOCK = os.getenv('USE_MOCK_DRONE', '0') == '1'

        if USE_MOCK:
            # 使用模拟器模式
            from djisdk.mock import create_mock_connections
            console.print("[bold yellow]⚠ 模拟器模式已启用（USE_MOCK_DRONE=1）[/bold yellow]")
            console.print("[dim]数据将由模拟器生成，不连接真实无人机[/dim]\n")
            connections = create_mock_connections(UAV_CONFIGS)
        else:
            # 使用真实无人机连接
            connections = setup_multiple_drc_connections(
                UAV_CONFIGS,
                MQTT_CONFIG,
                heartbeat_interval=HEARTBEAT_INTERVAL,
                osd_frequency=OSD_FREQUENCY,
                hsi_frequency=HSI_FREQUENCY,
                skip_drc_setup=SKIP_DRC_SETUP,
            )

        # 构建管理数据
        uav_clients = [
            {'id': str(i+1), 'mqtt': mqtt, 'caller': caller, 'heartbeat': heartbeat}
            for i, (mqtt, caller, heartbeat) in enumerate(connections)
        ]

        console.print(f"\n[bold bright_green]✓ 所有无人机已就绪 ({len(uav_clients)} 架)[/bold bright_green]")

        # === 阶段 1.5: 启动连接管理器（自动重连）===
        if not USE_MOCK and not SKIP_DRC_SETUP:
            # 只在真实模式且启用 DRC 时启用连接管理器
            console.rule("[bold bright_yellow]启动连接管理器[/bold bright_yellow]")
            for i, uav in enumerate(uav_clients):
                config = UAV_CONFIGS[i]
                try:
                    console.print(f"[bright_cyan]初始化连接管理器 #{i+1} ({config['callsign']})...[/bright_cyan]")

                    # 创建连接管理器
                    manager = DRCConnectionManager(
                        mqtt_client=uav['mqtt'],
                        service_caller=uav['caller'],
                        uav_config=config,
                        mqtt_config=MQTT_CONFIG,
                        osd_frequency=OSD_FREQUENCY,
                        hsi_frequency=HSI_FREQUENCY,
                        offline_timeout=OFFLINE_TIMEOUT,
                        reconnect_attempts=10,
                        reconnect_interval=1.0
                    )

                    # 启动管理器
                    manager.start(heartbeat_thread=uav['heartbeat'])

                    conn_managers.append(manager)
                    uav['connection_manager'] = manager  # 绑定到 UAV 客户端

                    console.print(f"[bright_green]✓ 连接管理器 #{i+1} 已启动[/bright_green]")
                except Exception as e:
                    console.print(f"[bright_red]✗ 连接管理器初始化失败: {e}[/bright_red]")

            if conn_managers:
                console.print(f"\n[bold bright_green]✓ 连接管理器已就绪 ({len(conn_managers)} 个)[/bold bright_green]")

        # === 阶段 2: 初始化 VRPN 客户端（如果启用）===
        if ENABLE_VRPN:
            console.rule("[bold bright_cyan]初始化 VRPN 动捕系统[/bold bright_cyan]")
            for i, config in enumerate(UAV_CONFIGS):
                vrpn_device = config.get('vrpn_device')
                if vrpn_device:
                    try:
                        console.print(f"[bright_cyan]连接 VRPN 设备: {vrpn_device}...[/bright_cyan]")
                        vrpn_client = VRPNClient(device_name=vrpn_device)
                        vrpn_clients.append({
                            'client': vrpn_client,
                            'device_name': vrpn_device.split('@')[0],
                            'uav_id': str(i+1)
                        })
                        console.print(f"[bright_green]✓ VRPN 客户端 #{i+1} 已连接[/bright_green]")
                    except Exception as e:
                        console.print(f"[bright_red]✗ VRPN 连接失败: {e}[/bright_red]")
                        vrpn_clients.append(None)
                else:
                    vrpn_clients.append(None)

            if any(vrpn_clients):
                console.print(f"\n[bold bright_green]✓ VRPN 动捕系统已就绪[/bold bright_green]")
            else:
                console.print(f"\n[bold bright_yellow]⚠ 无可用 VRPN 设备[/bold bright_yellow]")
                vrpn_clients = []  # 清空列表

        # === 阶段 3: 初始化 IVAS 系统（如果启用）===
        has_any_ivas_feature = any(IVAS_FEATURES.values())
        if ENABLE_IVAS and has_any_ivas_feature:
            console.rule("[bold bright_blue]初始化 IVAS 系统[/bold bright_blue]")

            # 获取第一个 IVAS 配置
            first_ivas_config = None
            for config in UAV_CONFIGS:
                if 'ivas' in config:
                    first_ivas_config = config['ivas']
                    break

            if first_ivas_config:
                # 创建共享的 IVAS Client（单例）
                ivas_client = IVASClient(
                    base_url=IVAS_SERVER['base_url'],
                    account=first_ivas_config['account'],
                    password=first_ivas_config['password']
                )

                # 登录
                if not ivas_client.login():
                    console.print("[bright_red]✗ IVAS 登录失败[/bright_red]")
                else:
                    console.print(f"[bright_cyan]✓ IVAS 客户端已登录 ({first_ivas_config['account']})[/bright_cyan]")

                    # 为每个无人机启动位置上报线程
                    if IVAS_FEATURES.get('position_report', False):
                        for i, uav in enumerate(uav_clients):
                            config = UAV_CONFIGS[i]

                            if 'ivas' not in config:
                                continue

                            device_code = config['ivas']['device_code']
                            callsign = config['callsign']

                            # 创建停止事件
                            stop_event = threading.Event()
                            ivas_stop_events.append(stop_event)

                            # 启动位置上报线程
                            thread = threading.Thread(
                                target=position_reporter,
                                args=(uav['mqtt'], ivas_client, device_code, callsign, 1.0, stop_event),
                                daemon=True,
                                name=f"ivas-position-{device_code}"
                            )
                            thread.start()
                            ivas_threads.append(thread)

                            # 添加额外字段到 uav_client（用于任务执行）
                            uav['config'] = config
                            uav['callsign'] = callsign
                            uav['flight_height'] = config.get('flight_height', 100.0)

                            console.print(f"[bright_cyan]  ✓ 设备 {device_code} 位置上报线程已启动[/bright_cyan]")

                    # 启动目标上报线程（如果启用）
                    if IVAS_FEATURES.get('target_report', False):
                        # 使用第一个设备的基准位置
                        base_lat = 23.0  # 可从配置获取
                        base_lon = 113.0
                        base_alt = 0.0
                        coord_range = {'lat_offset': 0.01, 'lon_offset': 0.01, 'alt_offset': 10}

                        stop_event = threading.Event()
                        ivas_stop_events.append(stop_event)

                        thread = threading.Thread(
                            target=target_reporter,
                            args=(ivas_client, base_lat, base_lon, base_alt, coord_range, 2.0, stop_event),
                            daemon=True,
                            name="ivas-target"
                        )
                        thread.start()
                        ivas_threads.append(thread)

                        console.print("[bright_cyan]  ✓ 目标上报线程已启动[/bright_cyan]")

                    # 启动任务轮询线程（如果启用）
                    if IVAS_FEATURES.get('task_receive', False):
                        # 构建设备映射 {device_code: uav_client}
                        uav_clients_map = {}
                        for i, uav in enumerate(uav_clients):
                            config = UAV_CONFIGS[i]
                            if 'ivas' in config:
                                device_code = config['ivas']['device_code']
                                uav_clients_map[device_code] = uav

                        stop_event = threading.Event()
                        ivas_stop_events.append(stop_event)

                        thread = threading.Thread(
                            target=task_poller,
                            args=(ivas_client, uav_clients_map, 0.5, stop_event),
                            daemon=True,
                            name="ivas-task-poller"
                        )
                        thread.start()
                        ivas_threads.append(thread)

                        console.print("[bright_cyan]  ✓ 任务轮询线程已启动[/bright_cyan]")

                    console.print(f"\n[bold bright_green]✓ IVAS 系统已就绪 ({len(ivas_threads)} 个线程)[/bold bright_green]")

        # Yield 连接给调用者使用
        yield uav_clients, vrpn_clients, ivas_threads

    finally:
        # === 自动清理资源 ===
        console.rule("[bold bright_magenta]断开连接[/bold bright_magenta]")

        # 清理 IVAS 线程
        if ivas_stop_events:
            console.print("[bright_cyan]清理 IVAS 线程...[/bright_cyan]")
            try:
                # 发送停止信号给所有线程
                for stop_event in ivas_stop_events:
                    stop_event.set()

                # 等待线程结束
                for thread in ivas_threads:
                    thread.join(timeout=2.0)
                    if thread.is_alive():
                        console.print(f"[bright_yellow]⚠ 线程 {thread.name} 未在超时时间内结束[/bright_yellow]")
                    else:
                        console.print(f"[bright_green]✓ 线程 {thread.name} 已停止[/bright_green]")

                console.print(f"[bright_green]✓ IVAS 系统已停止 ({len(ivas_threads)} 个线程)[/bright_green]")
            except Exception as e:
                console.print(f"[bright_yellow]⚠ IVAS 清理警告: {e}[/bright_yellow]")

        # 清理连接管理器
        if conn_managers:
            console.print("[bright_cyan]清理连接管理器...[/bright_cyan]")
            for i, manager in enumerate(conn_managers):
                try:
                    manager.stop()
                    console.print(f"[bright_green]✓ 连接管理器 #{i+1} 已停止[/bright_green]")
                except Exception as e:
                    console.print(f"[bright_yellow]⚠ 连接管理器清理警告: {e}[/bright_yellow]")

        # 清理 VRPN 客户端
        if vrpn_clients:
            console.print("[bright_cyan]清理 VRPN 客户端...[/bright_cyan]")
            for vrpn_data in vrpn_clients:
                if vrpn_data is not None:
                    try:
                        vrpn_data['client'].stop()
                        console.print(f"[bright_green]✓ VRPN 客户端 {vrpn_data['device_name']} 已断开[/bright_green]")
                    except Exception as e:
                        console.print(f"[bright_yellow]⚠ VRPN 清理警告: {e}[/bright_yellow]")

        # 清理无人机连接
        for i, uav_client in enumerate(uav_clients):
            uav_id = uav_client['id']
            sn = UAV_CONFIGS[i]['sn'] if i < len(UAV_CONFIGS) else "未知"
            console.print(f"[bright_cyan]清理无人机 #{uav_id} ({sn})...[/bright_cyan]")
            try:
                stop_heartbeat(uav_client['heartbeat'])
                uav_client['mqtt'].disconnect()
                console.print(f"[bright_green]✓ 无人机 #{uav_id} 已断开[/bright_green]")
            except Exception as e:
                console.print(f"[bright_yellow]⚠ 清理警告: {e}[/bright_yellow]")

        console.print(f"\n[bold bright_green]✓ 所有资源已清理完成[/bold bright_green]\n")


def run():
    """
    运行 Dashboard 监控系统

    这是主循环，体现 "好品味" 设计：
    - 主循环只做一件事：显示数据
    - 所有复杂性下沉到 setup_connections() 和 create_dashboard_layout()
    - 无特殊情况处理（VRPN/IVAS 是否启用不影响主循环）
    """
    console = Console()

    # 使用上下文管理器自动管理资源
    with setup_connections(console) as (uav_clients, vrpn_clients, ivas_threads):
        # 显示频率配置信息
        console.print(f"[bright_cyan]OSD 频率: {OSD_FREQUENCY} Hz | GUI 刷新频率: {GUI_REFRESH_RATE} Hz[/bright_cyan]")
        if ENABLE_VRPN and vrpn_clients:
            console.print(f"[bright_cyan]VRPN 动捕显示: [bright_green]已启用[/bright_green][/bright_cyan]")
        if ENABLE_IVAS and ivas_threads:
            console.print(f"[bright_cyan]IVAS 系统: [bright_green]已启用[/bright_green] ({len(ivas_threads)} 个线程)[/bright_cyan]")
        console.print(f"[bright_cyan]离线检测超时: {OFFLINE_TIMEOUT} 秒[/bright_cyan]")
        console.print("[bold bright_yellow]监控运行中... (按 Ctrl+C 退出)[/bold bright_yellow]\n")

        # 实时监控循环
        sleep_interval = 1.0 / GUI_REFRESH_RATE
        start_time = time.time()

        try:
            with Live(console=console, refresh_per_second=GUI_REFRESH_RATE, screen=True) as live:
                while True:
                    elapsed = int(time.time() - start_time)

                    # 核心：一行生成整个布局（无特殊情况）
                    layout = create_dashboard_layout(
                        uav_clients,
                        vrpn_clients,
                        UAV_CONFIGS,
                        elapsed,
                        OFFLINE_TIMEOUT,
                        ivas_adapters=None,  # DEPRECATED
                        enable_ivas=ENABLE_IVAS,
                        ivas_features=IVAS_FEATURES,
                        ivas_threads=ivas_threads,  # 传递线程列表
                    )

                    live.update(layout)
                    time.sleep(sleep_interval)

        except KeyboardInterrupt:
            console.print("\n\n[bright_yellow]中断信号收到，正在清理...[/bright_yellow]\n")
