#!/usr/bin/env python3
"""
一键发送控制权请求并进入 DRC 模式。

执行流程：
1. 向遥控器请求云端飞行控制权（cloud_control_auth_request）。
2. 提示用户在遥控器上确认授权。
3. 用户在终端按回车后，发送 drc_mode_enter 请求。

运行前请在配置区域填写好 MQTT 与凭证信息，直接执行：
    python control/request_and_enter_drc.py
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
from rich.live import Live


# ======== 通用配置 ========
MQTT_HOST = "192.168.31.73"
MQTT_PORT = 1883
MQTT_USERNAME = "admin"  # 如果 broker 需要认证，填入用户名
MQTT_PASSWORD = "302811055wjhhz"  # 如果 broker 需要认证，填入密码

GATEWAY_SN = "9N9CN2J0012CXY"

# 控制权请求参数
USER_ID = "groove"
USER_CALLSIGN = "吴建豪"

# DRC 模式中继参数``
MQTT_RELAY_ADDRESS = "192.168.31.73:1883"
MQTT_RELAY_CLIENT_ID = "drc-9N9CN8400164WH"
MQTT_RELAY_USERNAME = "admin"
MQTT_RELAY_PASSWORD = "302811055wjhhz"
MQTT_RELAY_EXPIRE_TIME = 1_700_000_000
MQTT_RELAY_ENABLE_TLS = False

OSD_FREQUENCY = 30
HSI_FREQUENCY = 10
HEARTBEAT_FREQUENCY_HZ = 5
# ======== 配置结束 ========


class BaseClient:
    """公共工具：日志、JSON Panel、连接处理等。"""

    def __init__(
        self,
        host: str,
        port: int,
        username: Optional[str],
        password: Optional[str],
        reply_topic: str,
    ):
        self._host = host
        self._port = port
        self._console = Console()
        self._reply_topic = reply_topic
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    # ---- Logging helpers ----
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

    # ---- MQTT callbacks (version-2 signatures) ----
    def _on_connect(self, client, _userdata, _flags, reason_code, _properties):
        readable = mqtt.connack_string(reason_code)
        self._info(f"连接到 MQTT -> rc={reason_code} ({readable})")
        if reason_code == 0 and self._reply_topic:
            client.subscribe(self._reply_topic)
            self._info(f"已订阅回复主题：{self._reply_topic}")

    def _on_disconnect(
        self, _client, _userdata, disconnect_flags, reason_code, _properties
    ):
        self._info(
            f"MQTT 连接已断开，rc={reason_code}, flags={disconnect_flags}"
        )

    def _on_message(self, _client, _userdata, msg):
        """留给子类实现"""
        raise NotImplementedError


class ControlRequestClient(BaseClient):
    def __init__(
        self,
        host: str,
        port: int,
        gateway_sn: str,
        user_id: str,
        user_callsign: str,
        username: Optional[str],
        password: Optional[str],
    ):
        super().__init__(
            host, port, username, password, f"thing/product/{gateway_sn}/services_reply"
        )
        self._gateway_sn = gateway_sn
        self._user_id = user_id
        self._callsign = user_callsign
        self._response = None
        self._tid = str(uuid.uuid4())
        self._bid = str(uuid.uuid4())

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
            "控制权回复 -> result=%s, status=%s" % (result_code, status)
        )
        self._console.print(
            self._json_panel("Control Reply", payload, "bright_magenta")
        )

        if payload.get("tid") == self._tid:
            self._response = payload

    def send(self) -> int:
        try:
            self._client.connect(self._host, self._port, keepalive=60)
        except Exception as exc:
            self._error(f"无法连接 MQTT：{exc}")
            return 1

        self._client.loop_start()
        time.sleep(1)

        payload = {
            "tid": self._tid,
            "bid": self._bid,
            "timestamp": int(time.time() * 1000),
            "method": "cloud_control_auth_request",
            "data": {
                "user_id": self._user_id,
                "user_callsign": self._callsign,
                "control_keys": ["flight"],
            },
        }
        topic = f"thing/product/{self._gateway_sn}/services"
        result = self._client.publish(topic, json.dumps(payload), qos=1)
        self._info(
            "已发送授权请求 -> topic=%s, mid=%s, rc=%s"
            % (topic, result.mid, result.rc)
        )
        self._console.print(
            self._json_panel("Control Request", payload, "green")
        )

        try:
            while True:
                time.sleep(0.2)
                if self._response:
                    data = self._response.get("data") or {}
                    status = (data.get("output") or {}).get("status")
                    result_code = data.get("result")
                    if result_code == 0 and status == "in_progress":
                        self._info("遥控器已收到请求（result=0, status=in_progress）。")
                        break
                    if result_code != 0:
                        self._warn(f"控制权请求失败 result={result_code}")
                        break
        except KeyboardInterrupt:
            self._warn("用户中断了控制权请求等待。")

        self._client.loop_stop()
        self._client.disconnect()

        if not self._response:
            self._warn("未收到控制权回复，请检查连接。")
            return 2

        result_code = (self._response.get("data") or {}).get("result")
        if result_code == 0:
            self._info("控制权请求成功，等待用户在遥控器上确认。")
            return 0

        self._warn("控制权请求失败 result=%s" % result_code)
        return 3


class DrcModeClient(BaseClient):
    def __init__(
        self,
        host: str,
        port: int,
        gateway_sn: str,
        username: Optional[str],
        password: Optional[str],
    ):
        super().__init__(
            host, port, username, password, f"thing/product/{gateway_sn}/services_reply"
        )
        self._gateway_sn = gateway_sn
        self._response = None
        self._tid = str(uuid.uuid4())
        self._bid = str(uuid.uuid4())

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

    def _on_message(self, _client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            self._warn(f"收到非 JSON 回复：{msg.payload!r}")
            return

        method = payload.get("method")
        result = (payload.get("data") or {}).get("result")
        self._info(f"DRC 回复 -> method={method}, result={result}")
        self._console.print(
            self._json_panel("DRC Reply", payload, "bright_magenta")
        )

        if payload.get("tid") == self._tid and method == "drc_mode_enter":
            self._response = payload

    def send(self) -> int:
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
            self._json_panel("DRC Request", payload, "green")
        )

        try:
            start = time.time()
            while self._response is None:
                time.sleep(0.2)
                if time.time() - start > 30:
                    self._warn("等待 DRC 回复超时。")
                    break
        except KeyboardInterrupt:
            self._warn("用户中断等待。")

        self._client.loop_stop()
        self._client.disconnect()

        if self._response is None:
            self._warn("未收到 DRC 回复。")
            return 2

        result_code = (self._response.get("data") or {}).get("result")
        if result_code == 0:
            self._info("进入 DRC 模式请求成功。")
            return 0

        self._warn(f"进入 DRC 模式失败 result={result_code}")
        return 3


class DrcHeartbeatClient(BaseClient):
    def __init__(
        self,
        host: str,
        port: int,
        gateway_sn: str,
        username: Optional[str],
        password: Optional[str],
        frequency_hz: float,
    ):
        super().__init__(
            host, port, username, password, f"thing/product/{gateway_sn}/drc/up"
        )
        self._gateway_sn = gateway_sn
        self._down_topic = f"thing/product/{gateway_sn}/drc/down"
        self._frequency = max(float(frequency_hz), 0.1)
        self._interval = 1.0 / self._frequency
        self._last_seq = int(time.time() * 1000)
        self._sent_count = 0
        self._recv_count = 0
        self._failed_count = 0
        self._last_sent_ts: Optional[int] = None
        self._last_send_seq: Optional[int] = None
        self._last_recv_ts: Optional[int] = None
        self._last_recv_seq: Optional[int] = None
        self._live: Optional[Live] = None

    def _next_seq(self) -> int:
        candidate = int(time.time() * 1000)
        if candidate <= self._last_seq:
            candidate = self._last_seq + 1
        self._last_seq = candidate
        return candidate

    def _build_payload(self) -> dict:
        timestamp = int(time.time() * 1000)
        return {
            "seq": self._next_seq(),
            "method": "heart_beat",
            "data": {
                "timestamp": timestamp,
            },
        }

    def _on_message(self, _client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            self._warn(f"收到异常心跳回复：{msg.payload!r}")
            return
        if payload.get("method") != "heart_beat":
            return

        self._recv_count += 1
        self._last_recv_seq = payload.get("seq")
        self._last_recv_ts = (payload.get("data") or {}).get("timestamp")
        if self._live:
            self._live.update(self._render_status(), refresh=True)

    def _render_status(self) -> Panel:
        summary = (
            f"[bold green]发出[/]: {self._sent_count} (失败 {self._failed_count})\n"
            f"[bold cyan]收到[/]: {self._recv_count}\n"
            f"[bold green]最近发送[/]: seq={self._last_send_seq or '-'}, ts={self._last_sent_ts or '-'}\n"
            f"[bold cyan]最近收到[/]: seq={self._last_recv_seq or '-'}, ts={self._last_recv_ts or '-'}\n"
            f"[bold yellow]频率[/]: {self._frequency:.2f}Hz"
        )
        return Panel(summary, title="DRC Heart Beat", padding=(1, 2))

    def run(self) -> int:
        try:
            self._client.connect(self._host, self._port, keepalive=30)
        except Exception as exc:
            self._error(f"无法建立心跳 MQTT 连接：{exc}")
            return 1

        self._client.loop_start()
        self._info(
            f"开始发送 DRC 心跳，频率 {self._frequency:.2f}Hz（间隔 {self._interval:.3f}s）。按 Ctrl+C 可停止。"
        )

        next_tick = time.perf_counter()
        try:
            with Live(
                self._render_status(),
                refresh_per_second=10,
                console=self._console,
                auto_refresh=False,
            ) as live:
                self._live = live
                while True:
                    now = time.perf_counter()
                    if now < next_tick:
                        time.sleep(min(self._interval, next_tick - now))
                        continue

                    payload = self._build_payload()
                    info = self._client.publish(
                        self._down_topic, json.dumps(payload), qos=0
                    )
                    if info.rc != mqtt.MQTT_ERR_SUCCESS:
                        self._failed_count += 1
                        self._warn(
                            f"心跳发送失败 rc={info.rc} seq={payload['seq']}"
                        )
                    else:
                        self._sent_count += 1
                        self._last_send_seq = payload["seq"]
                        self._last_sent_ts = payload["data"]["timestamp"]
                    live.update(self._render_status(), refresh=True)

                    next_tick += self._interval
                    if next_tick < now:
                        next_tick = now + self._interval
        except KeyboardInterrupt:
            self._warn("检测到中断，准备退出心跳循环。")
        finally:
            self._live = None
            self._client.loop_stop()
            self._client.disconnect()
            self._info("已停止 DRC 心跳连接。")

        return 0


def main() -> int:
    console = Console()
    console.rule("[bold cyan]控制权请求")
    control_client = ControlRequestClient(
        host=MQTT_HOST,
        port=MQTT_PORT,
        gateway_sn=GATEWAY_SN,
        user_id=USER_ID,
        user_callsign=USER_CALLSIGN,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
    )
    control_result = control_client.send()
    if control_result != 0:
        console.print("[bold red]控制权请求失败，终止流程。[/]")
        return control_result

    console.print(
        "\n[bold green]控制权请求已发送，请在遥控器上点击确认授权。"
        "完成后在此处按回车继续发送 DRC 请求。[/]"
    )
    try:
        input()
    except KeyboardInterrupt:
        console.print("[bold yellow]检测到中断，退出。[/]")
        return 1

    console.rule("[bold cyan]DRC 模式请求")
    drc_client = DrcModeClient(
        host=MQTT_HOST,
        port=MQTT_PORT,
        gateway_sn=GATEWAY_SN,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
    )
    drc_result = drc_client.send()
    if drc_result != 0:
        return drc_result

    console.rule("[bold cyan]DRC 心跳")
    console.print(
        "[bold green]已进入 DRC 模式，开始发送心跳以维持链路。[/]\n"
        "[bold yellow]按 Ctrl+C 停止心跳并退出。[/]"
    )
    heartbeat_client = DrcHeartbeatClient(
        host=MQTT_HOST,
        port=MQTT_PORT,
        gateway_sn=GATEWAY_SN,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        frequency_hz=HEARTBEAT_FREQUENCY_HZ,
    )
    return heartbeat_client.run()


if __name__ == "__main__":
    sys.exit(main())
