#!/usr/bin/env python3
"""
室内场地端程序

功能：
1. 发布 UWB 位置数据到 MQTT（uwb/position）[可选]
2. 订阅并接收任务指令（ivas/task/command），仅处理 mission=1
3. 接收到任务时播报"任务开始"

使用方法：
    python indoor_playground.py
"""

import json
import time
from rich.console import Console

import paho.mqtt.client as mqtt
import pyttsx3

console = Console()

# ========== 配置段 ==========

# 功能开关
ENABLE_UWB_PUBLISH = False               # 是否启用 UWB 发布功能

# MQTT 配置
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# UWB 配置（仅在 ENABLE_UWB_PUBLISH=True 时使用）
UWB_NODE_ID = 0                         # UWB 节点 ID
UWB_PUBLISH_TOPIC = 'uwb/position'      # UWB 数据发布主题
UWB_PUBLISH_RATE_HZ = 50                # 发布频率（Hz）

# 任务订阅配置
TASK_SUBSCRIBE_TOPIC = 'ivas/task/command'  # 任务指令订阅主题

# MQTT 客户端 ID
CLIENT_ID = f'playground-{int(time.time())}'

# ========== 语音播报初始化 ==========

def init_tts_engine():
    """初始化文本转语音引擎"""
    try:
        engine = pyttsx3.init()

        # 调整语速和音量
        rate = engine.getProperty('rate')
        engine.setProperty('rate', rate - 50)  # 减慢语速
        engine.setProperty('volume', 1.0)      # 最大音量

        # 查找并设置中文语音
        voices = engine.getProperty('voices')
        chinese_voice_id = None

        for v in voices:
            for lang in v.languages:
                if lang.lower().startswith('zh'):
                    chinese_voice_id = v.id
                    console.print(f"[dim]找到中文语音: {v.name} ({lang})[/dim]")
                    break
            if chinese_voice_id:
                break

        if chinese_voice_id:
            engine.setProperty('voice', chinese_voice_id)
        else:
            console.print("[yellow]⚠ 未找到中文语音包，将使用默认语音[/yellow]")

        return engine
    except Exception as e:
        console.print(f"[red]✗ 语音引擎初始化失败: {e}[/red]")
        return None

tts_engine = init_tts_engine()

# ========== MQTT 回调函数 ==========

def on_connect(client, userdata, flags, rc):
    """连接回调"""
    if rc == 0:
        console.print(f"[green]✓ 已连接到 MQTT Broker[/green]")
        # 订阅任务主题
        client.subscribe(TASK_SUBSCRIBE_TOPIC, qos=1)
        console.print(f"[green]✓ 已订阅任务主题: {TASK_SUBSCRIBE_TOPIC}[/green]")
    else:
        console.print(f"[red]✗ 连接失败，错误码: {rc}[/red]")


def on_task_message(client, userdata, msg):
    """任务消息回调"""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))

        # 解析任务信息
        task_id = payload.get('task_id', '?')
        mission_type = payload.get('mission_type', 0)
        mission_name = payload.get('mission_name', '未知')
        received_at = payload.get('received_at', '?')

        # 只处理 mission=1
        if mission_type == 1:
            console.print("\n" + "="*60)
            console.print(f"[bold green]🎯 接收到起飞指令！[/bold green]")
            console.print(f"  任务ID: {task_id}")
            console.print(f"  任务类型: mission={mission_type} ({mission_name})")
            console.print(f"  接收时间: {received_at}")
            console.print("="*60)
            console.print(json.dumps(payload, indent=2, ensure_ascii=False))
            console.print("="*60 + "\n")

            # 播报语音
            if tts_engine:
                console.print("[bold cyan]🔊 播报: 任务开始[/bold cyan]")
                try:
                    tts_engine.say("任务开始开始开始")
                    tts_engine.runAndWait()
                except Exception as e:
                    console.print(f"[red]✗ 语音播报失败: {e}[/red]")

            # TODO: 在这里添加实际的起飞控制逻辑
            console.print("[yellow]>> 执行起飞动作（待实现）[/yellow]\n")
        else:
            console.print(f"[dim]收到非起飞任务 (mission={mission_type})，忽略[/dim]")

    except Exception as e:
        console.print(f"[red]✗ 任务消息解析失败: {e}[/red]")


# ========== 主程序 ==========

