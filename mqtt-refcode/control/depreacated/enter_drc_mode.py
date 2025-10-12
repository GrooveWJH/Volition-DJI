#!/usr/bin/env python3
"""
发送 `drc_mode_enter` 指令，请求遥控器进入指令飞行控制模式。

配置好以下常量后，直接执行：
    python control/enter_drc_mode.py
"""

import json
import sys
import time
import uuid
from typing import Optional

import paho.mqtt.client as mqtt
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel


# ======== 配置区域 ========
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USERNAME = None  # 如果 broker 需要认证，填入用户名
MQTT_PASSWORD = None  # 如果 broker 需要认证，填入密码

# 遥控器（网关）序列号
GATEWAY_SN = "9N9CN8400164WH"

# DRC 模式所需的中继服务信息
MQTT_RELAY_ADDRESS = "192.168.31.240:1883"
MQTT_RELAY_CLIENT_ID = "drc-9N9CN8400164WH"
MQTT_RELAY_USERNAME = "admin"
MQTT_RELAY_PASSWORD = "302811055wjhhz"
MQTT_RELAY_EXPIRE_TIME = 1_700_000_000  # Unix 时间戳，单位秒
MQTT_RELAY_ENABLE_TLS = False

# 遥测上报频率
OSD_FREQUENCY = 30  # Hz，1-30
HSI_FREQUENCY = 10   # Hz，1-30

# 等待回复的最长时间（秒），None 则表示一直等待直到收到回复或手动终止
REPLY_TIMEOUT: Optional[float] = 15
# ======== 配置结束 ========


class DrcModeEnterClient:
    def __init__(
        self,
        host: str,
        port: int,
        gateway_sn: str,
        username: Optional[str],
        password: Optional[str],
        timeout: Optional[float],
    ):
        self._host = host
        self._port = port
        self._gateway_sn = gateway_sn
        self._timeout = timeout
        self._reply_topic = f"thing/product/{gateway_sn}/services_reply"
        self._tid = str(uuid.uuid4())
        self._bid = str(uuid.uuid4())
        self._response = None
        self._console = Console()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    @staticmethod
    def _json_panel(title: str, data: dict, style: str) -> Panel:
        return Panel(
            JSON.from_data(data, indent=2),
            title=title,
            title_align="left",
            border_style=style,
            padding=(1, 2),
        )

    def _log(self, level: str, message: str) -> None:
        styles = {
            "INFO": "bold cyan",
            "WARN": "bold yellow",
            "ERROR": "bold red",
        }
        style = styles.get(level, "white")
        self._console.print(f"[{style}]{level}[/] {message}")

    def _info(self, message: str) -> None:
        self._log("INFO", message)

    def _warn(self, message: str) -> None:
        self._log("WARN", message)

    def _error(self, message: str) -> None:
        self._log("ERROR", message)

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties):
        readable = mqtt.connack_string(reason_code)
        self._info(f"连接到 MQTT -> rc={reason_code} ({readable})")
        if reason_code == 0:
            client.subscribe(self._reply_topic)
            self._info(f"已订阅回复主题：{self._reply_topic}")

    def _on_disconnect(
        self, _client, _userdata, disconnect_flags, reason_code, _properties
    ):
        self._info(
            f"MQTT 连接已断开，rc={reason_code}, flags={disconnect_flags}"
        )

    def _on_message(self, _client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            self._warn(f"收到非 JSON 回复：{msg.payload!r}")
            return

        method = payload.get("method")
        data = payload.get("data") or {}
        result = data.get("result")

        self._info(f"收到回复 -> method={method}, result={result}")
        self._console.print(
            self._json_panel("Reply Payload", payload, "bright_magenta")
        )

        if payload.get("tid") == self._tid and method == "drc_mode_enter":
            self._response = payload

    def _build_payload(self) -> dict:
        return {
            "tid": self._tid,
            "bid": self._bid,
            "timestamp": int(time.time() * 1000),
            "method": "drc_mode_enter",
            "data": {
                "mqtt_broker": {
                    "address": MQTT_RELAY_ADDRESS,
                    "client_id": MQTT_RELAY_CLIENT_ID,
                    "username": MQTT_RELAY_USERNAME,
                    "password": MQTT_RELAY_PASSWORD,
                    "expire_time": MQTT_RELAY_EXPIRE_TIME,
                    "enable_tls": MQTT_RELAY_ENABLE_TLS,
                },
                "osd_frequency": OSD_FREQUENCY,
                "hsi_frequency": HSI_FREQUENCY,
            },
        }

    def run(self) -> int:
        try:
            self._client.connect(self._host, self._port, keepalive=60)
        except Exception as exc:
            self._error(f"无法连接 MQTT：{exc}")
            return 1

        self._client.loop_start()
        time.sleep(1)

        payload = self._build_payload()
        topic = f"thing/product/{self._gateway_sn}/services"
        result = self._client.publish(topic, json.dumps(payload), qos=1)
        self._info(
            "已发送 DRC 模式请求 -> topic=%s, mid=%s, rc=%s"
            % (topic, result.mid, result.rc)
        )
        self._console.print(
            self._json_panel("Request Payload", payload, "green")
        )

        start = time.time()
        try:
            while self._response is None:
                time.sleep(0.2)
                if (
                    self._timeout is not None
                    and time.time() - start >= self._timeout
                ):
                    self._warn(
                        f"超过 {self._timeout} 秒未收到回复，可检查遥控器是否在线或信息是否正确。"
                    )
                    break
        except KeyboardInterrupt:
            self._info("收到用户中断指令，停止等待。")

        self._client.loop_stop()
        self._client.disconnect()

        if self._response is None:
            self._warn("未获取到 `drc_mode_enter` 回复。")
            return 2

        result_code = (self._response.get("data") or {}).get("result")
        if result_code == 0:
            self._info("进入指令控制模式请求成功。")
            return 0

        hint = self._explain_result(result_code)
        self._warn(
            f"进入指令控制模式请求失败，result={result_code}"
            f"{' -> ' + hint if hint else ''}"
        )
        return 3

    @staticmethod
    def _explain_result(result: Optional[int]) -> Optional[str]:
        """根据常见错误码给出说明，未知结果返回 None。"""
        if result is None:
            return None

        explanations = {
            514304: "遥控器拒绝进入 DRC 模式或参数校验失败（请确认授权状态与中继凭证）。",
            100001: "请求参数不合法。",
            100101: "设备未在线或服务不可用。",
        }
        return explanations.get(result)


def main() -> int:
    client = DrcModeEnterClient(
        host=MQTT_HOST,
        port=MQTT_PORT,
        gateway_sn=GATEWAY_SN,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        timeout=REPLY_TIMEOUT,
    )
    return client.run()


if __name__ == "__main__":
    sys.exit(main())
