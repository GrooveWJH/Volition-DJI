#!/usr/bin/env python3
"""
DJI 无人机直播推流工具

功能：
1. 选择连接的无人机
2. 建立 DRC 连接
3. 启动直播推流
4. 显示请求和响应详情
"""

import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from djisdk import (
    MQTTClient,
    ServiceCaller,
    setup_drc_connection,
    stop_heartbeat,
)

console = Console()

# ========== 配置区域 ==========

# MQTT 配置
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# 无人机配置列表
UAV_CONFIGS = [
    {
        'name': 'UAV-001',
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot_1',
        'callsign': 'Pilot 1',
        'video_id': '1581F7FVC253A00D04J5/88-0-0/normal-0',  # {sn}/{camera_index}/{video_index}
    },
    {
        'name': 'UAV-002',
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot_2',
        'callsign': 'Pilot 2',
        'video_id': '9N9CN8400164WH/88-0-0/normal-0',
    },
    {
        'name': 'UAV-003',
        'sn': '9N9CN180011TJN',
        'user_id': 'pilot_3',
        'callsign': 'Pilot 3',
        'video_id': '9N9CN180011TJN/88-0-0/normal-0',
    },
]

# 直播配置
LIVE_CONFIG = {
    'url_type': 1,  # 0=Agora, 1=RTMP, 3=GB28181, 4=WebRTC
    'url': 'rtmp://192.168.8.151:1935/live/drone001',  # RTMP 推流地址
    'video_quality': 1,  # 0=自适应, 1=流畅, 2=标清, 3=高清, 4=超清
}

# OSD/HSI 频率配置
OSD_FREQUENCY = 1  # Hz
HSI_FREQUENCY = 1   # Hz


# ========== 工具函数 ==========

def display_uav_list():
    """显示无人机列表"""
    table = Table(title="[bold cyan]可用无人机列表[/bold cyan]", show_header=True, header_style="bold magenta")
    table.add_column("编号", style="cyan", justify="center")
    table.add_column("名称", style="green")
    table.add_column("序列号", style="yellow")
    table.add_column("呼号", style="blue")

    for i, uav in enumerate(UAV_CONFIGS, 1):
        table.add_row(str(i), uav['name'], uav['sn'], uav['callsign'])

    console.print(table)


def select_uav():
    """让用户选择无人机"""
    display_uav_list()

    while True:
        choice = Prompt.ask(
            "\n[bold cyan]请选择要连接的无人机编号[/bold cyan]",
            choices=[str(i) for i in range(1, len(UAV_CONFIGS) + 1)],
            default="1"
        )

        index = int(choice) - 1
        selected = UAV_CONFIGS[index]

        console.print(f"\n[green]✓ 已选择:[/green] [bold]{selected['name']}[/bold] ({selected['sn']})")
        return selected


def display_live_config(uav_config):
    """显示直播配置"""
    url_type_names = {0: "声网 Agora", 1: "RTMP", 3: "GB28181", 4: "WebRTC"}
    quality_names = {0: "自适应", 1: "流畅", 2: "标清", 3: "高清", 4: "超清"}

    table = Table(title="[bold cyan]直播推流配置[/bold cyan]", show_lines=True)
    table.add_column("参数", style="cyan", justify="right")
    table.add_column("值", style="yellow")

    table.add_row("无人机", f"{uav_config['name']} ({uav_config['sn']})")
    table.add_row("视频ID", uav_config['video_id'])
    table.add_row("协议类型", f"{url_type_names.get(LIVE_CONFIG['url_type'], '未知')} ({LIVE_CONFIG['url_type']})")
    table.add_row("推流地址", LIVE_CONFIG['url'])
    table.add_row("视频质量", f"{quality_names.get(LIVE_CONFIG['video_quality'], '未知')} ({LIVE_CONFIG['video_quality']})")

    console.print("\n")
    console.print(table)


def display_mqtt_payload(title, payload_dict):
    """美化显示 MQTT 消息内容"""
    json_str = json.dumps(payload_dict, indent=2, ensure_ascii=False)

    # 语法高亮
    from rich.syntax import Syntax
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)

    panel = Panel(
        syntax,
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )

    console.print("\n")
    console.print(panel)


