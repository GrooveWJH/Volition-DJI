#!/usr/bin/env python3
"""
DJI 无人机键盘控制脚本（美国手模式）

美国手布局：
- 左摇杆：W/S 控制油门（Throttle），A/D 控制偏航（Yaw）
- 右摇杆：↑/↓ 控制俯仰（Pitch），←/→ 控制横滚（Roll）
- J 键：满油门下（油门最小）
- K 键：外八解锁（左下右下，用于解锁无人机）
- 空格键：重置所有通道到中值（悬停）
- ESC/Q 键：退出程序

配置参数请直接修改下方的 CONFIG 字典
"""
import time
from pynput import keyboard as kb
from rich.console import Console
from rich.panel import Panel
from rich.live import Live

from djisdk import (
    MQTTClient, ServiceCaller,
    request_control_auth, enter_drc_mode,
    start_heartbeat, stop_heartbeat,
    send_stick_control
)

# 导入虚拟摇杆UI
from keyboard import generate_layout, pressed_keys, stick_state, reset_sticks, update_stick_from_keys

console = Console()

# ========== 配置参数（直接在这里修改）==========
CONFIG = {
    # MQTT 连接配置
    'gateway_sn': '9N9CN2J0012CXY',          # 默认 SN，将在启动时选择
    'mqtt_host': '192.168.8.155',                  # MQTT 服务器地址
    'mqtt_port': 1883,                       # MQTT 端口
    'mqtt_username': 'dji',                  # MQTT 用户名
    'mqtt_password': 'lab605605',            # MQTT 密码

    # 控制配置
    'frequency': 30.0,                       # 发送频率（Hz，推荐 5-10）
    'user_id': 'keyboard_pilot',             # 控制权用户 ID
    'user_callsign': 'Keyboard Pilot',       # 控制权呼号

    # DRC 模式配置
    'osd_frequency': 30,                     # OSD 频率（Hz）
    'hsi_frequency': 10,                     # HSI 频率（Hz）

    # UI 配置
    'ui_scale': 1.0,                         # 摇杆UI显示比例（0.5-2.0）
}

# 无人机 SN 列表
DRONE_SNS = {
    '1': '9N9CN2J0012CXY',  # 001
    '2': '9N9CN8400164WH',  # 002
    '3': '9N9CN180011TJN',  # 003
}
# ==============================================

# 杆量常量
NEUTRAL = 1024      # 中值
HALF_RANGE = 330    # 半杆量（1024 ± 330）
FULL_RANGE = 660    # 满杆量（1024 ± 660）


