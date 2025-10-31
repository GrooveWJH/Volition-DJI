"""
DJI 云端服务调用 - 统一接口

所有 DJI 服务的调用函数都在这里，通过通用包装消除重复代码。
"""
import time
import json
import threading
from typing import Dict, Any, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor
from ..core import ServiceCaller, MQTTClient
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


# ========== 飞行控制 ==========

def return_home(caller: ServiceCaller) -> Dict[str, Any]:
    """
    一键返航

    发送返航指令，无人机将自动返回起飞点。

    Args:
        caller: 服务调用器

    Returns:
        服务返回数据

    Example:
        >>> return_home(caller)
        [cyan]执行一键返航...[/cyan]
        [green]✓ 返航指令已发送[/green]
    """
    console.print("[cyan]执行一键返航...[/cyan]")
    return _call_service(caller, "return_home", data=None, success_msg="返航指令已发送")


# ========== DRC 杆量控制 ==========

def send_stick_control(
    mqtt_client: MQTTClient,
    roll: int = 1024,
    pitch: int = 1024,
    throttle: int = 1024,
    yaw: int = 1024
) -> None:
    """
    发送 DRC 杆量控制指令（无回包机制）

    建立DRC链路之后，可通过此指令控制飞行器姿态。
    发送频率需要保持5-10Hz，才能比较精准地控制飞行器的运动。

    Args:
        mqtt_client: MQTT 客户端（注意：不是 ServiceCaller）
        roll: 横滚通道 (364-1684, 中值1024)，控制左右平移
              增大向右倾斜，减小向左倾斜
        pitch: 俯仰通道 (364-1684, 中值1024)，控制前后平移
               增大向前俯冲，减小向后抬头
        throttle: 升降通道 (364-1684, 中值1024)，控制升降
                  增大升高，减小降低
        yaw: 偏航通道 (364-1684, 中值1024)，控制左右旋转
             增大顺时针旋转，减小逆时针旋转

    示例:
        >>> # 悬停（所有通道中值）
        >>> send_stick_control(mqtt)
        >>>
        >>> # 向前飞行
        >>> send_stick_control(mqtt, pitch=1354)  # 1024 + 330 (半杆)
        >>>
        >>> # 向左飞行
        >>> send_stick_control(mqtt, roll=694)  # 1024 - 330 (半杆)
    """
    # 参数验证
    if not (364 <= roll <= 1684):
        raise ValueError(f"roll 必须在 [364, 1684] 范围内，当前值: {roll}")
    if not (364 <= pitch <= 1684):
        raise ValueError(f"pitch 必须在 [364, 1684] 范围内，当前值: {pitch}")
    if not (364 <= throttle <= 1684):
        raise ValueError(f"throttle 必须在 [364, 1684] 范围内，当前值: {throttle}")
    if not (364 <= yaw <= 1684):
        raise ValueError(f"yaw 必须在 [364, 1684] 范围内，当前值: {yaw}")

    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    seq = int(time.time() * 1000)

    payload = {
        "seq": seq,
        "method": "stick_control",
        "data": {
            "roll": roll,
            "pitch": pitch,
            "throttle": throttle,
            "yaw": yaw
        }
    }

    # 发送控制指令（QoS 0，无回包机制）
    mqtt_client.client.publish(topic, json.dumps(payload), qos=0)


# ========== DRC 连接设置 ==========

