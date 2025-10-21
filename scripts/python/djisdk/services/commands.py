"""
DJI 云端服务调用 - 统一接口

所有 DJI 服务的调用函数都在这里，通过通用包装消除重复代码。
"""
from typing import Dict, Any, Optional
from ..core import ServiceCaller
from rich.console import Console

console = Console()


def _call_service(
    caller: ServiceCaller,
    method: str,
    data: Optional[Dict[str, Any]] = None,
    success_msg: Optional[str] = None
) -> Dict[str, Any]:
    """
    通用服务调用包装 - 消除所有重复代码

    Args:
        caller: 服务调用器
        method: DJI 服务方法名
        data: 请求数据
        success_msg: 成功时的提示信息

    Returns:
        服务返回的数据字典

    Raises:
        Exception: 服务调用失败
    """
    try:
        result = caller.call(method, data or {})

        if result.get('result') == 0:
            if success_msg:
                console.print(f"[green]✓ {success_msg}[/green]")
            return result.get('data', {})
        else:
            error_msg = result.get('message', str(result))
            raise Exception(f"{method} 失败: {error_msg}")

    except Exception as e:
        console.print(f"[red]✗ {method}: {e}[/red]")
        raise


# ========== 控制权管理 ==========

def request_control_auth(
    caller: ServiceCaller,
    user_id: str = "default_user",
    user_callsign: str = "Cloud Pilot"
) -> Dict[str, Any]:
    """请求控制权"""
    console.print("[bold cyan]请求控制权...[/bold cyan]")
    return _call_service(
        caller,
        "cloud_control_auth_request",
        {
            "user_id": user_id,
            "user_callsign": user_callsign,
            "control_keys": ["flight"]
        },
        "控制权请求成功"
    )


def release_control_auth(caller: ServiceCaller) -> Dict[str, Any]:
    """释放控制权"""
    console.print("[cyan]释放控制权...[/cyan]")
    return _call_service(caller, "cloud_control_auth_release", success_msg="控制权已释放")


# ========== DRC 模式 ==========

def enter_drc_mode(
    caller: ServiceCaller,
    mqtt_broker: Dict[str, Any],
    osd_frequency: int = 30,
    hsi_frequency: int = 10
) -> Dict[str, Any]:
    """进入 DRC 模式"""
    console.print("[bold cyan]进入 DRC 模式...[/bold cyan]")
    result = _call_service(
        caller,
        "drc_mode_enter",
        {
            "mqtt_broker": mqtt_broker,
            "osd_frequency": osd_frequency,
            "hsi_frequency": hsi_frequency
        },
        f"已进入 DRC 模式 (OSD: {osd_frequency}Hz, HSI: {hsi_frequency}Hz)"
    )
    return result


def exit_drc_mode(caller: ServiceCaller) -> Dict[str, Any]:
    """退出 DRC 模式"""
    console.print("[cyan]退出 DRC 模式...[/cyan]")
    return _call_service(caller, "drc_mode_exit", success_msg="已退出 DRC 模式")


# ========== 直播控制 ==========

def change_live_lens(
    caller: ServiceCaller,
    video_id: str,
    video_type: str = "normal"
) -> Dict[str, Any]:
    """切换直播镜头"""
    console.print(f"[cyan]切换直播镜头: {video_id} ({video_type})[/cyan]")
    return _call_service(
        caller,
        "drc_live_lens_change",
        {"video_id": video_id, "video_type": video_type},
        f"镜头已切换到 {video_id}"
    )


def set_live_quality(caller: ServiceCaller, video_quality: int) -> Dict[str, Any]:
    """设置直播清晰度 (0-自适应, 1-流畅, 2-标清, 3-高清, 4-超清)"""
    quality_names = {0: "自适应", 1: "流畅", 2: "标清", 3: "高清", 4: "超清"}
    quality_name = quality_names.get(video_quality, "未知")
    console.print(f"[cyan]设置直播清晰度: {quality_name}[/cyan]")
    return _call_service(
        caller,
        "live_set_quality",
        {"video_quality": video_quality},
        f"清晰度已设置为 {quality_name}"
    )


def start_live_push(
    caller: ServiceCaller,
    url: str,
    video_id: str,
    url_type: int = 0,
    video_quality: int = 0
) -> Dict[str, Any]:
    """开始直播推流 (url_type: 0-RTMP, 1-RTSP, 2-GB28181)"""
    console.print(f"[bold cyan]开始直播推流...[/bold cyan]")
    console.print(f"[dim]URL: {url}[/dim]")
    console.print(f"[dim]镜头: {video_id}[/dim]")
    return _call_service(
        caller,
        "live_start_push",
        {
            "url": url,
            "video_id": video_id,
            "url_type": url_type,
            "video_quality": video_quality
        },
        "直播推流已开始"
    )


def stop_live_push(caller: ServiceCaller, video_id: str) -> Dict[str, Any]:
    """停止直播推流"""
    console.print(f"[cyan]停止直播推流: {video_id}[/cyan]")
    return _call_service(
        caller,
        "live_stop_push",
        {"video_id": video_id},
        "直播推流已停止"
    )


# ========== 扩展示例 ==========
# 添加新服务只需 1-2 行！

# def send_joystick(caller: ServiceCaller, pitch: float, roll: float, yaw: float, throttle: float) -> Dict[str, Any]:
#     """发送虚拟摇杆指令"""
#     return _call_service(caller, "drc_joystick", {"pitch": pitch, "roll": roll, "yaw": yaw, "throttle": throttle})

# def control_gimbal(caller: ServiceCaller, pitch: float, yaw: float) -> Dict[str, Any]:
#     """控制云台"""
#     return _call_service(caller, "drc_gimbal_control", {"pitch": pitch, "yaw": yaw})
