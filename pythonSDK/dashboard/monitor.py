"""
Dashboard 监控循环模块

使用上下文管理器管理资源，消除重复的清理代码。
新增：IVAS 系统集成（位置上报、任务接收）。
"""
import os
import time
from contextlib import contextmanager
from rich.console import Console
from rich.live import Live

from djisdk import setup_multiple_drc_connections, stop_heartbeat
from vrpn import VRPNClient

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
    IVAS_ACCOUNTS,
)
from .panels import create_dashboard_layout
from .ivas_adapter import IVASAdapter


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
        (uav_clients, vrpn_clients, ivas_adapters) 元组
    """
    uav_clients = []
    vrpn_clients = []
    ivas_adapters = []  # 新增：IVAS 适配器列表

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

        # === 阶段 3: 初始化 IVAS 客户端（如果启用）===
        if ENABLE_IVAS and IVAS_FEATURES.get('position_report', False):
            console.rule("[bold bright_blue]初始化 IVAS 系统[/bold bright_blue]")
            for i, uav in enumerate(uav_clients):
                if i < len(IVAS_ACCOUNTS):
                    account = IVAS_ACCOUNTS[i]
                    config = UAV_CONFIGS[i]

                    try:
                        console.print(f"[bright_cyan]初始化 IVAS 适配器 #{i+1} ({account['account']})...[/bright_cyan]")

                        # 创建 IVAS 适配器
                        adapter = IVASAdapter(
                            device_code=account['device_code'],
                            mqtt_client=uav['mqtt'],
                            ivas_config={
                                **IVAS_SERVER,
                                'account': account['account'],
                                'password': account['password'],
                            },
                            uav_config=config
                        )

                        # 启动 IVAS 客户端后台线程
                        adapter.start()

                        ivas_adapters.append(adapter)
                        uav['ivas'] = adapter  # 绑定到 UAV 客户端

                        console.print(f"[bright_green]✓ IVAS 适配器 #{i+1} 已启动[/bright_green]")
                    except Exception as e:
                        console.print(f"[bright_red]✗ IVAS 初始化失败: {e}[/bright_red]")

            if ivas_adapters:
                console.print(f"\n[bold bright_green]✓ IVAS 系统已就绪 ({len(ivas_adapters)} 个设备)[/bold bright_green]")
            else:
                console.print(f"\n[bold bright_yellow]⚠ IVAS 系统未启动[/bold bright_yellow]")

        # Yield 连接给调用者使用
        yield uav_clients, vrpn_clients, ivas_adapters

    finally:
        # === 自动清理资源 ===
        console.rule("[bold bright_magenta]断开连接[/bold bright_magenta]")

        # 清理 IVAS 客户端
        if ivas_adapters:
            console.print("[bright_cyan]清理 IVAS 客户端...[/bright_cyan]")
            for i, adapter in enumerate(ivas_adapters):
                try:
                    adapter.stop()
                    console.print(f"[bright_green]✓ IVAS 适配器 #{i+1} 已停止[/bright_green]")
                except Exception as e:
                    console.print(f"[bright_yellow]⚠ IVAS 清理警告: {e}[/bright_yellow]")

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
    with setup_connections(console) as (uav_clients, vrpn_clients, ivas_adapters):
        # 显示频率配置信息
        console.print(f"[bright_cyan]OSD 频率: {OSD_FREQUENCY} Hz | GUI 刷新频率: {GUI_REFRESH_RATE} Hz[/bright_cyan]")
        if ENABLE_VRPN and vrpn_clients:
            console.print(f"[bright_cyan]VRPN 动捕显示: [bright_green]已启用[/bright_green][/bright_cyan]")
        if ENABLE_IVAS and ivas_adapters:
            console.print(f"[bright_cyan]IVAS 系统: [bright_green]已启用[/bright_green] ({len(ivas_adapters)} 个设备)[/bright_cyan]")
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
                        ivas_adapters=ivas_adapters,
                        enable_ivas=ENABLE_IVAS,
                        ivas_features=IVAS_FEATURES,
                    )

                    live.update(layout)
                    time.sleep(sleep_interval)

        except KeyboardInterrupt:
            console.print("\n\n[bright_yellow]中断信号收到，正在清理...[/bright_yellow]\n")
