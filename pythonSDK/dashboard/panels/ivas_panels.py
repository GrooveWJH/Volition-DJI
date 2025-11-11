"""
IVAS 面板模块

负责生成 IVAS 相关面板，包括：
- IVAS 全局信息面板（任务接收、统计信息、DEBUG消息）
- 态势感知面板（占位，未来扩展）
"""
from typing import List
from rich.panel import Panel
from rich.table import Table
from ..ivas_debug import debug_manager


def create_ivas_global_panel(ivas_adapters: List, elapsed: int) -> Panel:
    """
    创建 IVAS 全局信息面板

    显示：
    - IVAS 连接状态
    - 最新接收的任务
    - 统计信息

    Args:
        ivas_adapters: IVAS 适配器列表
        elapsed: 运行时间（秒）

    Returns:
        Rich Panel 对象
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_blue", justify="right")
    table.add_column(style="bold bright_white")

    # 分割线函数
    def add_separator():
        table.add_row("", "[dim]" + "─" * 30 + "[/dim]")

    # 标题 - 前卫配色：霓虹色系
    table.add_row("IVAS 状态:", "[bright_green]运行中[/bright_green]" if ivas_adapters else "[bright_red]未启用[/bright_red]")
    table.add_row("运行时间:", f"[bright_green]{elapsed}[/bright_green] 秒")
    add_separator()

    # 统计信息 - 前卫配色：亮青色数据
    table.add_row("在线设备:", f"[bright_cyan]{len(ivas_adapters)}[/bright_cyan] 个")
    add_separator()

    # 任务接收信息（汇总所有adapter的最新任务）
    table.add_row("[bold]最新任务:[/bold]", "")

    mission_names = {
        1: "原地起飞5米", 2: "原地降落", 3: "返航", 4: "前往指定点",
        5: "多航点任务1", 6: "多航点任务2", 7: "多航点任务3"
    }

    has_task = False
    for adapter in ivas_adapters:
        task = adapter.get_latest_task()
        if task:
            has_task = True
            mission = task.get('mission', 0)
            mission_name = mission_names.get(mission, f"未知任务({mission})")
            target_id = task.get('id', 0)

            # 显示任务信息 - 前卫配色：亮洋红任务 + 亮青ID
            table.add_row("  任务类型:", f"[bright_magenta]{mission_name}[/bright_magenta]")
            table.add_row("  目标ID:", f"[bright_cyan]{target_id}[/bright_cyan]")

            # 如果是前往指定点任务，显示坐标
            if mission == 4:
                lat = task.get('lat', 0)
                lon = task.get('lon', 0)
                alt = task.get('alt', 0)
                table.add_row("  目标坐标:", f"({lat:.6f}, {lon:.6f}, {alt:.1f})")

            break  # 只显示第一个有任务的adapter

    if not has_task:
        table.add_row("", "[dim]暂无任务[/dim]")

    # DEBUG 消息区域
    add_separator()
    table.add_row("[bold bright_yellow]DEBUG 消息:[/bold bright_yellow]", "")

    debug_messages = debug_manager.get_recent_messages(n=20)
    if debug_messages:
        for msg in debug_messages:
            callsign = msg['callsign']
            message = msg['message']
            msg_type = msg['type']

            # 根据消息类型设置颜色
            if msg_type == 'error' or '❌' in message:
                color = 'bright_red'
            elif '✅' in message:
                color = 'bright_green'
            elif '🔍' in message:
                color = 'bright_yellow'
            else:
                color = 'bright_white'

            # 格式化显示：[Pilot 1] 消息内容
            table.add_row("", f"[{color}][{callsign}] {message}[/{color}]")
    else:
        table.add_row("", "[dim]暂无 DEBUG 消息[/dim]")

    return Panel(
        table,
        title="[bold bright_cyan]IVAS 全局信息[/bold bright_cyan]",
        border_style="bright_cyan",
        padding=(1, 2)
    )


def create_situation_awareness_panel() -> Panel:
    """
    创建态势感知面板（留白，暂不实现）

    占位面板，用于未来扩展。

    Returns:
        Rich Panel 对象
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold bright_yellow")

    table.add_row("[dim]功能开发中...[/dim]")
    table.add_row("")
    table.add_row("[dim]态势感知数据源尚未接入[/dim]")
    table.add_row("")
    table.add_row("[dim]未来将显示：[/dim]")
    table.add_row("[dim]- 目标检测信息[/dim]")
    table.add_row("[dim]- 威胁评估[/dim]")
    table.add_row("[dim]- 环境态势[/dim]")

    return Panel(
        table,
        title="[bold bright_yellow]态势感知[/bold bright_yellow]",
        border_style="bright_yellow",
        padding=(1, 2)
    )