#!/usr/bin/env python3
"""
DJI 无人机 RTMP 直播工具

功能：
1. 连接无人机并进入 DRC 模式
2. 自动检测相机参数 (payload_index, aircraft_sn)
3. 开始 RTMP 直播推流
4. 停止直播推流
"""

import time
import json
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich.syntax import Syntax
from djisdk import (
    setup_drc_connection,
    stop_heartbeat,
)

console = Console()


def print_json_message(title, data, color="cyan"):
    """
    美化打印 JSON 消息

    Args:
        title: 标题
        data: JSON 数据（dict）
        color: 边框颜色
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    panel = Panel(
        syntax,
        title=f"[bold {color}]{title}[/bold {color}]",
        border_style=color,
        padding=(1, 2)
    )
    console.print("\n")
    console.print(panel)

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
    },
    {
        'name': 'UAV-002',
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot_2',
        'callsign': 'Pilot 2',
    },
    {
        'name': 'UAV-003',
        'sn': '9N9CN180011TJN',
        'user_id': 'pilot_3',
        'callsign': 'Pilot 3',
    },
]

# RTMP 直播配置
RTMP_URL = 'rtmp://192.168.31.73:1935/live/drone001'
VIDEO_INDEX = 'normal-0'  # 视频流索引
VIDEO_QUALITY = 1  # 0=自适应, 1=流畅, 2=标清, 3=高清, 4=超清

# DRC 配置
OSD_FREQUENCY = 1  # Hz
HSI_FREQUENCY = 1  # Hz


# ========== 工具函数 ==========

def display_uav_list():
    """显示无人机列表"""
    table = Table(title="[bold cyan]可用无人机列表[/bold cyan]", show_header=True, header_style="bold magenta")
    table.add_column("编号", style="cyan", justify="center")
    table.add_column("名称", style="green")
    table.add_column("序列号", style="yellow")

    for i, uav in enumerate(UAV_CONFIGS, 1):
        table.add_row(str(i), uav['name'], uav['sn'])

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


def wait_for_camera_data(mqtt_client, max_wait=10):
    """
    等待相机数据到达

    Args:
        mqtt_client: MQTT 客户端
        max_wait: 最大等待时间（秒）

    Returns:
        (aircraft_sn, payload_index) 或 (None, None) 如果超时
    """
    console.print(f"\n[yellow]⏳ 等待相机数据（最多 {max_wait} 秒）...[/yellow]")

    start_time = time.time()
    while time.time() - start_time < max_wait:
        aircraft_sn = mqtt_client.get_aircraft_sn()
        payload_index = mqtt_client.get_payload_index()

        if aircraft_sn and payload_index:
            console.print(f"[green]✓ 无人机 SN: {aircraft_sn}[/green]")
            console.print(f"[green]✓ 相机索引: {payload_index}[/green]")
            return aircraft_sn, payload_index

        time.sleep(0.5)

    console.print("[yellow]⚠ 超时，将使用默认值[/yellow]")
    return None, None


def build_video_id(mqtt_client):
    """
    构建 video_id

    Args:
        mqtt_client: MQTT 客户端

    Returns:
        video_id 字符串，格式: {aircraft_sn}/{payload_index}/{video_index}
    """
    aircraft_sn = mqtt_client.get_aircraft_sn() or mqtt_client.gateway_sn
    payload_index = mqtt_client.get_payload_index() or "88-0-0"
    return f"{aircraft_sn}/{payload_index}/{VIDEO_INDEX}"


def start_live(caller, mqtt_client):
    """
    开始直播推流

    Args:
        caller: 服务调用器
        mqtt_client: MQTT 客户端

    Returns:
        video_id: 用于停止直播的 video_id
    """
    console.print("\n[bold cyan]========== 开始直播推流 ==========[/bold cyan]")

    # 构建 video_id
    video_id = build_video_id(mqtt_client)
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")
    console.print(f"[cyan]RTMP URL:[/cyan] {RTMP_URL}")
    console.print(f"[cyan]视频质量:[/cyan] {['自适应', '流畅', '标清', '高清', '超清'][VIDEO_QUALITY]}")

    # 构造请求数据
    request_data = {
        "url": RTMP_URL,
        "url_type": 1,  # RTMP
        "video_id": video_id,
        "video_quality": VIDEO_QUALITY
    }

    # 构造完整的 MQTT 请求消息（模拟）
    import uuid
    tid = str(uuid.uuid4())
    full_request = {
        "bid": tid,
        "data": request_data,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": "live_start_push"
    }

    # 打印发送的请求
    print_json_message("📤 发送 MQTT 请求 (live_start_push)", full_request, "blue")

    # 调用 SDK 开始直播
    try:
        result = caller.call("live_start_push", request_data)

        # 构造完整的 MQTT 响应消息（模拟）
        full_response = {
            "bid": tid,
            "data": result,
            "tid": tid,
            "timestamp": int(time.time() * 1000),
            "method": "live_start_push"
        }

        # 打印接收的响应
        print_json_message("📥 接收 MQTT 响应 (live_start_push)", full_response, "green")

        # 判定成功：data.result == 0
        if result.get('result') == 0:
            console.print("\n[bold green]✓ 直播推流已启动！[/bold green]")

            # 显示额外信息（如果有）
            output = result.get('output', {})
            if output:
                console.print(f"[dim]输出信息: {output}[/dim]")

            return video_id
        else:
            error_code = result.get('result', 'unknown')
            error_msg = result.get('message', '无错误信息')
            console.print(f"\n[bold red]✗ 直播推流失败[/bold red]")
            console.print(f"[red]错误码: {error_code}[/red]")
            console.print(f"[red]错误信息: {error_msg}[/red]")
            return None

    except Exception as e:
        console.print(f"\n[bold red]✗ 请求异常: {e}[/bold red]")
        return None


def stop_live(caller, video_id):
    """
    停止直播推流

    Args:
        caller: 服务调用器
        video_id: 要停止的 video_id
    """
    console.print("\n[bold cyan]========== 停止直播推流 ==========[/bold cyan]")
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")

    # 构造请求数据
    request_data = {"video_id": video_id}

    # 构造完整的 MQTT 请求消息（模拟）
    import uuid
    tid = str(uuid.uuid4())
    full_request = {
        "bid": tid,
        "data": request_data,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": "live_stop_push"
    }

    # 打印发送的请求
    print_json_message("📤 发送 MQTT 请求 (live_stop_push)", full_request, "blue")

    try:
        result = caller.call("live_stop_push", request_data)

        # 构造完整的 MQTT 响应消息（模拟）
        full_response = {
            "bid": tid,
            "data": result,
            "tid": tid,
            "timestamp": int(time.time() * 1000),
            "method": "live_stop_push"
        }

        # 打印接收的响应
        print_json_message("📥 接收 MQTT 响应 (live_stop_push)", full_response, "green")

        # 判定成功：data.result == 0
        if result.get('result') == 0:
            console.print("\n[bold green]✓ 直播推流已停止！[/bold green]")

            # 显示额外信息（如果有）
            output = result.get('output', {})
            if output:
                console.print(f"[dim]输出信息: {output}[/dim]")
        else:
            error_code = result.get('result', 'unknown')
            error_msg = result.get('message', '无错误信息')
            console.print(f"\n[bold red]✗ 停止直播失败[/bold red]")
            console.print(f"[red]错误码: {error_code}[/red]")
            console.print(f"[red]错误信息: {error_msg}[/red]")

    except Exception as e:
        console.print(f"\n[bold red]✗ 请求异常: {e}[/bold red]")


# ========== 主程序 ==========

def main():
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]DJI 无人机 RTMP 直播工具[/bold cyan]")
    console.print("=" * 60 + "\n")

    # 步骤 1: 选择无人机
    selected_uav = select_uav()

    # 步骤 2: 确认继续
    console.print("\n")
    confirm = Prompt.ask(
        "[bold yellow]是否继续建立连接?[/bold yellow]",
        choices=["y", "n"],
        default="y"
    )

    if confirm.lower() != 'y':
        console.print("[yellow]操作已取消[/yellow]")
        return

    # 步骤 3: 建立 DRC 连接
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

    video_id = None

    try:
        # 步骤 4: 等待相机数据
        wait_for_camera_data(mqtt, max_wait=10)

        # 步骤 5: 开始直播
        video_id = start_live(caller, mqtt)

        if video_id:
            # 步骤 6: 等待用户停止
            console.print("\n[bold yellow]直播运行中...[/bold yellow]")
            input("\n按 Enter 键停止直播并退出...")

            # 步骤 7: 停止直播
            stop_live(caller, video_id)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]收到中断信号[/yellow]")
        if video_id:
            stop_live(caller, video_id)

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
