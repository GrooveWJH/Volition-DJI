#!/usr/bin/env python3
"""
向本地/指定 MQTT Broker 发送云端控制权请求。

配置后直接运行 python request_control.py 即可。
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

GATEWAY_SN = "9N9CN8400164WH"
USER_ID = "groove"
USER_CALLSIGN = "groove"

# 等待回复的最长时间（秒），设置为 None 表示持续监听直到出现终止状态或手动退出
REPLY_TIMEOUT = None
# ======== 配置结束 ========


class ControlRequestClient:
    def __init__(
        self,
        host: str,
        port: int,
        gateway_sn: str,
        user_id: str,
        user_callsign: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._host = host
        self._port = port
        self._gateway_sn = gateway_sn
        self._user_id = user_id
        self._user_callsign = user_callsign
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
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

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
        palette = {
            "INFO": "bold cyan",
            "WARN": "bold yellow",
            "ERROR": "bold red",
        }
        style = palette.get(level, "white")
        self._console.print(f"[{style}]{level}[/] {message}")

    def _info(self, message: str) -> None:
        self._log("INFO", message)

    def _warn(self, message: str) -> None:
        self._log("WARN", message)

    def _error(self, message: str) -> None:
        self._log("ERROR", message)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        readable = mqtt.connack_string(reason_code)
        self._info(f"连接到 MQTT -> rc={reason_code} ({readable})")
        if reason_code == 0:
            client.subscribe(self._reply_topic)
            self._info(f"已订阅回复主题：{self._reply_topic}")

    def _on_disconnect(
        self, _client, _userdata, disconnect_flags, reason_code, properties
    ):
        self._info(f"MQTT 连接已断开，rc={reason_code}, flags={disconnect_flags}")

    def _render_reply(self, payload: dict) -> None:
        self._console.print(
            self._json_panel("Reply Payload", payload, "bright_magenta")
        )

    def _on_message(self, _client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            self._warn(f"收到无法解析的回复：{msg.payload!r}")
            return

        data = payload.get("data") or {}
        result_code = data.get("result")
        status = (data.get("output") or {}).get("status")

        self._info(
            "收到服务回复 -> "
            f"result={result_code}, status={status}, payload="
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        self._render_reply(payload)

        if payload.get("tid") == self._tid:
            self._response = payload

    def run(self) -> int:
        try:
            self._client.connect(self._host, self._port, keepalive=60)
        except Exception as exc:
            self._error(f"无法连接 MQTT：{exc}")
            return 1

        self._client.loop_start()
        time.sleep(1)  # 等待连接建立

        request = {
            "tid": self._tid,
            "bid": self._bid,
            "timestamp": int(time.time() * 1000),
            "method": "cloud_control_auth_request",
            "data": {
                "user_id": self._user_id,
                "user_callsign": self._user_callsign,
                "control_keys": ["flight"],
            },
        }

        topic = f"thing/product/{self._gateway_sn}/services"
        result = self._client.publish(topic, json.dumps(request), qos=1)
        self._info(
            "已发送授权请求 -> "
            f"topic={topic}, mid={result.mid}, rc={result.rc}"
        )
        self._console.print(
            self._json_panel("Request Payload", request, "green")
        )
        self._info("请在遥控器上确认授权操作，本程序将持续监听回复（Ctrl+C 结束）。")

        # 持续监听回复
        start = time.time()
        terminal_status = {"ok", "rejected", "timeout", "cancelled"}
        try:
            while True:
                time.sleep(0.2)
                if self._response:
                    data = self._response.get("data") or {}
                    status = (data.get("output") or {}).get("status")
                    result_code = data.get("result")
                    if result_code == 0:
                        self._info("收到 result=0，授权已通过，结束监听。")
                        break
                    if status in terminal_status:
                        self._info(f"检测到终止状态 {status}，将结束监听。")
                        break
                if self._timeout is not None and time.time() - start >= self._timeout:
                    self._warn(f"超过 {self._timeout} 秒未收到终止状态，自动结束监听。")
                    break
        except KeyboardInterrupt:
            self._info("收到用户中断指令，停止监听。")

        self._client.loop_stop()
        self._client.disconnect()

        if self._response is None:
            self._warn("在监听期间未收到任何匹配回复，请检查网关在线状态或主题。")
            return 2

        data = self._response.get("data", {})
        status = (data.get("output") or {}).get("status")
        result_code = data.get("result")
        if result_code == 0:
            self._info(f"授权请求流程完成，状态：{status or '未知'}。")
            return 0

        self._warn(
            f"授权请求失败 result={result_code}, status={status}, payload={data}"
        )
        return 3


def main() -> int:
    client = ControlRequestClient(
        host=MQTT_HOST,
        port=MQTT_PORT,
        gateway_sn=GATEWAY_SN,
        user_id=USER_ID,
        user_callsign=USER_CALLSIGN,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        timeout=REPLY_TIMEOUT,
    )
    return client.run()


if __name__ == "__main__":
    sys.exit(main())