def setup_drc_connection(
    gateway_sn: str,
    mqtt_config: Dict[str, Any],
    user_id: str = "pilot",
    user_callsign: str = "Callsign",
    osd_frequency: int = 30,
    hsi_frequency: int = 10,
    heartbeat_interval: float = 1.0,
    wait_for_user: bool = True
) -> Tuple[MQTTClient, ServiceCaller, threading.Thread]:
    """
    Setup complete DRC connection in one call.

    Steps:
    1. Connect MQTT
    2. Request control auth
    3. Wait for user confirmation (optional)
    4. Enter DRC mode
    5. Start heartbeat

    Args:
        gateway_sn: Gateway serial number
        mqtt_config: MQTT connection config (host, port, username, password)
        user_id: User ID for control auth
        user_callsign: User callsign for control auth
        osd_frequency: OSD data frequency (Hz)
        hsi_frequency: HSI data frequency (Hz)
        heartbeat_interval: Heartbeat interval (seconds)
        wait_for_user: Wait for user confirmation before entering DRC mode

    Returns:
        (mqtt_client, service_caller, heartbeat_thread)

    Example:
        >>> mqtt, caller, heartbeat = setup_drc_connection(
        ...     "1234567890ABC",
        ...     {'host': '172.20.10.2', 'port': 1883, 'username': 'admin', 'password': 'pass'}
        ... )
        >>> # Use mqtt, caller for commands
        >>> stop_heartbeat(heartbeat)
        >>> mqtt.disconnect()
    """
    from ..services.heartbeat import start_heartbeat
    import uuid

    console.print(f"[bold cyan]设置 DRC 连接: {gateway_sn}[/bold cyan]")

    # Step 1: Connect MQTT
    mqtt = MQTTClient(gateway_sn, mqtt_config)
    mqtt.connect()

    # Step 2: Create ServiceCaller
    caller = ServiceCaller(mqtt)

    try:
        # Step 3: Request control auth
        request_control_auth(caller, user_id=user_id, user_callsign=user_callsign)

        # Step 4: Wait for user (optional)
        if wait_for_user:
            input("🔔 请在 DJI Pilot APP 上允许控制权，然后按 Enter 继续...")

        # Step 5: Enter DRC mode (construct mqtt_broker config)
        # 添加3位随机UUID后缀，避免多实例冲突
        random_suffix = str(uuid.uuid4())[:3]
        mqtt_broker_config = {
            'address': f"{mqtt_config['host']}:{mqtt_config['port']}",
            'client_id': f"drc-{gateway_sn}-{random_suffix}",
            'username': mqtt_config['username'],
            'password': mqtt_config['password'],
            'expire_time': int(time.time()) + 3600,  # 1 hour expiry
            'enable_tls': mqtt_config.get('enable_tls', False)
        }
        enter_drc_mode(caller, mqtt_broker=mqtt_broker_config,
                      osd_frequency=osd_frequency, hsi_frequency=hsi_frequency)

        # Step 6: Start heartbeat
        heartbeat = start_heartbeat(mqtt, interval=heartbeat_interval)

        console.print("[bold green]✓ DRC 连接设置完成[/bold green]")
        return mqtt, caller, heartbeat

    except Exception as e:
        # Cleanup on failure
        console.print(f"[red]✗ 设置失败: {e}[/red]")
        mqtt.disconnect()
        raise


