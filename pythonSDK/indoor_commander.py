#!/usr/bin/env python3
"""
室内指挥端程序

功能：
1. 订阅 UWB MQTT 主题（uwb/position）
2. 上报位置到 IVAS
3. 轮询 IVAS 任务
4. 转发 mission=1 任务到 MQTT（ivas/task/command）
5. 基于位置触发目标上报（永久激活模式）

使用方法：
    python indoor_commander.py
"""

import json
import time
import threading
from rich.console import Console
import paho.mqtt.client as mqtt

# IVAS 模块导入（重构后）
from ivas import IVASClient, DryRunReporter, UWBPosition, ThreadManager
from ivas.ivas_threads import (
    uwb_position_reporter,
    uwb_trigger_target_reporter,
    task_mqtt_forwarder
)

# 加载统一配置（单一来源）
from dashboard.config import (
    UAV_CONFIGS,
    IVAS_SERVER,
    MQTT_CONFIG,
    INDOOR_SYSTEM  # 室内系统配置
)

console = Console()

# ========== 全局状态（仅数据共享）==========

# UWB 位置数据（线程安全）
uwb_position = UWBPosition()

# ========== MQTT 回调 ==========

def on_connect(client, userdata, flags, rc):
    """连接回调"""
    cfg = INDOOR_SYSTEM  # 配置别名
    if rc == 0:
        console.print(f"[green]✓ 已连接到 MQTT Broker[/green]")
        # 订阅 UWB 主题
        client.subscribe(cfg['uwb']['subscribe_topic'], qos=0)
        console.print(f"[green]✓ 已订阅 UWB 主题: {cfg['uwb']['subscribe_topic']}[/green]")
    else:
        console.print(f"[red]✗ 连接失败，错误码: {rc}[/red]")


def on_uwb_message(client, userdata, msg):
    """UWB MQTT 消息回调"""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        pos = payload['position']

        # 使用 UWBPosition 的线程安全 update() 方法
        uwb_position.update(
            x=pos['x'],
            y=pos['y'],
            z=pos['z'],
            timestamp=payload['timestamp']
        )
    except Exception as e:
        print(f"[UWB] 主题解析失败: {e}")


# ========== 主程序 ==========

def main():
    """主函数"""
    cfg = INDOOR_SYSTEM  # 配置别名
    uav_cfg = UAV_CONFIGS[0]  # 使用第一台无人机配置

    console.print("\n[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]")
    console.print("[bold bright_cyan]       室内指挥端程序[/bold bright_cyan]")
    console.print("[bold bright_cyan]       UWB 订阅 + IVAS 交互 + 任务转发[/bold bright_cyan]")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    # 打印配置信息
    console.print(f"[bold]📋 配置信息[/bold]")
    console.print(f"  呼号: {uav_cfg['callsign']} (device_code={uav_cfg['ivas']['device_code']})")

    # IVAS 模式状态
    if not cfg['use_dry_run']:
        console.print(f"  IVAS 模式: [green]已启用[/green] ({IVAS_SERVER['base_url']})")
    else:
        console.print(f"  IVAS 模式: [yellow]Dry-run（仅打印，不连接服务器）[/yellow]")

    console.print(f"  UWB 订阅主题: {cfg['uwb']['subscribe_topic']}")
    console.print(f"  任务转发主题: {cfg['task']['publish_topic']}")
    console.print(f"  位置上报频率: {cfg['reporting']['position_hz']} Hz")
    console.print(f"  任务轮询频率: {cfg['reporting']['task_hz']} Hz")

    # 目标配置状态
    if cfg['targets']['enabled']:
        console.print(f"  目标上报: [green]已启用[/green] (频率: {cfg['reporting']['target_hz']}Hz, 目标数: {len(cfg['targets']['positions'])})")
        console.print(f"  触发模式: [cyan]永久激活[/cyan] (进入区域后持续上报)")
    else:
        console.print(f"  目标上报: [yellow]已禁用[/yellow]")

    # 高度配置状态
    if cfg['uwb']['use_altitude']:
        console.print(f"  高度来源: [cyan]UWB 实时高度[/cyan]")
    else:
        console.print(f"  高度来源: [yellow]固定高度 {cfg['uwb']['fixed_altitude_base']:.2f}m (±{cfg['uwb']['fixed_altitude_range']:.2f}m)[/yellow]")

    console.print()

    # 1. 初始化 IVAS（或 Dry-run 模式）
    console.print("[bold]📡 步骤 1: 初始化 IVAS[/bold]")

    if not cfg['use_dry_run']:
        # 真实 IVAS 连接
        ivas_config = uav_cfg['ivas']
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
    mqtt_client = mqtt.Client(client_id=f'commander-{int(time.time())}')
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

    # 3-5. 启动所有线程（使用 ThreadManager 统一管理）
    console.print("[bold]🚀 步骤 3-5: 启动所有工作线程[/bold]")
    manager = ThreadManager()

    # 启动位置上报线程
    manager.spawn(
        f"uwb-position-{uav_cfg['ivas']['device_code']}",
        uwb_position_reporter,
        uwb_position,  # UWBPosition 对象（内置线程安全）
        ivas_client,
        uav_cfg['ivas']['device_code'],
        uav_cfg['callsign'],
        cfg['uwb']['transform'],
        1.0 / cfg['reporting']['position_hz'],
        # stop_event 由 ThreadManager 自动管理
        use_uwb_altitude=cfg['uwb']['use_altitude'],
        fixed_altitude_base=cfg['uwb']['fixed_altitude_base'],
        fixed_altitude_range=cfg['uwb']['fixed_altitude_range'],
        default_heading=cfg['defaults']['heading'],
        default_motion=cfg['defaults']['motion'],
        user_name='indoor',
        print_duration=cfg['reporting']['position_log_duration']
    )

    # 启动目标上报线程（如果启用）
    if cfg['targets']['enabled']:
        manager.spawn(
            "target-reporter",
            uwb_trigger_target_reporter,
            uwb_position,  # UWBPosition 对象（内置线程安全）
            ivas_client,
            cfg['uwb']['transform'],
            cfg['targets']['trigger_areas'],
            cfg['targets']['positions'],
            1.0 / cfg['reporting']['target_hz'],
            # stop_event 由 ThreadManager 自动管理
            print_duration=cfg['reporting']['target_log_duration']
        )

    # 启动任务轮询线程
    manager.spawn(
        "task-poller",
        task_mqtt_forwarder,
        ivas_client,
        mqtt_client,
        cfg['task']['publish_topic'],
        cfg['task']['mission_filter'],  # 只转发 mission=1 (起飞)
        1.0 / cfg['reporting']['task_hz'],
        # stop_event 由 ThreadManager 自动管理
    )

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
        # 停止所有线程（ThreadManager 统一管理）
        manager.stop_all()

        # 停止 MQTT
        console.print("[bright_cyan]停止 MQTT...[/bright_cyan]")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        console.print("[bright_green]✓ MQTT 已断开[/bright_green]")

        console.print("[bold green]✅ 程序已退出[/bold green]\n")


if __name__ == '__main__':
    main()
