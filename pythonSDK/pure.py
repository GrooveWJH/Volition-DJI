#!/usr/bin/env python3
"""
纯净版 IVAS + 多DRC 程序

专注于：
1. IVAS 任务接收和分发
2. 多无人机 DRC 控制
3. 任务执行 DEBUG 输出

不包含：
- Dashboard UI
- VRPN 数据
- 无人机状态显示

使用方法：
    python pure.py

重构说明：
现在直接使用 dashboard/ivas_threads.py 中的线程函数，与 dashboard 共享同一套实现。

配置复用：
- 复用 control/config.py 中的控制参数（PID、频率等）
- 复用 dashboard/config.py 中的 IVAS 配置
"""
import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any
from rich.console import Console

from djisdk import MQTTClient, ServiceCaller
from djisdk import request_control_auth, enter_drc_mode, start_heartbeat, stop_heartbeat
from ivas import IVASClient

# 导入共享的线程函数
from ivas.ivas_threads import task_poller, position_reporter, fake_target_reporter

# 导入配置（复用 dashboard 配置，避免重复）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control.config as ctrl_cfg
from config import (
    MQTT_CONFIG,
    UAV_CONFIGS,
    IVAS_SERVER,
    IVAS_ADVANCED,
    IVAS_FEATURES,
    IVAS_FAKE_TARGET
)

console = Console()

# ========== 配置 ==========

# 机器颜色映射（用于DEBUG输出）
DEVICE_COLORS = {
    1: 'bright_cyan',
    2: 'bright_magenta',
    3: 'bright_green',
}

# 任务状态文件路径
MISSION_STATE_FILE = Path('/tmp/djisdk_mission_state.json')


# ========== 辅助函数 ==========