def main():
    # 提示用户选择无人机
    console.print("[bold yellow]请选择要控制的无人机 (1, 2, 3):[/bold yellow]", end=" ")
    choice = input()

    if choice in DRONE_SNS:
        CONFIG['gateway_sn'] = DRONE_SNS[choice]
        console.print(f"[bold green]✓ 已选择无人机 {choice} (SN: {CONFIG['gateway_sn']})[/bold green]\n")
    else:
        default_sn = DRONE_SNS['1']
        CONFIG['gateway_sn'] = default_sn
        console.print(f"[yellow]⚠ 无效选择 '{choice}'，将使用默认无人机 1 (SN: {default_sn})[/yellow]\n")

    console.print(Panel.fit(
        "[bold cyan]🚁 DJI 无人机键盘控制[/bold cyan]\n"
        f"[dim]SN: {CONFIG['gateway_sn']}[/dim]\n"
        f"[dim]MQTT: {CONFIG['mqtt_host']}:{CONFIG['mqtt_port']}[/dim]",
        border_style="cyan"
    ))

    # 1. 连接 MQTT
    console.print("[bold cyan]━━━ 步骤 1/4: 连接 MQTT ━━━[/bold cyan]")
    mqtt_config = {
        'host': CONFIG['mqtt_host'],
        'port': CONFIG['mqtt_port'],
        'username': CONFIG['mqtt_username'],
        'password': CONFIG['mqtt_password']
    }
    mqtt_client = MQTTClient(CONFIG['gateway_sn'], mqtt_config)
    try:
        mqtt_client.connect()
    except Exception as e:
        console.print(f"[red]✗ MQTT 连接失败: {e}[/red]")
        return 1
    
    caller = ServiceCaller(mqtt_client)

    # 询问用户是否已处于 DRC 模式
    console.print("\n[bold yellow]无人机是否已处于 DRC 模式？(y/n):[/bold yellow]", end=" ")
    in_drc_mode = input().lower() == 'y'

    if not in_drc_mode:
        # 2. 请求控制权
        console.print("\n[bold cyan]━━━ 步骤 2/4: 请求控制权 ━━━[/bold cyan]")
        try:
            request_control_auth(
                caller,
                user_id=CONFIG['user_id'],
                user_callsign=CONFIG['user_callsign']
            )
        except Exception as e:
            console.print(f"[red]✗ 控制权请求失败: {e}[/red]")
            mqtt_client.disconnect()
            return 1

        # 等待用户在遥控器上确认授权
        console.print("\n[bold green]控制权请求已发送，请在遥控器上点击确认授权。[/bold green]")
        console.print("[bold yellow]完成后在此处按回车继续...[/bold yellow]")
        try:
            input()
        except KeyboardInterrupt:
            console.print("\n[yellow]检测到中断，退出。[/yellow]")
            mqtt_client.disconnect()
            return 1
    else:
        console.print("[bold green]✓ 已跳过控制权请求和进入 DRC 模式。[/bold green]")

    if not in_drc_mode:
        # 3. 进入 DRC 模式
        console.print("\n[bold cyan]━━━ 步骤 3/4: 进入 DRC 模式 ━━━[/bold cyan]")
        drc_mqtt_broker = {
            'address': f"{CONFIG['mqtt_host']}:{CONFIG['mqtt_port']}",
            'client_id': 'drc-keyboard-control',
            'username': CONFIG['mqtt_username'],
            'password': CONFIG['mqtt_password'],
            'expire_time': int(time.time()) + 3600,  # 1小时后过期
            'enable_tls': False
        }
        enter_drc_mode(
            caller,
            mqtt_broker=drc_mqtt_broker,
            osd_frequency=CONFIG['osd_frequency'],
            hsi_frequency=CONFIG['hsi_frequency']
        )

    # 4. 启动心跳
    console.print("\n[bold cyan]━━━ 步骤 4/4: 启动心跳 ━━━[/bold cyan]")
    heartbeat_thread = start_heartbeat(mqtt_client, interval=0.2)

    console.print("\n[bold green]✓ 初始化完成！开始键盘控制...[/bold green]\n")

    # 键盘监听
    running = True

    def on_press(key):
        """按键按下事件"""
        try:
            if hasattr(key, 'char') and key.char:
                pressed_keys.add(key.char.lower())
            elif key == kb.Key.up:
                pressed_keys.add('up')
            elif key == kb.Key.down:
                pressed_keys.add('down')
            elif key == kb.Key.left:
                pressed_keys.add('left')
            elif key == kb.Key.right:
                pressed_keys.add('right')
            elif key == kb.Key.space:
                reset_sticks()
            elif key == kb.Key.esc:
                nonlocal running
                running = False
                return False
        except AttributeError:
            pass

    def on_release(key):
        """按键释放事件"""
        try:
            if hasattr(key, 'char') and key.char:
                pressed_keys.discard(key.char.lower())
            elif key == kb.Key.up:
                pressed_keys.discard('up')
            elif key == kb.Key.down:
                pressed_keys.discard('down')
            elif key == kb.Key.left:
                pressed_keys.discard('left')
            elif key == kb.Key.right:
                pressed_keys.discard('right')
        except AttributeError:
            pass

        # Q 键退出
        if hasattr(key, 'char') and key.char and key.char.lower() == 'q':
            nonlocal running
            running = False
            return False

    # 启动键盘监听器（suppress=True 防止按键显示在终端）
    listener = kb.Listener(
        on_press=on_press,
        on_release=on_release,
        suppress=True  # 抑制按键输出到终端，避免干扰显示
    )
    listener.start()

    # 主控制循环 - 使用 Live UI
    interval = 1.0 / CONFIG['frequency']
    ui_scale = CONFIG['ui_scale']

    try:
        with Live(
            generate_layout(scale=ui_scale),
            console=console,
            refresh_per_second=CONFIG['frequency'],
            screen=True  # 全屏模式，避免终端跳动
        ) as live:
            while running:
                start_time = time.perf_counter()

                # 更新杆量
                update_stick_from_keys()

                # 发送控制指令
                send_stick_control(
                    mqtt_client,
                    roll=stick_state['roll'],
                    pitch=stick_state['pitch'],
                    throttle=stick_state['throttle'],
                    yaw=stick_state['yaw']
                )

                # 更新UI显示
                live.update(generate_layout(scale=ui_scale))

                # 精确等待下一次发送
                elapsed = time.perf_counter() - start_time
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ 收到中断信号[/yellow]")

    finally:
        # 停止键盘监听
        listener.stop()

        # 清理资源
        console.print("\n[cyan]━━━ 清理资源 ━━━[/cyan]")

        # 发送悬停指令（安全措施）
        console.print("[yellow]发送悬停指令...[/yellow]")
        for _ in range(5):
            send_stick_control(mqtt_client)
            time.sleep(0.1)

        # 停止心跳
        stop_heartbeat(heartbeat_thread)

        # 断开连接
        mqtt_client.disconnect()

        console.print("[bold green]✓ 已安全退出[/bold green]")

    return 0


if __name__ == '__main__':
    exit(main())
