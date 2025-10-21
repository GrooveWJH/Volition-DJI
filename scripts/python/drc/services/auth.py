"""
控制权请求服务
"""
from typing import Dict, Any
from ..core import ServiceCaller
from rich.console import Console

console = Console()


def request_control_auth(
    caller: ServiceCaller,
    user_id: str = "default_user",
    user_callsign: str = "Cloud Pilot"
) -> bool:
    """
    请求控制权

    Args:
        caller: 服务调用器
        user_id: 用户 ID
        user_callsign: 用户呼号（显示在遥控器上）

    Returns:
        是否成功获取控制权
    """
    console.print("[bold cyan]请求控制权...[/bold cyan]")

    data = {
        "user_id": user_id,
        "user_callsign": user_callsign,
        "control_keys": ["flight"]  # 请求飞行控制权
    }

    try:
        result = caller.call("cloud_control_auth_request", data)

        if result.get('result') == 0:
            console.print("[green]✓ 控制权请求成功[/green]")
            return True
        else:
            console.print(f"[red]✗ 控制权请求失败: {result}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 控制权请求异常: {e}[/red]")
        raise  # 让调用者决定如何处理异常


def release_control_auth(caller: ServiceCaller) -> bool:
    """
    释放控制权

    Args:
        caller: 服务调用器

    Returns:
        是否成功释放
    """
    console.print("[cyan]释放控制权...[/cyan]")

    try:
        result = caller.call("cloud_control_auth_release", {})
        console.print("[green]✓ 控制权已释放[/green]")
        return True

    except Exception as e:
        console.print(f"[yellow]释放控制权异常: {e}[/yellow]")
        raise  # 让调用者决定如何处理异常