def setup_multiple_drc_connections(
    uav_configs: List[Dict[str, str]],
    mqtt_config: Dict[str, Any],
    osd_frequency: int = 30,
    hsi_frequency: int = 10,
    heartbeat_interval: float = 1.0,
    skip_drc_setup: bool = False
) -> List[Tuple[MQTTClient, ServiceCaller, threading.Thread]]:
    """
    Setup multiple DRC connections in parallel (3x faster than sequential).

    Optimizations:
    - Phase 1: Parallel MQTT connect + auth request
    - Phase 2: Single user confirmation for all UAVs
    - Phase 3: Parallel DRC mode enter + heartbeat start

    Args:
        uav_configs: List of UAV configs, each containing:
            - 'sn': Gateway serial number (required)
            - 'user_id': User ID (optional, default: 'pilot')
            - 'callsign': User callsign (optional, default: 'Callsign')
        mqtt_config: MQTT connection config (host, port, username, password)
        osd_frequency: OSD data frequency (Hz)
        hsi_frequency: HSI data frequency (Hz)
        heartbeat_interval: Heartbeat interval (seconds)
        skip_drc_setup: Skip control auth and DRC mode setup (only connect MQTT)

    Returns:
        List of (mqtt_client, service_caller, heartbeat_thread) tuples

    Example:
        >>> uav_configs = [
        ...     {'sn': 'SN1', 'user_id': 'pilot1', 'callsign': 'Alpha'},
        ...     {'sn': 'SN2', 'user_id': 'pilot2', 'callsign': 'Bravo'},
        ... ]
        >>> connections = setup_multiple_drc_connections(uav_configs, mqtt_config)
        >>> # Use connections...
        >>> for mqtt, caller, heartbeat in connections:
        ...     stop_heartbeat(heartbeat)
        ...     mqtt.disconnect()
    """
    from ..services.heartbeat import start_heartbeat

    if skip_drc_setup:
        console.print(f"[bold yellow]仅连接 MQTT ({len(uav_configs)} 架无人机)[/bold yellow]")
        console.print("[dim]跳过控制权请求和 DRC 模式设置[/dim]\n")

        # 只建立 MQTT 连接，不请求控制权和 DRC 模式
        connections = []
        for config in uav_configs:
            sn = config['sn']
            console.print(f"[cyan]连接 {sn}...[/cyan]")

            mqtt = MQTTClient(sn, mqtt_config)
            mqtt.connect()
            caller = ServiceCaller(mqtt)

            # 不启动心跳（因为没有进入 DRC 模式）
            # 创建一个空的 MockHeartbeatThread 占位
            from ..mock.mock_drone import MockHeartbeatThread
            heartbeat = MockHeartbeatThread()

            connections.append((mqtt, caller, heartbeat))
            console.print(f"[green]✓ {sn} MQTT 已连接[/green]")

        console.print(f"\n[bold green]✓ 所有 MQTT 连接已建立 ({len(connections)} 架)[/bold green]\n")
        return connections

    # 正常的 DRC 连接流程
    console.print(f"[bold cyan]并行设置 {len(uav_configs)} 架无人机的 DRC 连接[/bold cyan]\n")

    # Phase 1: Parallel connect + auth request
    def phase1_connect_and_auth(config):
        sn = config['sn']
        user_id = config.get('user_id', 'pilot')
        callsign = config.get('callsign', 'Callsign')

        console.print(f"[dim]连接 {sn}...[/dim]")
        mqtt = MQTTClient(sn, mqtt_config)
        mqtt.connect()
        caller = ServiceCaller(mqtt)
        request_control_auth(caller, user_id=user_id, user_callsign=callsign)

        return (sn, mqtt, caller)

    with ThreadPoolExecutor() as executor:
        phase1_results = list(executor.map(phase1_connect_and_auth, uav_configs))

    console.print(f"\n[green]✓ 已请求 {len(phase1_results)} 架无人机的控制权[/green]")

    # Phase 2: Wait for user (single input for all)
    input("\n🔔 请在 DJI Pilot APP 上允许所有无人机的控制权，然后按 Enter 继续...\n")

    # Phase 3: Parallel enter DRC + start heartbeat
    def phase3_enter_drc_and_heartbeat(result):
        import uuid
        sn, mqtt, caller = result

        console.print(f"[dim]设置 {sn} DRC 模式...[/dim]")
        # 添加3位随机UUID后缀，避免多实例冲突
        random_suffix = str(uuid.uuid4())[:3]
        mqtt_broker_config = {
            'address': f"{mqtt_config['host']}:{mqtt_config['port']}",
            'client_id': f"drc-{sn}-{random_suffix}",
            'username': mqtt_config['username'],
            'password': mqtt_config['password'],
            'expire_time': int(time.time()) + 3600,  # 1 hour expiry
            'enable_tls': mqtt_config.get('enable_tls', False)
        }
        enter_drc_mode(caller, mqtt_broker=mqtt_broker_config,
                      osd_frequency=osd_frequency, hsi_frequency=hsi_frequency)
        heartbeat = start_heartbeat(mqtt, interval=heartbeat_interval)

        return (mqtt, caller, heartbeat)

    with ThreadPoolExecutor() as executor:
        connections = list(executor.map(phase3_enter_drc_and_heartbeat, phase1_results))

    console.print(f"\n[bold green]✓ 所有无人机 DRC 连接设置完成 ({len(connections)} 架)[/bold green]\n")
    return connections


# ========== 扩展示例 ==========
# 添加新服务只需 1-2 行！

# def send_joystick(caller: ServiceCaller, pitch: float, roll: float, yaw: float, throttle: float) -> Dict[str, Any]:
#     """发送虚拟摇杆指令"""
#     return _call_service(caller, "drc_joystick", {"pitch": pitch, "roll": roll, "yaw": yaw, "throttle": throttle})

# def control_gimbal(caller: ServiceCaller, pitch: float, yaw: float) -> Dict[str, Any]:
#     """控制云台"""
#     return _call_service(caller, "drc_gimbal_control", {"pitch": pitch, "yaw": yaw})
