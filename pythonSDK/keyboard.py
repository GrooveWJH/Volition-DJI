#!/usr/bin/env python3
"""
键盘控制测试工具 - 虚拟摇杆可视化（美国手模式）

功能：
- 在 CLI 中实时显示两个虚拟摇杆
- 根据键盘输入实时更新摇杆位置
- 显示杆量数值（364-1684，中值1024）

按键说明：
- J 键：满油门下（油门最小）
- K 键：外八解锁（左下右下，用于解锁无人机）
"""
import time
import argparse
from pynput import keyboard
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table

console = Console()

# 杆量常量
NEUTRAL = 1024
HALF_RANGE = 330
FULL_RANGE = 660
MIN_VALUE = 364
MAX_VALUE = 1684

# 当前杆量状态（美国手）
stick_state = {
    'throttle': NEUTRAL,  # 左摇杆 Y 轴：W/S
    'yaw': NEUTRAL,       # 左摇杆 X 轴：A/D
    'pitch': NEUTRAL,     # 右摇杆 Y 轴：↑/↓
    'roll': NEUTRAL,      # 右摇杆 X 轴：←/→
}

# 按键状态跟踪
pressed_keys = set()


def reset_sticks():
    """重置所有通道到中值"""
    stick_state['throttle'] = NEUTRAL
    stick_state['yaw'] = NEUTRAL
    stick_state['pitch'] = NEUTRAL
    stick_state['roll'] = NEUTRAL


def update_stick_from_keys():
    """根据当前按下的按键更新杆量"""
    reset_sticks()

    # 左摇杆 - 油门和偏航（美国手）
    if 'w' in pressed_keys:
        stick_state['throttle'] = NEUTRAL + HALF_RANGE
    if 's' in pressed_keys:
        stick_state['throttle'] = NEUTRAL - HALF_RANGE
    if 'a' in pressed_keys:
        stick_state['yaw'] = NEUTRAL - HALF_RANGE
    if 'd' in pressed_keys:
        stick_state['yaw'] = NEUTRAL + HALF_RANGE

    # 右摇杆 - 俯仰和横滚
    if 'up' in pressed_keys:
        stick_state['pitch'] = NEUTRAL + HALF_RANGE
    if 'down' in pressed_keys:
        stick_state['pitch'] = NEUTRAL - HALF_RANGE
    if 'left' in pressed_keys:
        stick_state['roll'] = NEUTRAL - HALF_RANGE
    if 'right' in pressed_keys:
        stick_state['roll'] = NEUTRAL + HALF_RANGE

    # K 键 - 外八解锁（左下右下）
    if 'k' in pressed_keys:
        stick_state['throttle'] = NEUTRAL - FULL_RANGE
        stick_state['yaw'] = NEUTRAL - FULL_RANGE
        stick_state['pitch'] = NEUTRAL - FULL_RANGE
        stick_state['roll'] = NEUTRAL + FULL_RANGE

    # J 键 - 满油门下（仅油门最小）
    if 'j' in pressed_keys:
        stick_state['throttle'] = NEUTRAL - FULL_RANGE


