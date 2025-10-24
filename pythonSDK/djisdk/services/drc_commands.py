"""
DRC 无回包指令（Fire-and-forget 模式）

这些指令与普通服务不同：
- 使用 /drc/down topic（而非 /services）
- QoS 0，无响应回包
- 使用 seq 序列号（而非 tid）
- 调用方负责控制发送频率
"""
import json
import time
from ..core import MQTTClient
from rich.console import Console

console = Console()


def send_stick_control(
    mqtt_client: MQTTClient,
    roll: int = 1024,
    pitch: int = 1024,
    throttle: int = 1024,
    yaw: int = 1024,
    seq: int | None = None
) -> None:
    """
    发送 DRC 杆量控制指令（单次发送，调用方控制频率）

    Args:
        mqtt_client: MQTT 客户端
        roll: 横滚/左右平移 (364-1684, 中值1024)
        pitch: 俯仰/前后平移 (364-1684, 中值1024)
        throttle: 升降 (364-1684, 中值1024)
        yaw: 偏航/旋转 (364-1684, 中值1024)
        seq: 序列号（None 则自动生成时间戳）

    注意:
        - 无返回值（Fire-and-forget）
        - 调用方需自行控制频率（推荐 5-10Hz / 100-200ms 间隔）
        - 参数范围：364-1684，中值 1024（悬停/静止）

    示例:
        >>> # 单次发送
        >>> send_stick_control(mqtt, roll=1200, pitch=1024, yaw=1024, throttle=1024)
        >>>
        >>> # 循环控制（调用方负责频率）
        >>> for i in range(50):
        ...     send_stick_control(mqtt, roll=1200, pitch=1024, yaw=1024, throttle=1024)
        ...     time.sleep(0.1)  # 10Hz
    """
    # 参数校验
    for name, value in [("roll", roll), ("pitch", pitch), ("throttle", throttle), ("yaw", yaw)]:
        if not 364 <= value <= 1684:
            console.print(f"[red]✗ {name} 超出范围: {value} (应在 364-1684)[/red]")
            raise ValueError(f"{name} must be in range [364, 1684], got {value}")

    # 生成 seq
    if seq is None:
        seq = int(time.time() * 1000)

    # 构建消息
    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
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

    # 发送（QoS 0，无响应）
    try:
        mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
    except Exception as e:
        console.print(f"[red]✗ 杆量控制发送失败: {e}[/red]")
        raise
