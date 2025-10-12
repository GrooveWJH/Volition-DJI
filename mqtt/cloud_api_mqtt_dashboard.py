#!/usr/bin/env python3

import json
import os
import threading
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

from importlib.metadata import version

import paho
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string

load_dotenv(override=True)

host_addr = os.environ["HOST_ADDR"]
mqtt_username = os.environ.get("USERNAME")
mqtt_password = os.environ.get("PASSWORD")
dashboard_port = int(os.environ.get("DASHBOARD_PORT", "8000"))

app = Flask(__name__)

MAX_MESSAGES = 200
_messages = deque(maxlen=MAX_MESSAGES)
_devices: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
_connection_status = {"connected": False, "last_rc": None, "timestamp": None}
MAX_EVENTS_PER_DEVICE = 20


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _parse_payload(payload: bytes) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return payload.decode("utf-8", errors="ignore")


def _summarize_message(topic: str, message: Any) -> str:
    if isinstance(message, dict):
        if topic.endswith("osd"):
            data = message.get("data", {})
            lat = data.get("latitude")
            lon = data.get("longitude")
            height = data.get("height")
            speed = data.get("horizontal_speed") or data.get("vertical_speed")
            battery = data.get("capacity_percent")
            return (
                f"OSD lat={lat} lon={lon} height={height} speed={speed} "
                f"battery={battery}"
            )
        if topic.endswith("state"):
            data = message.get("data", {})
            mode = data.get("mode_code")
            status = data.get("live_status") or data.get("status")
            return f"State mode={mode} status={status}"
        if topic.endswith("events"):
            data = message.get("data", {})
            event = data.get("type") or data.get("event_type")
            return f"Event {event}: {json.dumps(data)[:80]}"
        if topic.endswith("status"):
            return f"Status {json.dumps(message)[:100]}"
        return json.dumps(message)[:180]
    return str(message)[:180]


def _store_message(topic: str, message: Any, summary: str) -> None:
    entry = {
        "timestamp": _timestamp(),
        "topic": topic,
        "summary": summary,
        "raw": message,
    }
    with _lock:
        _messages.appendleft(entry)


def _extract_product(topic: str) -> Optional[str]:
    parts = topic.split("/")
    if len(parts) >= 4 and parts[1] == "product":
        return parts[2]
    return None


def _normalize_osd(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "height": data.get("height"),
        "horizontal_speed": data.get("horizontal_speed"),
        "vertical_speed": data.get("vertical_speed"),
        "attitude_head": data.get("attitude_head"),
        "attitude_pitch": data.get("attitude_pitch"),
        "attitude_roll": data.get("attitude_roll"),
        "battery_percent": data.get("capacity_percent"),
        "wind_direction": data.get("wind_direction"),
        "wind_speed": data.get("wind_speed"),
        "total_flight_time": data.get("total_flight_time"),
        "total_flight_distance": data.get("total_flight_distance"),
        "home_distance": data.get("home_distance"),
        "gear": data.get("gear"),
        "mode_code": data.get("mode_code"),
        "timestamp": _timestamp(),
    }


def _normalize_state(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "firmware_version": data.get("firmware_version"),
        "mode_code": data.get("mode_code"),
        "live_status": data.get("live_status"),
        "is_fixed": (data.get("position_state") or {}).get("is_fixed"),
        "gps_number": (data.get("position_state") or {}).get("gps_number"),
        "rtk_number": (data.get("position_state") or {}).get("rtk_number"),
        "storage": data.get("storage"),
        "updated_at": _timestamp(),
    }


def _append_events(device: Dict[str, Any], message: Dict[str, Any]) -> None:
    events = message.get("data", {}).get("list", [])
    if not events:
        return
    device_events = device.setdefault("events", deque(maxlen=MAX_EVENTS_PER_DEVICE))
    for evt in events:
        device_events.appendleft(
            {
                "code": evt.get("code"),
                "type": evt.get("type") or evt.get("event_type"),
                "level": evt.get("level"),
                "args": evt.get("args") or {},
                "time": _timestamp(),
            }
        )


def _update_device_snapshot(topic: str, message: Any) -> None:
    product = _extract_product(topic)
    if not product or not isinstance(message, dict):
        return

    parts = topic.split("/")
    category = parts[3] if len(parts) > 3 else ""
    device = _devices.setdefault(
        product,
        {
            "product": product,
            "updated": _timestamp(),
            "osd": {},
            "state": {},
            "events": deque(maxlen=MAX_EVENTS_PER_DEVICE),
            "last_topics": {},
        },
    )

    device["updated"] = _timestamp()
    device["last_topics"][category] = _timestamp()

    data_section = message.get("data", {})

    if category == "osd":
        device["osd"] = _normalize_osd(data_section)
    elif category == "state":
        device["state"] = _normalize_state(data_section)
    elif category == "events":
        _append_events(device, message)
    elif category == "status":
        device["status"] = {
            "payload": message,
            "updated_at": _timestamp(),
        }
    elif category == "property" and len(parts) > 4 and parts[4] == "set":
        device.setdefault("last_property_set", deque(maxlen=5)).appendleft(
            {"payload": data_section, "time": _timestamp()}
        )