def render_joystick(x_value, y_value, x_label, y_label, title, scale=1.0):
    """
    渲染一个虚拟摇杆（十字形状，粗线条）

    Args:
        x_value: X 轴杆量值
        y_value: Y 轴杆量值
        x_label: X 轴标签
        y_label: Y 轴标签
        title: 摇杆标题
        scale: 显示比例 (0.5-2.0)
    """
    # 计算摇杆位置
    size = int(10 * scale)  # 摇杆半径（可调节）
    x_percent = ((x_value - NEUTRAL) / FULL_RANGE) * 100
    y_percent = ((y_value - NEUTRAL) / FULL_RANGE) * 100

    x_pos = int((x_percent / 100) * size)  # -size 到 +size
    y_pos = int((y_percent / 100) * size)  # -size 到 +size

    # 构建摇杆可视化（粗线条）
    lines = []
    for y in range(size, -size - 1, -1):
        line = ""
        for x in range(-size, size + 1):
            # 摇杆当前位置（3x3 粗点）
            if abs(x - x_pos) <= 1 and abs(y - y_pos) <= 1:
                if abs(x_percent) > 10 or abs(y_percent) > 10:
                    line += "█"  # 有偏移时用实心方块
                else:
                    line += "●"  # 中心时用圆点
            # 中心十字（粗线条）
            elif x == 0 and abs(y) <= 1:
                line += "┃"  # 垂直粗线
            elif y == 0 and abs(x) <= 1:
                line += "━"  # 水平粗线
            elif x == 0 and y == 0:
                line += "╋"  # 中心点
            # 边框
            elif (x == -size or x == size) and abs(y) <= size:
                line += "│"
            elif (y == -size or y == size) and abs(x) <= size:
                line += "─"
            # 四个角
            elif x == -size and y == size:
                line += "┌"
            elif x == size and y == size:
                line += "┐"
            elif x == -size and y == -size:
                line += "└"
            elif x == size and y == -size:
                line += "┘"
            else:
                line += " "
        lines.append(line)

    joystick_display = "\n".join(lines)

    # 数值显示（带颜色）
    x_diff = x_value - NEUTRAL
    y_diff = y_value - NEUTRAL

    x_color = "green" if x_diff > 0 else "red" if x_diff < 0 else "yellow"
    y_color = "green" if y_diff > 0 else "red" if y_diff < 0 else "yellow"

    content = (
        f"[bold cyan]{title}[/bold cyan]\n\n"
        f"{joystick_display}\n\n"
        f"[{x_color}]{x_label}: {x_value:4d} ({x_diff:+4d}) {x_percent:+6.1f}%[/{x_color}]\n"
        f"[{y_color}]{y_label}: {y_value:4d} ({y_diff:+4d}) {y_percent:+6.1f}%[/{y_color}]"
    )

    return Panel(content, border_style="cyan", padding=(1, 2))


def render_controls():
    """渲染控制说明"""
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("按键", style="cyan", width=12)
    table.add_column("功能", style="white", width=25)

    table.add_row("W / S", "左摇杆上/下（油门）")
    table.add_row("A / D", "左摇杆左/右（偏航）")
    table.add_row("↑ / ↓", "右摇杆上/下（俯仰）")
    table.add_row("← / →", "右摇杆左/右（横滚）")
    table.add_row("J", "满油门下")
    table.add_row("K", "外八解锁")
    table.add_row("空格", "重置到中值")
    table.add_row("ESC/Q", "退出程序")

    return Panel(table, title="🎮 控制说明", border_style="green")


def render_all_values():
    """渲染所有杆量的详细数值"""
    table = Table(show_header=True, header_style="bold yellow", box=None)
    table.add_column("通道", style="cyan", width=12)
    table.add_column("数值", style="white", width=10, justify="right")
    table.add_column("偏移", style="white", width=10, justify="right")
    table.add_column("百分比", style="white", width=10, justify="right")

    for name, key in [
        ("油门 (Throttle)", "throttle"),
        ("偏航 (Yaw)", "yaw"),
        ("俯仰 (Pitch)", "pitch"),
        ("横滚 (Roll)", "roll"),
    ]:
        value = stick_state[key]
        diff = value - NEUTRAL
        percentage = (diff / FULL_RANGE) * 100

        color = "green" if diff > 0 else "red" if diff < 0 else "yellow"

        table.add_row(
            name,
            f"[{color}]{value}[/{color}]",
            f"[{color}]{diff:+d}[/{color}]",
            f"[{color}]{percentage:+.1f}%[/{color}]"
        )

    return Panel(table, title="📊 杆量数值", border_style="yellow")


def render_pressed_keys():
    """显示当前按下的按键"""
    if pressed_keys:
        keys_text = ", ".join(sorted(pressed_keys))
        color = "green"
    else:
        keys_text = "无"
        color = "dim"

    return Panel(
        f"[{color}]{keys_text}[/{color}]",
        title="⌨️  当前按键",
        border_style="blue"
    )


