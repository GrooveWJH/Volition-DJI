#!/usr/bin/env python3
"""
检测并打印遥控器上行的 drc_drone_state_push 消息。

运行示例：
    python control/drc_state_detector.py
"""

import json
import sys
import time
from dataclasses import dataclass
from typing import Optional

import paho.mqtt.client as mqtt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# ======== MQTT 基本配置（根据实际环境调整） ========
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USERNAME = "admin"
MQTT_PASSWORD = "302811055wjhhz"
GATEWAY_SN = "9N9CN2J0012CXY"
# ================================================

TOPIC_UP = f"thing/product/{GATEWAY_SN}/drc/up"
TARGET_METHOD = "drc_drone_state_push"

MODE_MAP = {
    0: "待机", 1: "起飞准备", 2: "起飞准备完毕", 3: "手动飞行", 4: "自动起飞",
    5: "航线飞行", 6: "全景拍照", 7: "智能跟随", 8: "ADS-B 躲避", 9: "自动返航",
    10: "自动降落", 11: "强制降落", 12: "三桨叶降落", 13: "升级中", 14: "未连接",
    15: "APAS", 16: "虚拟摇杆", 17: "指令飞行",
}

LANDING_TYPE_MAP = {0: "未降落", 1: "机场内降落", 2: "备降点降落", 3: "用户主动降落", 4: "飞行器触发降落"}
LANDING_PROTECTION_MAP = {
    0: "未开启检测", 1: "地面不平 / 水面，退出", 2: "未检测到地面，退出", 3: "机场内降落检测"
}


@dataclass
class DroneState:
    seq: int
    stealth_state: bool
    night_lights_state: bool
    mode_code: int
    landing_type: int
    landing_protection_type: int


class DrcStateDetector:
    def __init__(
        self,
        host: str,
        port: int,
        username: Optional[str],
        password: Optional[str],
        topic: str,
    ):
        self._console = Console()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._host = host
        self._port = port
        self._topic = topic
        self._last_seq: Optional[int] = None

    # ---- MQTT 回调 ----
    def _on_connect(self, client, _userdata, _flags, reason_code, _properties):
        readable = mqtt.connack_string(reason_code)
        self._console.print(f"[bold cyan]MQTT 连接 -> rc={reason_code} ({readable})[/]")
        if reason_code == 0:
            client.subscribe(self._topic)
            self._console.print(f"[bold green]已订阅 {self._topic}[/]")

    def _on_disconnect(self, _client, _userdata, disconnect_flags, reason_code, _properties):
        self._console.print(
            f"[bold yellow]MQTT 断开 -> rc={reason_code}, flags={disconnect_flags}[/]"
        )

    def _on_message(self, _client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            self._console.print(f"[bold red]收到无法解析的 payload：{msg.payload!r}[/]")
            return

        if payload.get("method") != TARGET_METHOD:
            return

        seq = payload.get("seq")
        data = payload.get("data") or {}

        try:
            state = DroneState(
                seq=int(seq),
                stealth_state=bool(data.get("stealth_state")),
                night_lights_state=bool(data.get("night_lights_state")),
                mode_code=int(data.get("mode_code")),
                landing_type=int(data.get("landing_type")),
                landing_protection_type=int(data.get("landing_protection_type")),
            )
        except (TypeError, ValueError):
            self._console.print(f"[bold red]收到字段缺失或类型异常的数据：{payload}[/]")
            return

        self._render_state(state)

    # ---- 渲染 ----
    def _render_state(self, state: DroneState) -> None:
        seq_status = self._check_seq(state.seq)

        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_row("隐蔽模式", "开启" if state.stealth_state else "关闭")
        table.add_row("夜航灯", "开启" if state.night_lights_state else "关闭")
        table.add_row("飞行模式", MODE_MAP.get(state.mode_code, f"未知({state.mode_code})"))
        table.add_row("降落类型", LANDING_TYPE_MAP.get(state.landing_type, f"未知({state.landing_type})"))
        table.add_row(
            "降落检测",
            LANDING_PROTECTION_MAP.get(
                state.landing_protection_type, f"未知({state.landing_protection_type})"
            ),
        )

        panel = Panel(
            table,
            title=f"[bold cyan]drc_drone_state_push[/]  seq=[bold]{state.seq}[/] {seq_status}",
            border_style="bright_magenta",
            padding=(1, 2),
        )
        self._console.print(panel)

    def _check_seq(self, current_seq: int) -> str:
        if self._last_seq is None:
            self._last_seq = current_seq
            return "[green]✓ 初始[/]"

        if current_seq <= self._last_seq:
            warning = f"[bold red]⚠ 序号未递增 (last={self._last_seq})[/]"
            self._last_seq = max(self._last_seq, current_seq)
            return warning

        lag = current_seq - self._last_seq
        self._last_seq = current_seq
        return f"[green]✓ +{lag}[/]"

    # ---- 外部接口 ----
    def run(self) -> int:
        try:
            self._client.connect(self._host, self._port, keepalive=60)
        except Exception as exc:
            self._console.print(f"[bold red]MQTT 连接失败：{exc}[/]")
            return 1

        self._console.print(
            "[bold green]等待上行 drc_drone_state_push 消息，按 Ctrl+C 退出。[/]"
        )

        try:
            self._client.loop_forever()
        except KeyboardInterrupt:
            self._console.print("\n[bold yellow]检测器终止。[/]")
        finally:
            try:
                self._client.disconnect()
            except Exception:
                pass

        return 0


def main() -> int:
    detector = DrcStateDetector(
        host=MQTT_HOST,
        port=MQTT_PORT,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        topic=TOPIC_UP,
    )
    return detector.run()


if __name__ == "__main__":
    sys.exit(main())
