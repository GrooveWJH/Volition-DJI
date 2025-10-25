# live.py - DJI 无人机直播推流工具

## 功能说明

这个工具用于快速启动 DJI 无人机的直播推流功能。

## 特点

- ✅ **交互式选择无人机** - 从预配置的3台无人机中选择
- ✅ **自动建立 DRC 连接** - 自动完成认证、进入 DRC 模式、启动心跳
- ✅ **美化显示 MQTT 消息** - 清晰显示发送和接收的完整 JSON 数据
- ✅ **彩色终端输出** - 使用 Rich 库提供友好的用户界面

## 配置说明

所有配置项都在文件顶部，可以直接修改：

### 1. MQTT 配置 (第 24-29 行)

```python
MQTT_CONFIG = {
    'host': '81.70.222.38',      # MQTT 服务器地址
    'port': 1883,                # MQTT 端口
    'username': 'dji',           # 用户名
    'password': 'lab605605'      # 密码
}
```

### 2. 无人机配置 (第 32-53 行)

```python
UAV_CONFIGS = [
    {
        'name': 'UAV-001',                           # 显示名称
        'sn': '9N9CN2J0012CXY',                      # 网关序列号
        'user_id': 'pilot_1',                        # 用户ID
        'callsign': 'Pilot 1',                       # 呼号
        'video_id': '9N9CN2J0012CXY/39-0-7/normal-0', # 视频流ID
    },
    # ... 另外两台无人机
]
```

**video_id 格式说明:**
- 格式: `{sn}/{camera_index}/{video_index}`
- `{sn}`: 视频源设备序列号
- `{camera_index}`: 相机索引，格式为 `{type-subtype-gimbalindex}`
  - 常见值: `39-0-7` (主相机)
- `{video_index}`: 码流索引
  - `normal-0`: 普通码流

### 3. 直播配置 (第 56-60 行)

```python
LIVE_CONFIG = {
    'url_type': 1,   # 协议类型
    'url': 'rtmp://192.168.1.100:1935/live/stream',  # 推流地址
    'video_quality': 0,  # 视频质量
}
```

**url_type 选项:**
- `0` - 声网 Agora
- `1` - RTMP
- `3` - GB28181
- `4` - WebRTC (仅支持 WHIP 协议)

**video_quality 选项:**
- `0` - 自适应
- `1` - 流畅 (960×540, 512Kbps)
- `2` - 标清 (1280×720, 1Mbps)
- `3` - 高清 (1280×720, 1.5Mbps)
- `4` - 超清 (1920×1080, 3Mbps)

**各协议的 url 格式示例:**

**RTMP:**
```
rtmp://192.168.1.1:8080/live
```

**GB28181:**
```
serverIP=192.168.1.1&serverPort=8080&serverID=34000000000000000000&agentID=300000000010000000000&agentPassword=0000000&localPort=7060&channel=340000000000000000000
```

**声网 Agora:**
```
channel=1ZNDH360010162_39-0-7&sn=1ZNDH360010162&token=006dca67721582a...&uid=50000
```
注意：token 中的特殊字符（如 `+`）需要 URL encode

**WebRTC (WHIP):**
```
http://192.168.1.1:8080/rtc/v1/whip/?app=live&stream=livestream
```

### 4. OSD/HSI 频率 (第 63-64 行)

```python
OSD_FREQUENCY = 100  # Hz - OSD 数据推送频率
HSI_FREQUENCY = 10   # Hz - HSI 数据推送频率
```

## 使用步骤

### 1. 运行程序

```bash
python3 live.py
```

### 2. 选择无人机

程序会显示可用的无人机列表：

```
               可用无人机列表
┏━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ 编号 ┃ 名称    ┃ 序列号         ┃ 呼号    ┃
┡━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│  1   │ UAV-001 │ 9N9CN2J0012CXY │ Pilot 1 │
│  2   │ UAV-002 │ 9N9CN8400164WH │ Pilot 2 │
│  3   │ UAV-003 │ 9N9CN180011TJN │ Pilot 3 │
└──────┴─────────┴────────────────┴─────────┘
```

输入编号（1-3）选择要连接的无人机。

### 3. 查看配置

程序会显示当前的直播推流配置，确认无误后继续。

### 4. 在 DJI Pilot APP 上授权

程序会提示：
```
🔔 请在 DJI Pilot APP 上允许控制权，然后按 Enter 继续...
```

在手机/遥控器的 DJI Pilot APP 上点击"允许"，然后按 Enter。

### 5. 查看 MQTT 消息

程序会美化显示发送的请求和接收的响应：

**发送的请求：**
```json
{
  "bid": "f9f07aad-d1f1-4dc1-8ad0-a3417fd365cc",
  "data": {
    "url": "rtmp://192.168.1.100:1935/live/stream",
    "url_type": 1,
    "video_id": "9N9CN2J0012CXY/39-0-7/normal-0",
    "video_quality": 0
  },
  "tid": "b103b00a-3fcc-476e-9cb6-bc5e27d2defd",
  "timestamp": 1734425015702,
  "method": "live_start_push"
}
```

**接收的响应：**
```json
{
  "bid": "f9f07aad-d1f1-4dc1-8ad0-a3417fd365cc",
  "data": {
    "result": 0  // 0 表示成功，非0表示错误
  },
  "tid": "b103b00a-3fcc-476e-9cb6-bc5e27d2defd",
  "timestamp": 1734425016105,
  "method": "live_start_push"
}
```

### 6. 退出

按 Enter 键停止直播并退出程序。程序会自动清理资源（停止心跳、断开连接）。

## 常见问题

### Q: 如何修改推流地址？

A: 修改文件顶部的 `LIVE_CONFIG['url']`：

```python
LIVE_CONFIG = {
    'url': 'rtmp://你的服务器地址:端口/应用名/流名',
    # ...
}
```

### Q: 如何添加更多无人机？

A: 在 `UAV_CONFIGS` 列表中添加新的配置项：

```python
UAV_CONFIGS = [
    # ... 现有配置 ...
    {
        'name': 'UAV-004',
        'sn': '新的序列号',
        'user_id': 'pilot_4',
        'callsign': 'Pilot 4',
        'video_id': '新的序列号/39-0-7/normal-0',
    },
]
```

### Q: 如何测试不同的视频质量？

A: 修改 `LIVE_CONFIG['video_quality']`：

```python
LIVE_CONFIG = {
    'video_quality': 4,  # 改为超清
    # ...
}
```

### Q: result 返回非0是什么意思？

A: `result` 字段是 DJI 的错误码：
- `0` - 成功
- 非0 - 失败，具体错误信息会显示在响应的 `message` 字段中

## 依赖项

- `djisdk` - DJI Python SDK
- `rich` - 终端美化库

## 技术细节

程序流程：
1. 用户选择无人机 → 2. 建立 MQTT 连接 → 3. 请求控制权 → 4. 等待用户授权 → 5. 进入 DRC 模式 → 6. 启动心跳 → 7. 发送直播推流请求 → 8. 显示响应 → 9. 保持连接 → 10. 清理资源

MQTT 通信：
- **下行 Topic**: `thing/product/{gateway_sn}/services`
- **上行 Topic**: `thing/product/{gateway_sn}/services_reply`
- **Method**: `live_start_push`

## 许可

遵循项目主许可协议。