def start_live_push_with_details(caller: ServiceCaller, uav_config: dict):
    """
    启动直播推流并显示详细的请求/响应信息

    Args:
        caller: 服务调用器
        uav_config: 无人机配置
    """
    console.print("\n[bold cyan]========== 开始直播推流 ==========[/bold cyan]")

    # 构造请求数据
    request_data = {
        "url": LIVE_CONFIG['url'],
        "url_type": LIVE_CONFIG['url_type'],
        "video_id": uav_config['video_id'],
        "video_quality": LIVE_CONFIG['video_quality']
    }

    # 显示即将发送的请求（模拟完整 MQTT payload）
    import time
    import uuid
    tid = str(uuid.uuid4())
    simulated_request = {
        "bid": tid,
        "data": request_data,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": "live_start_push"
    }

    display_mqtt_payload("📤 发送 MQTT 请求", simulated_request)

    # 实际发送请求
    console.print("\n[yellow]发送中...[/yellow]")

    try:
        # 调用 SDK 函数（内部会调用 caller.call）
        result = caller.call("live_start_push", request_data)

        # 构造响应 payload（模拟完整响应）
        simulated_response = {
            "bid": tid,
            "data": result,
            "tid": tid,
            "timestamp": int(time.time() * 1000),
            "method": "live_start_push"
        }

        display_mqtt_payload("📥 接收 MQTT 响应", simulated_response)

        # 检查结果
        if result.get('result') == 0:
            console.print("\n[bold green]✓ 直播推流启动成功！[/bold green]")
            console.print(f"[green]视频流正在推送到:[/green] [cyan]{LIVE_CONFIG['url']}[/cyan]")
        else:
            console.print(f"\n[bold red]✗ 直播推流失败[/bold red]")
            console.print(f"[red]错误信息:[/red] {result}")

    except Exception as e:
        console.print(f"\n[bold red]✗ 请求异常: {e}[/bold red]")


# ========== 主程序 ==========

def main():
    console.print("\n[bold]" + "=" * 60 + "[/bold]")
    console.print("[bold cyan]DJI 无人机直播推流工具[/bold cyan]")
    console.print("[bold]" + "=" * 60 + "[/bold]\n")

    # 步骤 1: 选择无人机
    selected_uav = select_uav()

    # 步骤 2: 显示直播配置
    display_live_config(selected_uav)

    # 步骤 3: 确认继续
    console.print("\n")
    confirm = Prompt.ask(
        "[bold yellow]是否继续建立连接并启动直播?[/bold yellow]",
        choices=["y", "n"],
        default="y"
    )

    if confirm.lower() != 'y':
        console.print("[yellow]操作已取消[/yellow]")
        return

    # 步骤 4: 建立 DRC 连接
    console.print("\n[bold cyan]========== 建立 DRC 连接 ==========[/bold cyan]\n")

    mqtt, caller, heartbeat = setup_drc_connection(
        gateway_sn=selected_uav['sn'],
        mqtt_config=MQTT_CONFIG,
        user_id=selected_uav['user_id'],
        user_callsign=selected_uav['callsign'],
        osd_frequency=OSD_FREQUENCY,
        hsi_frequency=HSI_FREQUENCY,
        heartbeat_interval=1.0,
        wait_for_user=True
    )

    try:
        # 步骤 5: 启动直播推流
        start_live_push_with_details(caller, selected_uav)

        # 步骤 6: 保持连接（可选）
        console.print("\n[bold yellow]直播运行中，按 Ctrl+C 停止...[/bold yellow]")
        input("\n按 Enter 键停止直播并退出...")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]收到中断信号[/yellow]")

    finally:
        # 清理资源
        console.print("\n[bold cyan]========== 清理资源 ==========[/bold cyan]")
        console.print("[cyan]停止心跳...[/cyan]")
        stop_heartbeat(heartbeat)
        console.print("[cyan]断开 MQTT 连接...[/cyan]")
        mqtt.disconnect()
        console.print("[bold green]✓ 清理完成[/bold green]\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        console.print(f"\n[bold red]程序异常: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