def main():
    """主函数"""
    console.print("\n[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]")
    console.print("[bold bright_cyan]       室内场地端程序[/bold bright_cyan]")
    console.print("[bold bright_cyan]       UWB 发布 + 任务接收 + 语音播报[/bold bright_cyan]")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    # 打印配置信息
    console.print(f"[bold]📋 配置信息[/bold]")
    console.print(f"  MQTT Broker: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}")
    console.print(f"  UWB 发布功能: {'[green]✓ 已启用[/green]' if ENABLE_UWB_PUBLISH else '[yellow]✗ 已禁用[/yellow]'}")
    if ENABLE_UWB_PUBLISH:
        console.print(f"  UWB 发布主题: {UWB_PUBLISH_TOPIC}")
        console.print(f"  UWB 发布频率: {UWB_PUBLISH_RATE_HZ} Hz")
    console.print(f"  任务订阅主题: {TASK_SUBSCRIBE_TOPIC}")
    console.print(f"  语音播报: {'[green]✓ 已启用[/green]' if tts_engine else '[yellow]✗ 不可用[/yellow]'}")
    console.print()

    # 1. 初始化 UWB 客户端（可选）
    uwb_client = None
    if ENABLE_UWB_PUBLISH:
        console.print("[bold]📍 步骤 1: 初始化 UWB 客户端[/bold]")
        try:
            from uwb.uwb_client import UWBClient
            uwb_client = UWBClient(target_node_id=UWB_NODE_ID, use_smoothing=True)
            console.print(f"[bright_green]✓ UWB 客户端已初始化 (Node ID: {UWB_NODE_ID})[/bright_green]")
        except Exception as e:
            console.print(f"[red]✗ UWB 客户端初始化失败: {e}[/red]")
            console.print("[yellow]⚠ 将继续运行，但不发布 UWB 数据[/yellow]")
            uwb_client = None
        console.print()
    else:
        console.print("[yellow]📍 步骤 1: 跳过 UWB 初始化（已禁用）[/yellow]\n")

    # 2. 连接 MQTT
    console.print("[bold]🔌 步骤 2: 连接 MQTT Broker[/bold]")
    mqtt_client = mqtt.Client(client_id=CLIENT_ID)
    mqtt_client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_task_message

    try:
        mqtt_client.connect(MQTT_CONFIG['host'], MQTT_CONFIG['port'], 60)
    except Exception as e:
        console.print(f"[red]✗ MQTT 连接失败: {e}[/red]")
        if uwb_client:
            uwb_client.stop()
        return

    mqtt_client.loop_start()
    time.sleep(0.5)  # 等待连接建立
    console.print()

    # 3. 运行主循环
    console.print("[bold green]✅ 系统就绪[/bold green]")
    console.print("[dim]按 Ctrl+C 退出[/dim]\n")
    console.print("[bold bright_cyan]" + "="*60 + "[/bold bright_cyan]\n")

    publish_interval = 1.0 / UWB_PUBLISH_RATE_HZ if ENABLE_UWB_PUBLISH else 0
    last_publish_time = time.time()
    msg_count = 0

    try:
        while True:
            current_time = time.time()

            # 发布 UWB 数据（如果启用）
            if ENABLE_UWB_PUBLISH and uwb_client and (current_time - last_publish_time >= publish_interval):
                pos = uwb_client.get_position()

                if pos:
                    x, y, z = pos
                    msg_count += 1

                    # 构造 JSON 消息
                    message = {
                        'node_id': UWB_NODE_ID,
                        'timestamp': round(current_time, 3),
                        'position': {
                            'x': round(x, 4),
                            'y': round(y, 4),
                            'z': round(z, 4)
                        }
                    }

                    # 发布到 MQTT
                    payload = json.dumps(message)
                    result = mqtt_client.publish(UWB_PUBLISH_TOPIC, payload, qos=0)

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        # 仅打印前 10 条消息
                        if msg_count <= 10:
                            console.print(
                                f"[green]✓[/green] [[cyan]{msg_count:05d}[/cyan]] "
                                f"UWB 发布: x={x:7.4f}, y={y:7.4f}, z={z:7.4f}",
                                end='\r'
                            )
                        else:
                            # 后续仅更新计数
                            console.print(
                                f"[dim]UWB 发布中... (已发布 {msg_count} 条)[/dim]",
                                end='\r'
                            )

                    last_publish_time = current_time

            time.sleep(0.001)  # 1ms 睡眠

    except KeyboardInterrupt:
        console.print(f"\n\n[yellow]⚠️  接收到中断信号，正在退出...[/yellow]")

    finally:
        console.print(f"\n[bold]🧹 清理资源...[/bold]")

        if ENABLE_UWB_PUBLISH and msg_count > 0:
            console.print(f"[cyan]总共发布了 {msg_count} 条 UWB 消息[/cyan]")

        if uwb_client:
            uwb_client.stop()
            console.print("[green]✓ UWB 客户端已停止[/green]")

        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        console.print("[green]✓ MQTT 已断开[/green]")

        console.print("[bold green]✅ 程序已退出[/bold green]\n")


if __name__ == '__main__':
    main()
