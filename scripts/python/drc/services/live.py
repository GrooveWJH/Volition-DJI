"""
直播控制服务
"""
from typing import Dict, Any
from ..core import ServiceCaller
from rich.console import Console

console = Console()


def change_live_lens(caller: ServiceCaller, video_id: str, video_type: str) -> bool:
    """
    切换直播镜头

    Args:
        caller: 服务调用器
        video_id: 镜头 ID（如 "52-0-0"）
        video_type: 镜头类型（如 "normal"）

    Returns:
        是否成功切换
    """
    console.print(f"[cyan]切换直播镜头: {video_id} ({video_type})[/cyan]")

    data = {
        "video_id": video_id,
        "video_type": video_type
    }

    try:
        result = caller.call("drc_live_lens_change", data)

        if result.get('result') == 0:
            console.print(f"[green]✓ 镜头已切换到: {video_id}[/green]")
            return True
        else:
            console.print(f"[red]✗ 镜头切换失败: {result}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 镜头切换异常: {e}[/red]")
        raise  # 让调用者决定如何处理异常


def set_live_quality(caller: ServiceCaller, video_quality: int) -> bool:
    """
    设置直播清晰度

    Args:
        caller: 服务调用器
        video_quality: 清晰度等级（0-适应, 1-流畅, 2-标清, 3-高清, 4-超清）

    Returns:
        是否成功设置
    """
    quality_names = {
        0: "自适应",
        1: "流畅",
        2: "标清",
        3: "高清",
        4: "超清"
    }

    quality_name = quality_names.get(video_quality, "未知")
    console.print(f"[cyan]设置直播清晰度: {quality_name}[/cyan]")

    data = {"video_quality": video_quality}

    try:
        result = caller.call("live_set_quality", data)

        if result.get('result') == 0:
            console.print(f"[green]✓ 清晰度已设置为: {quality_name}[/green]")
            return True
        else:
            console.print(f"[red]✗ 设置清晰度失败: {result}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 设置清晰度异常: {e}[/red]")
        raise  # 让调用者决定如何处理异常


def start_live_push(caller: ServiceCaller, url: str, video_id: str) -> bool:
    """
    开始直播推流

    Args:
        caller: 服务调用器
        url: 推流 URL (rtmp://...)
        video_id: 镜头 ID

    Returns:
        是否成功开始推流
    """
    console.print(f"[bold cyan]开始直播推流...[/bold cyan]")
    console.print(f"[dim]URL: {url}[/dim]")
    console.print(f"[dim]镜头: {video_id}[/dim]")

    data = {
        "url": url,
        "video_id": video_id,
        "url_type": 0,  # 0-RTMP, 1-RTSP, 2-GB28181
        "video_quality": 0  # 自适应
    }

    try:
        result = caller.call("live_start_push", data)

        if result.get('result') == 0:
            console.print("[green]✓ 直播推流已开始[/green]")
            return True
        else:
            console.print(f"[red]✗ 开始推流失败: {result}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 开始推流异常: {e}[/red]")
        raise  # 让调用者决定如何处理异常


def stop_live_push(caller: ServiceCaller, video_id: str) -> bool:
    """
    停止直播推流

    Args:
        caller: 服务调用器
        video_id: 镜头 ID

    Returns:
        是否成功停止推流
    """
    console.print(f"[cyan]停止直播推流: {video_id}[/cyan]")

    data = {"video_id": video_id}

    try:
        result = caller.call("live_stop_push", data)

        if result.get('result') == 0:
            console.print("[green]✓ 直播推流已停止[/green]")
            return True
        else:
            console.print(f"[yellow]停止推流失败: {result}[/yellow]")
            return False

    except Exception as e:
        console.print(f"[yellow]停止推流异常: {e}[/yellow]")
        raise  # 让调用者决定如何处理异常
