"""
IVAS 面板模块

负责生成 IVAS 相关面板，包括：
- IVAS 全局信息面板（运行状态、线程数量）
- 态势感知面板（占位，未来扩展）
"""
from typing import Optional
from rich.panel import Panel
from rich.table import Table


def create_ivas_global_panel(ivas_threads: Optional[list], elapsed: int) -> Panel:
    """
    创建 IVAS 全局信息面板

    显示：
    - IVAS 运行状态
    - 后台线程数量
    - 运行时间

    Args:
        ivas_threads: IVAS 后台线程列表（可选）
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

    # IVAS 运行状态
    is_running = ivas_threads is not None and len(ivas_threads) > 0
    status = "[bright_green]运行中[/bright_green]" if is_running else "[bright_red]未启用[/bright_red]"

    table.add_row("IVAS 状态:", status)
    table.add_row("运行时间:", f"[bright_green]{elapsed}[/bright_green] 秒")

    if is_running:
        add_separator()
        table.add_row("后台线程:", f"[bright_cyan]{len(ivas_threads)}[/bright_cyan] 个")

        # 显示线程名称
        table.add_row("[dim]活动线程:[/dim]", "")
        for thread in ivas_threads:
            if thread.is_alive():
                table.add_row("", f"[bright_green]● {thread.name}[/bright_green]")
            else:
                table.add_row("", f"[bright_red]○ {thread.name}[/bright_red]")
    else:
        add_separator()
        table.add_row("", "[dim]IVAS 系统未启用[/dim]")
        table.add_row("", "[dim]任务执行日志输出到控制台[/dim]")

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