def setup_drc(uav_config: Dict[str, Any], mqtt_config: Dict[str, Any]) -> tuple:
    """
    建立 DRC 连接

    Args:
        uav_config: 无人机配置
        mqtt_config: MQTT 配置

    Returns:
        (mqtt_client, caller, heartbeat_thread) 或 (None, None, None) 如果失败
    """
    device_code = uav_config['ivas']['device_code']
    callsign = uav_config['callsign']
    color = DEVICE_COLORS.get(device_code, 'bright_white')

    def log(level: str, message: str):
        """彩色日志输出"""
        timestamp = time.strftime("%H:%M:%S")
        level_colors = {
            'info': 'bright_white',
            'warning': 'bright_yellow',
            'error': 'bright_red',
        }
        level_color = level_colors.get(level, 'bright_white')
        console.print(
            f"[dim]{timestamp}[/dim] [{color}][{callsign}][/{color}] "
            f"[{level_color}]{message}[/{level_color}]"
        )

    try:
        # 1. 连接 MQTT
        log('info', f"连接 MQTT ({mqtt_config['host']}:{mqtt_config['port']})...")
        mqtt = MQTTClient(uav_config['sn'], mqtt_config)
        mqtt.connect()
        log('info', "✅ MQTT 连接成功")

        # 2. 请求控制权
        log('info', "请求控制权...")
        caller = ServiceCaller(mqtt)
        request_control_auth(caller, user_id=uav_config['user_id'], user_callsign=callsign)
        log('info', "✅ 控制权获取成功")

        # 3. 进入 DRC 模式
        log('info', "进入 DRC 模式...")
        mqtt_broker_config = {
            'address': f"{mqtt_config['host']}:{mqtt_config['port']}",
            'client_id': f"drc-{device_code}",
            'username': mqtt_config['username'],
            'password': mqtt_config['password'],
            'expire_time': int(time.time()) + 3600,
            'enable_tls': False
        }
        enter_drc_mode(caller, mqtt_broker=mqtt_broker_config, osd_frequency=10, hsi_frequency=5)
        log('info', "✅ DRC 模式已启动")

        # 4. 启动心跳
        log('info', "启动心跳...")
        heartbeat_thread = start_heartbeat(mqtt, interval=1.0)
        log('info', "✅ 心跳已启动")

        return mqtt, caller, heartbeat_thread

    except Exception as e:
        log('error', f"❌ DRC 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def cleanup_drc(mqtt, heartbeat_thread, callsign: str, device_code: int):
    """
    清理 DRC 资源

    Args:
        mqtt: MQTT 客户端
        heartbeat_thread: 心跳线程
        callsign: 呼号
        device_code: 设备编号
    """
    color = DEVICE_COLORS.get(device_code, 'bright_white')

    def log(level: str, message: str):
        timestamp = time.strftime("%H:%M:%S")
        level_colors = {'info': 'bright_white', 'warning': 'bright_yellow', 'error': 'bright_red'}
        level_color = level_colors.get(level, 'bright_white')
        console.print(
            f"[dim]{timestamp}[/dim] [{color}][{callsign}][/{color}] "
            f"[{level_color}]{message}[/{level_color}]"
        )

    log('info', "清理资源...")

    if heartbeat_thread:
        stop_heartbeat(heartbeat_thread)

    if mqtt:
        mqtt.disconnect()

    log('info', "✅ 资源清理完成")


# ========== 主程序 ==========

def main():
    """主函数"""
    console.print("\n[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]")
    console.print("[bold bright_cyan]       纯净版 IVAS + 多DRC 程序[/bold bright_cyan]")
    console.print("[bold bright_cyan]       使用共享的 IVAS 线程函数[/bold bright_cyan]")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    # 0. 清理旧的任务状态文件（避免 dashboard 读取过期数据）
    if MISSION_STATE_FILE.exists():
        try:
            MISSION_STATE_FILE.unlink()
            console.print("[bright_yellow]✓ 已清理旧的任务状态文件[/bright_yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  清理任务状态文件失败: {e}[/yellow]")
    console.print()

    # 1. 初始化所有无人机的 IVAS 客户端
    console.print("[bold]📡 步骤 1: 初始化 IVAS 客户端[/bold]")

    # 为后续任务轮询创建一个共享的 IVAS 客户端（单点轮询）
    shared_ivas_client = None

    # 2. 建立所有无人机的 DRC 连接
    console.print("\n[bold]🚁 步骤 2: 初始化无人机 DRC 连接[/bold]")

    uav_clients = []
    uav_clients_map = {}

    for uav_config in UAV_CONFIGS:
        device_code = uav_config['ivas']['device_code']
        callsign = uav_config['callsign']

        console.print(f"\n[bold bright_cyan]初始化 {callsign} (device_code={device_code})...[/bold bright_cyan]")

        # 2.1. 创建独立的 IVAS 客户端
        ivas_config = uav_config['ivas']
        ivas_client = IVASClient(
            base_url=IVAS_SERVER['base_url'],
            account=ivas_config['account'],
            password=ivas_config['password']
        )

        # 登录 IVAS
        if not ivas_client.login():
            console.print(f"[red]❌ {callsign} IVAS 登录失败 (账号: {ivas_config['account']})，退出程序[/red]")
            # 清理已建立的连接
            for uav in uav_clients:
                cleanup_drc(uav['mqtt'], uav['heartbeat'], uav['callsign'], uav['device_code'])
            return

        console.print(f"[bright_green]✓ IVAS 客户端已登录 (账号: {ivas_config['account']})[/bright_green]")

        # 保存第一个 IVAS 客户端用于任务轮询（单点轮询）
        if shared_ivas_client is None:
            shared_ivas_client = ivas_client

        # 2.2. 建立 DRC 连接
        mqtt, caller, heartbeat = setup_drc(uav_config, MQTT_CONFIG)

        if not mqtt:
            console.print(f"[red]❌ {callsign} DRC 连接失败，退出程序[/red]")
            # 清理已建立的连接
            for uav in uav_clients:
                cleanup_drc(uav['mqtt'], uav['heartbeat'], uav['callsign'], uav['device_code'])
            return

        # 保存连接信息
        uav_client = {
            'device_code': device_code,
            'callsign': callsign,
            'mqtt': mqtt,
            'caller': caller,
            'heartbeat': heartbeat,
            'ivas_client': ivas_client,  # 每架无人机独立的 IVAS 客户端
            'config': uav_config,
            'flight_height': uav_config.get('flight_height', 100.0),
            'current_runner': None,  # 用于任务执行
            # 假目标上报的按需启动/关闭
            'fake_target_config': IVAS_FAKE_TARGET if (IVAS_FEATURES.get('fake_target_report', False) and IVAS_FAKE_TARGET['enabled']) else None,
            'fake_target_thread': None,
            'fake_target_stop': None
        }

        uav_clients.append(uav_client)
        uav_clients_map[device_code] = uav_client

    console.print()

    # 2.5. 启动位置上报线程（如果启用）
    position_threads = []
    position_stop_events = []

    if IVAS_FEATURES.get('position_report', False):
        console.print("[bold]📍 步骤 2.5: 启动位置上报[/bold]")

        for uav in uav_clients:
            device_code = uav['device_code']
            callsign = uav['callsign']

            # 创建停止事件
            stop_event = threading.Event()
            position_stop_events.append(stop_event)

            # 启动位置上报线程（使用各自的 IVAS 客户端）
            thread = threading.Thread(
                target=position_reporter,
                args=(
                    uav['mqtt'],
                    uav['ivas_client'],  # ✅ 使用各自的 IVAS 客户端
                    device_code,
                    callsign,
                    1.0 / IVAS_SERVER['report_hz'],
                    stop_event,
                    IVAS_ADVANCED['require_gps'],
                    IVAS_ADVANCED.get('position_log_duration', 5.0)  # ✅ 位置上报日志时长
                ),
                daemon=True,
                name=f"ivas-position-{device_code}"
            )
            thread.start()
            position_threads.append(thread)

            console.print(f"[bright_green]✓ {callsign} 位置上报线程已启动 (账号: {uav['config']['ivas']['account']})[/bright_green]")

        console.print()

    # 2.6. 假目标上报不在此处全局启动：仅在任务执行阶段针对航线任务（mission 5/6/7）按需启动
    fake_target_threads = []
    fake_target_stop_events = []
    if IVAS_FEATURES.get('fake_target_report', False) and IVAS_FAKE_TARGET['enabled']:
        console.print("[bold]🎯 步骤 2.6: 假目标上报将按需在航线任务启动[/bold]")

    # 3. 启动任务轮询线程（使用共享 IVAS 客户端进行单点轮询）
    console.print("[bold]🎯 步骤 3: 启动任务轮询[/bold]")

    task_stop_event = threading.Event()
    task_thread = threading.Thread(
        target=task_poller,
        args=(
            shared_ivas_client,  # ✅ 单点轮询，使用第一个账号
            uav_clients_map,
            1.0 / IVAS_SERVER['task_hz'],
            task_stop_event,
            True  # pure.py 必须启用任务分发（监视模式仅对 dashboard 有意义）
        ),
        daemon=True,
        name="ivas-task-poller"
    )
    task_thread.start()

    console.print(f"[bright_green]✓ 任务轮询线程已启动 (单点轮询账号: {UAV_CONFIGS[0]['ivas']['account']})[/bright_green]")
    console.print()

    # 4. 运行
    console.print("[bold green]✅ 系统就绪，等待 IVAS 任务...[/bold green]")
    console.print("[dim]按 Ctrl+C 退出[/dim]\n")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    try:
        # 主线程等待
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  接收到中断信号，正在退出...[/yellow]")

    finally:
        # 5. 清理资源
        console.print("\n[bold]🧹 清理资源...[/bold]")

        # 停止位置上报线程
        if position_stop_events:
            console.print("[bright_cyan]停止位置上报线程...[/bright_cyan]")
            for stop_event in position_stop_events:
                stop_event.set()

            for thread in position_threads:
                thread.join(timeout=2.0)
                if thread.is_alive():
                    console.print(f"[yellow]⚠️  {thread.name} 未在超时时间内结束[/yellow]")
                else:
                    console.print(f"[bright_green]✓ {thread.name} 已停止[/bright_green]")

        # 停止假目标上报线程
        if fake_target_stop_events:
            console.print("[bright_cyan]停止假目标上报线程...[/bright_cyan]")
            for stop_event in fake_target_stop_events:
                stop_event.set()

            for thread in fake_target_threads:
                thread.join(timeout=2.0)
                if thread.is_alive():
                    console.print(f"[yellow]⚠️  {thread.name} 未在超时时间内结束[/yellow]")
                else:
                    console.print(f"[bright_green]✓ {thread.name} 已停止[/bright_green]")

        # 停止任务轮询线程
        console.print("[bright_cyan]停止任务轮询线程...[/bright_cyan]")
        task_stop_event.set()
        task_thread.join(timeout=2.0)
        if task_thread.is_alive():
            console.print("[yellow]⚠️  任务轮询线程未在超时时间内结束[/yellow]")
        else:
            console.print("[bright_green]✓ 任务轮询线程已停止[/bright_green]")

        # 清理所有无人机连接
        for uav in uav_clients:
            cleanup_drc(
                uav['mqtt'],
                uav['heartbeat'],
                uav['callsign'],
                uav['device_code']
            )

        # 清理任务状态文件，防止 Dashboard 读取过期任务数据
        if MISSION_STATE_FILE.exists():
            try:
                MISSION_STATE_FILE.unlink()
                console.print("[bright_yellow]✓ 已删除任务状态文件[/bright_yellow]")
            except Exception as e:
                console.print(f"[yellow]⚠️  删除任务状态文件失败: {e}[/yellow]")

        console.print("[bold green]✅ 程序已退出[/bold green]\n")


if __name__ == '__main__':
    main()