def generate_layout(scale=1.0):
    """生成整体布局"""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=12)
    )

    # 主区域分为左右两个摇杆
    layout["main"].split_row(
        Layout(name="left_stick"),
        Layout(name="right_stick")
    )

    # 底部分为两个区域
    layout["footer"].split_row(
        Layout(name="controls"),
        Layout(name="keys")
    )

    # 填充内容
    layout["header"].update(Panel(
        "[bold cyan]🎮 虚拟摇杆测试工具（美国手模式）[/bold cyan]",
        border_style="cyan"
    ))

    layout["left_stick"].update(render_joystick(
        stick_state['yaw'],
        stick_state['throttle'],
        "偏航 (Yaw)",
        "油门 (Throttle)",
        "🕹️  左摇杆 (WASD)",
        scale=scale
    ))

    layout["right_stick"].update(render_joystick(
        stick_state['roll'],
        stick_state['pitch'],
        "横滚 (Roll)",
        "俯仰 (Pitch)",
        "🕹️  右摇杆 (方向键)",
        scale=scale
    ))

    layout["controls"].update(render_controls())
    layout["keys"].update(render_pressed_keys())

    return layout


def main():
    parser = argparse.ArgumentParser(description='虚拟摇杆测试工具')
    parser.add_argument('--scale', type=float, default=1.0, help='显示比例 (0.5-2.0, 默认1.0)')
    args = parser.parse_args()

    # 限制 scale 范围
    scale = max(0.5, min(2.0, args.scale))

    console.print(Panel.fit(
        "[bold green]启动虚拟摇杆测试工具...[/bold green]\n"
        f"[dim]显示比例: {scale}[/dim]",
        border_style="green"
    ))
    console.print("[dim]按 ESC 或 Q 键退出\n[/dim]")

    running = True

    def on_press(key):
        """按键按下事件"""
        nonlocal running
        try:
            if hasattr(key, 'char') and key.char:
                pressed_keys.add(key.char.lower())
            elif key == keyboard.Key.up:
                pressed_keys.add('up')
            elif key == keyboard.Key.down:
                pressed_keys.add('down')
            elif key == keyboard.Key.left:
                pressed_keys.add('left')
            elif key == keyboard.Key.right:
                pressed_keys.add('right')
            elif key == keyboard.Key.space:
                reset_sticks()
            elif key == keyboard.Key.esc:
                running = False
                return False
        except AttributeError:
            pass

    def on_release(key):
        """按键释放事件"""
        nonlocal running
        try:
            if hasattr(key, 'char') and key.char:
                pressed_keys.discard(key.char.lower())
            elif key == keyboard.Key.up:
                pressed_keys.discard('up')
            elif key == keyboard.Key.down:
                pressed_keys.discard('down')
            elif key == keyboard.Key.left:
                pressed_keys.discard('left')
            elif key == keyboard.Key.right:
                pressed_keys.discard('right')
        except AttributeError:
            pass

        if hasattr(key, 'char') and key.char and key.char.lower() == 'q':
            running = False
            return False

    # 启动键盘监听器（suppress=True 防止按键显示在终端）
    listener = keyboard.Listener(
        on_press=on_press,
        on_release=on_release,
        suppress=True  # 抑制按键输出到终端
    )
    listener.start()

    # 使用 Rich Live 实现实时刷新
    try:
        with Live(
            generate_layout(scale),
            console=console,
            refresh_per_second=20,
            screen=True  # 全屏模式，避免终端跳动
        ) as live:
            while running:
                # 更新杆量
                update_stick_from_keys()

                # 刷新布局
                live.update(generate_layout(scale))

                # 短暂休眠
                time.sleep(0.05)

    except KeyboardInterrupt:
        pass

    finally:
        listener.stop()
        console.print("\n[bold green]✓ 已退出[/bold green]")


if __name__ == '__main__':
    main()
