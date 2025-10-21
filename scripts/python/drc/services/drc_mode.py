"""
DRC 模式控制服务
"""
from typing import Dict, Any, Optional
from ..core import ServiceCaller
from rich.console import Console
from rich.table import Table

console = Console()


def enter_drc_mode(
    caller: ServiceCaller,
    mqtt_broker: Dict[str, Any],
    osd_frequency: int = 30,
    hsi_frequency: int = 10
) -> bool:
    """
    进入 DRC 模式

    Args:
        caller: 服务调用器
        mqtt_broker: MQTT 中继服务器配置，包含:
            - address: MQTT 服务器地址 (如 "127.0.0.1:1883")
            - client_id: 客户端 ID
            - username: 用户名
            - password: 密码
            - expire_time: 过期时间（Unix 时间戳）
            - enable_tls: 是否启用 TLS
        osd_frequency: OSD 数据推送频率（Hz，1-10）
        hsi_frequency: HSI 数据推送频率（Hz，1-10）

    Returns:
        是否成功进入 DRC 模式
    """
    console.print("[bold cyan]进入 DRC 模式...[/bold cyan]")

    data = {
        "mqtt_broker": mqtt_broker,
        "osd_frequency": osd_frequency,
        "hsi_frequency": hsi_frequency
    }

    try:
        result = caller.call("drc_mode_enter", data)

        if result.get('result') == 0:
            console.print("[green]✓ 已进入 DRC 模式[/green]")

            # 显示配置
            table = Table(title="DRC 配置")
            table.add_column("参数", style="cyan")
            table.add_column("值", style="green")
            table.add_row("OSD 频率", f"{osd_frequency} Hz")
            table.add_row("HSI 频率", f"{hsi_frequency} Hz")
            console.print(table)

            return True
        else:
            console.print(f"[red]✗ 进入 DRC 模式失败: {result}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 进入 DRC 模式异常: {e}[/red]")
        raise  # 让调用者决定如何处理异常


def exit_drc_mode(caller: ServiceCaller) -> bool:
    """
    退出 DRC 模式

    Args:
        caller: 服务调用器

    Returns:
        是否成功退出
    """
    console.print("[cyan]退出 DRC 模式...[/cyan]")

    try:
        result = caller.call("drc_mode_exit", {})

        if result.get('result') == 0:
            console.print("[green]✓ 已退出 DRC 模式[/green]")
            return True
        else:
            console.print(f"[yellow]退出 DRC 模式失败: {result}[/yellow]")
            return False

    except Exception as e:
        console.print(f"[yellow]退出 DRC 模式异常: {e}[/yellow]")
        raise  # 让调用者决定如何处理异常
