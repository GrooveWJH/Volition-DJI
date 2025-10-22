# DJI MQTT 嗅探器

> 通用的 DJI MQTT 消息监听和捕获工具

## 🎯 功能特性

1. **多 Topic 同时监听** - 支持同时监听多个 MQTT topic
2. **实时统计显示** - Rich 终端 UI 实时显示消息类型、数量、频率
3. **分类存储** - 每个 topic 的消息保存到独立的 JSON 文件
4. **规范目录结构** - 输出到 `sniffed_data/{timestamp}/` 目录
5. **可选 DRC 模式** - 可自动进入 DRC 模式获取 OSD/HSI 数据
6. **心跳监控** - 实时显示 DRC 心跳发送/接收状态

## 🚀 快速开始

### 1. 配置监听的 Topic

编辑 `utils/mqtt_sniffer.py` 中的配置：

```python
# 嗅探配置
ENABLE_DRC_MODE = True  # 是否自动进入 DRC 模式
SNIFF_TOPICS = [
    f"sys/product/{GATEWAY_SN}/status",         # 设备状态
    f"thing/product/{GATEWAY_SN}/events_reply", # 事件回复
    f"thing/product/{GATEWAY_SN}/drc/up",       # DRC 上行数据
]
OUTPUT_BASE_DIR = "sniffed_data"  # 输出根目录
```

### 2. 运行嗅探器

```bash
python utils/mqtt_sniffer.py
```

### 3. 查看实时统计

终端会显示实时更新的监控面板：

```
┌─────────────────────── DJI MQTT 嗅探器 ───────────────────────┐
│ ┌─ status ───────┐  ┌─ events_reply ─┐  ┌─ up ─────────┐    │
│ │ 消息类型   次数 │  │ 消息类型  次数 │  │ 消息类型 次数 │    │
│ │ heartbeat  120  │  │ event_A    5   │  │ osd_info 1200 │    │
│ └────────────────┘  └────────────────┘  └───────────────┘    │
├───────────────────────────────────────────────────────────────┤
│ 运行时间: 60.0秒 | 总消息数: 1325 | 监听主题: 3 | 心跳: 发300/收300 (5.0Hz) │
└───────────────────────────────────────────────────────────────┘
```

### 4. 停止并保存

按 `Ctrl+C` 停止嗅探，自动保存数据到：

```
sniffed_data/
└── 20251021_164530/        # 时间戳目录
    ├── _summary.json       # 汇总信息
    ├── status.json         # status topic 的所有消息
    ├── events_reply.json   # events_reply topic 的所有消息
    └── up.json             # drc/up topic 的所有消息
```

## 📊 输出文件格式

### 各 Topic 的 JSON 文件

```json
{
  "metadata": {
    "topic": "thing/product/9N9CN180011TJN/drc/up",
    "gateway_sn": "9N9CN180011TJN",
    "capture_time": "2025-10-21T16:45:30.123456",
    "runtime_seconds": 60.5,
    "total_messages": 1200,
    "message_types": 3
  },
  "statistics": {
    "drc_camera_osd_info_push": {
      "count": 1000,
      "frequency_hz": 16.53,
      "first_time": "2025-10-21T16:44:30.000000",
      "last_time": "2025-10-21T16:45:30.000000"
    },
    "heart_beat": {
      "count": 200,
      "frequency_hz": 3.31,
      "first_time": "...",
      "last_time": "..."
    }
  },
  "latest_messages": {
    "drc_camera_osd_info_push": { /* 最新消息完整内容 */ },
    "heart_beat": { /* 最新消息完整内容 */ }
  }
}
```

### 汇总文件 `_summary.json`

```json
{
  "capture_info": {
    "gateway_sn": "9N9CN180011TJN",
    "capture_time": "2025-10-21T16:45:30.123456",
    "runtime_seconds": 60.5,
    "topics": [
      "sys/product/9N9CN180011TJN/status",
      "thing/product/9N9CN180011TJN/events_reply",
      "thing/product/9N9CN180011TJN/drc/up"
    ]
  },
  "statistics": {
    "status": {
      "full_topic": "sys/product/9N9CN180011TJN/status",
      "total_messages": 60,
      "message_types": 1,
      "methods": ["heartbeat"]
    },
    "events_reply": { /* ... */ },
    "up": { /* ... */ }
  }
}
```

## ⚙️ 配置选项

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `ENABLE_DRC_MODE` | 是否自动进入 DRC 模式 | `True` |
| `SNIFF_TOPICS` | 监听的 topic 列表 | `[status, events_reply, drc/up]` |
| `OUTPUT_BASE_DIR` | 输出根目录 | `sniffed_data` |
| `OSD_FREQUENCY` | OSD 数据频率（仅 DRC 模式） | `100 Hz` |
| `HSI_FREQUENCY` | HSI 数据频率（仅 DRC 模式） | `2 Hz` |

## 📝 使用场景

### 场景 1: 只监听状态消息（不进入 DRC 模式）

```python
ENABLE_DRC_MODE = False
SNIFF_TOPICS = [
    f"sys/product/{GATEWAY_SN}/status"
]
```

### 场景 2: 监听所有控制相关消息

```python
ENABLE_DRC_MODE = True
SNIFF_TOPICS = [
    f"thing/product/{GATEWAY_SN}/services_reply",
    f"thing/product/{GATEWAY_SN}/drc/up",
    f"thing/product/{GATEWAY_SN}/events"
]
```

### 场景 3: 调试特定功能

```python
ENABLE_DRC_MODE = True
SNIFF_TOPICS = [
    f"thing/product/{GATEWAY_SN}/drc/up",  # 只监听 DRC 数据
]
OSD_FREQUENCY = 1  # 降低频率减少消息量
```

## 🔧 技术细节

- **基于** `djisdk` 库（原 `drc` 库）
- **消息处理** - 支持链式消息处理器，不影响其他功能
- **频率计算** - 使用 `(count - 1) / time_span` 精确计算
- **文件命名** - 使用 topic 最后一段作为文件名（`status.json`, `up.json`）
- **时间戳格式** - ISO 8601 格式，便于解析

## 📦 相关文件

- `../djisdk/` - DJI Cloud API Python SDK 库
- `utils/mqtt_sniffer.py` - MQTT 嗅探器主程序（本文件）
- `../request_and_enter_drc.py.bak` - 原始脚本备份

---

**提示**: 如果只需要监听消息而不需要进入 DRC 模式，设置 `ENABLE_DRC_MODE = False` 可以跳过控制权请求步骤。