def on_connect(client: mqtt.Client, userdata, flags, rc, properties=None):
    readable = mqtt.connack_string(rc)
    with _lock:
        _connection_status.update(
            {
                "connected": rc == 0,
                "last_rc": readable,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    print(f"Connected with result code {readable}")
    if rc == 0:
        client.subscribe("sys/#")
        client.subscribe("thing/#")


def on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
    message = _parse_payload(msg.payload)
    summary = _summarize_message(msg.topic, message)
    print(f"📨 {msg.topic} -> {summary}")
    _store_message(msg.topic, message, summary)
    with _lock:
        _update_device_snapshot(msg.topic, message)
    if msg.topic.endswith("status"):
        if isinstance(message, dict) and message.get("method") == "update_topo":
            reply = {
                "tid": message.get("tid"),
                "bid": message.get("bid"),
                "timestamp": message.get("timestamp", 0) + 2,
                "data": {"result": 0},
            }
            client.publish(msg.topic + "_reply", payload=json.dumps(reply))
            _store_message(
                msg.topic + "_reply",
                reply,
                "Reply update_topo -> result=0",
            )


def _client_factory() -> mqtt.Client:
    PAHO_MAIN_VER = int(version("paho-mqtt").split(".")[0])
    if PAHO_MAIN_VER == 1:
        client = mqtt.Client(transport="tcp")
    else:
        client = mqtt.Client(
            paho.mqtt.enums.CallbackAPIVersion.VERSION2,
            transport="tcp",
        )

    if mqtt_username:
        client.username_pw_set(mqtt_username, mqtt_password)

    client.on_connect = on_connect
    client.on_message = on_message
    return client


client = _client_factory()
client.connect(host_addr, 1883, 60)
client.loop_start()


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>DJI MQTT 仪表盘</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f4f6f8;
      --card-bg: #ffffff;
      --primary: #1a73e8;
      --text-primary: #202124;
      --text-secondary: #5f6368;
      --divider: #e0e0e0;
      --success: #1e8e3e;
      --error: #d93025;
    }
    * { box-sizing: border-box; }
    body {
      font-family: 'Roboto', 'Helvetica', 'Arial', sans-serif;
      background: var(--bg);
      color: var(--text-primary);
      margin: 0;
      padding: 2rem 3rem;
    }
    header {
      margin-bottom: 1.5rem;
    }
    header h1 {
      margin: 0;
      font-size: 2rem;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    header h1::before {
      content: "";
      width: 12px;
      height: 32px;
      border-radius: 8px;
      background: var(--primary);
      display: inline-block;
    }
    header p {
      margin: 0.2rem 0 0;
      color: var(--text-secondary);
    }
    .card {
      background: var(--card-bg);
      border-radius: 16px;
      box-shadow: 0 8px 24px rgba(60, 64, 67, 0.15);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    .status-card {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      border-left: 6px solid var(--success);
    }
    .status-card.offline {
      border-left-color: var(--error);
    }
    .status-main {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }
    .status-title {
      font-size: 1.1rem;
      font-weight: 500;
    }
    .status-meta {
      color: var(--text-secondary);
      font-size: 0.95rem;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      border-radius: 999px;
      padding: 0.35rem 0.9rem;
      font-size: 0.85rem;
      font-weight: 500;
      color: #fff;
      background: var(--primary);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.5rem;
    }
    .device-card h2 {
      margin: 0;
      font-size: 1.3rem;
      font-weight: 500;
    }
    .device-subtitle {
      color: var(--text-secondary);
      font-size: 0.9rem;
      margin-top: 0.25rem;
    }
    .section {
      margin-top: 1.2rem;
    }
    .section h3 {
      margin: 0 0 0.6rem;
      font-size: 1rem;
      font-weight: 500;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .data-table {
      width: 100%;
      border-collapse: collapse;
    }
    .data-table th,
    .data-table td {
      border-bottom: 1px solid var(--divider);
      padding: 0.45rem 0;
      font-size: 0.95rem;
      text-align: left;
    }
    .data-table th {
      width: 45%;
      color: var(--text-secondary);
      font-weight: 400;
    }
    .data-table td {
      font-weight: 500;
    }
    .events-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 0.6rem;
    }
    .events-table th, .events-table td {
      border-bottom: 1px solid var(--divider);
      padding: 0.45rem 0.4rem;
      font-size: 0.9rem;
      text-align: left;
    }
    .events-table th {
      color: var(--text-secondary);
      font-weight: 500;
    }
    .muted {
      color: var(--text-secondary);
    }
    .message-table-wrapper {
      overflow-x: auto;
      margin-top: 1rem;
    }
    table.message-table {
      width: 100%;
      border-collapse: collapse;
    }
    table.message-table th,
    table.message-table td {
      border-bottom: 1px solid var(--divider);
      padding: 0.6rem 0.4rem;
      font-size: 0.9rem;
    }
    table.message-table th {
      color: var(--text-secondary);
      font-weight: 500;
    }
    code {
      background: rgba(26, 115, 232, 0.08);
      padding: 0.2rem 0.4rem;
      border-radius: 6px;
      font-size: 0.85rem;
    }
    @media (max-width: 768px) {
      body { padding: 1.5rem; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>DJI MQTT 仪表盘</h1>
    <p>实时监测无人机通过 MQTT 上传的遥测、状态与事件数据</p>
  </header>

  <section class="card status-card" id="status-card">
    <div class="status-main">
      <div class="status-title" id="status-title">连接状态加载中…</div>
      <div class="status-meta" id="status-meta"></div>
    </div>
    <span class="chip" id="status-chip">等待数据</span>
  </section>

  <section>
    <div class="grid" id="device-grid">
      <div class="card device-card">
        <h2>尚未收到设备数据</h2>
        <p class="device-subtitle">一旦 MQTT 上有新的 `thing/product/...` 消息会自动刷新</p>
      </div>
    </div>
  </section>

  <section class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div>
        <h2 style="margin:0; font-size:1.2rem; font-weight:500;">最近消息摘要</h2>
        <p class="device-subtitle" style="margin-top:0.2rem;">保留最新 50 条以便排查</p>
      </div>
    </div>
    <div class="message-table-wrapper">
      <table class="message-table">
        <thead>
          <tr>
            <th>时间 (UTC)</th>
            <th>Topic</th>
            <th>摘要</th>
          </tr>
        </thead>
        <tbody id="message-body"></tbody>
      </table>
    </div>
  </section>

  <script>
    function formatNumber(value, digits = 2) {
      if (value === null || value === undefined || Number.isNaN(value)) return "—";
      if (typeof value !== "number") return value;
      return Number(value).toFixed(digits);
    }

    function formatInteger(value) {
      if (value === null || value === undefined || Number.isNaN(value)) return "—";
      return Math.round(Number(value));
    }

    function renderStatus(status) {
      const card = document.getElementById("status-card");
      const title = document.getElementById("status-title");
      const meta = document.getElementById("status-meta");
      const chip = document.getElementById("status-chip");

      if (status.connected) {
        card.classList.remove("offline");
        title.textContent = "已连接至 MQTT Broker";
        meta.textContent = `最近握手：${status.timestamp || "—"}，返回码：${status.last_rc}`;
        chip.textContent = "在线";
        chip.style.background = "var(--success)";
      } else {
        card.classList.add("offline");
        title.textContent = "尚未建立 MQTT 连接";
        meta.textContent = status.last_rc ? `最后错误：${status.last_rc}` : "等待客户端尝试连接…";
        chip.textContent = "离线";
        chip.style.background = "var(--error)";
      }
    }

    function buildTelemetryRows(osd) {
      if (!osd || Object.keys(osd).length === 0) {
        return '<tr><td colspan="2" class="muted">暂未收到 OSD 数据</td></tr>';
      }
      const rows = [
        ["纬度", formatNumber(osd.latitude, 6)],
        ["经度", formatNumber(osd.longitude, 6)],
        ["相对高度 (m)", formatNumber(osd.height, 2)],
        ["水平速度 (m/s)", formatNumber(osd.horizontal_speed, 2)],
        ["垂直速度 (m/s)", formatNumber(osd.vertical_speed, 2)],
        ["电量 (%)", formatInteger(osd.battery_percent)],
        ["总飞行时间 (s)", formatInteger(osd.total_flight_time)],
        ["累计航程 (m)", formatNumber(osd.total_flight_distance, 1)],
        ["返航距离 (m)", formatNumber(osd.home_distance, 1)],
        ["风向 (°)", formatNumber(osd.wind_direction, 1)],
        ["风速 (m/s)", formatNumber(osd.wind_speed, 1)],
        ["航向 (°)", formatNumber(osd.attitude_head, 1)],
        ["俯仰 (°)", formatNumber(osd.attitude_pitch, 1)],
        ["横滚 (°)", formatNumber(osd.attitude_roll, 1)],
      ];
      return rows
        .map(([label, value]) => `<tr><th>${label}</th><td>${value}</td></tr>`)
        .join("");
    }

    function buildStateRows(state) {
      if (!state || Object.keys(state).length === 0) {
        return '<tr><td colspan="2" class="muted">暂未收到状态数据</td></tr>';
      }
      const storage = state.storage || {};
      const hasStorage =
        storage &&
        Number.isFinite(Number(storage.total)) &&
        Number.isFinite(Number(storage.used));
      const rows = [
        ["固件版本", state.firmware_version || "—"],
        ["飞行模式码", state.mode_code ?? "—"],
        ["实时状态", state.live_status ?? "—"],
        ["GPS 卫星数", formatInteger(state.gps_number)],
        ["RTK 卫星数", formatInteger(state.rtk_number)],
        ["定位是否固定", state.is_fixed === null || state.is_fixed === undefined ? "—" : (state.is_fixed ? "已固定" : "未固定")],
        ["存储占用", hasStorage ? `${Math.round(Number(storage.used) / 1024)} / ${Math.round(Number(storage.total) / 1024)} MB` : "—"],
        ["最近上报", state.updated_at || "—"],
      ];
      return rows
        .map(([label, value]) => `<tr><th>${label}</th><td>${value}</td></tr>`)
        .join("");
    }

    function buildEventsTable(events) {
      if (!events || events.length === 0) {
        return '<p class="muted">暂无事件上报</p>';
      }
      const lines = events.slice(0, 6).map(evt => {
        const args = Object.keys(evt.args || {}).length ? JSON.stringify(evt.args) : "—";
        return `
          <tr>
            <td>${evt.time}</td>
            <td>${evt.code || "—"}</td>
            <td>${evt.type || "—"}</td>
            <td>${args}</td>
          </tr>
        `;
      });
      return `
        <table class="events-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>事件代码</th>
              <th>类型</th>
              <th>参数</th>
            </tr>
          </thead>
          <tbody>${lines.join("")}</tbody>
        </table>
      `;
    }

    function renderDevices(devices) {
      const grid = document.getElementById("device-grid");
      grid.innerHTML = "";

      if (!devices.length) {
        grid.innerHTML = `
          <div class="card device-card">
            <h2>尚未收到设备数据</h2>
            <p class="device-subtitle">请确认 Pilot App 已登录并向 MQTT 推送数据</p>
          </div>
        `;
        return;
      }

      devices.forEach(device => {
        const card = document.createElement("div");
        card.className = "card device-card";
        card.innerHTML = `
          <div>
            <h2>${device.product || "未知设备"}</h2>
            <div class="device-subtitle">
              最后消息时间：${device.updated || "—"}
              ${device.last_topics && device.last_topics.osd ? ` · OSD 上报：${device.last_topics.osd}` : ""}
            </div>
          </div>

          <div class="section">
            <h3>飞行遥测</h3>
            <table class="data-table">
              <tbody>${buildTelemetryRows(device.osd)}</tbody>
            </table>
          </div>

          <div class="section">
            <h3>系统状态</h3>
            <table class="data-table">
              <tbody>${buildStateRows(device.state)}</tbody>
            </table>
          </div>

          <div class="section">
            <h3>最新事件</h3>
            ${buildEventsTable(device.events)}
          </div>
        `;
        grid.appendChild(card);
      });
    }

    function renderMessages(messages) {
      const tbody = document.getElementById("message-body");
      tbody.innerHTML = "";
      const limited = messages.slice(0, 50);
      limited.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.timestamp}</td>
          <td><code>${row.topic}</code></td>
          <td>${row.summary}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    async function refresh() {
      try {
        const [statusResp, devicesResp, messagesResp] = await Promise.all([
          fetch("/api/status"),
          fetch("/api/devices"),
          fetch("/api/messages"),
        ]);
        const [status, devices, messages] = await Promise.all([
          statusResp.json(),
          devicesResp.json(),
          messagesResp.json(),
        ]);
        renderStatus(status);
        renderDevices(devices);
        renderMessages(messages);
      } catch (err) {
        console.error("刷新数据失败", err);
      }
    }

    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/api/messages")
def api_messages():
    with _lock:
        return jsonify(list(_messages))


@app.route("/api/status")
def api_status():
    with _lock:
        return jsonify(_connection_status)


@app.route("/api/devices")
def api_devices():
    with _lock:
        snapshot = []
        for device in _devices.values():
            snapshot.append(
                {
                    "product": device.get("product"),
                    "updated": device.get("updated"),
                    "osd": device.get("osd"),
                    "state": device.get("state"),
                    "status": device.get("status"),
                    "events": list(device.get("events", [])),
                    "last_property_set": list(device.get("last_property_set", [])),
                    "last_topics": device.get("last_topics", {}),
                }
            )
        return jsonify(snapshot)


if __name__ == "__main__":
    print(f"Starting dashboard on http://{host_addr}:{dashboard_port}")
    app.run(host=host_addr, port=dashboard_port)
