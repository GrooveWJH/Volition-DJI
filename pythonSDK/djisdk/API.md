# DJI SDK API 参考文档

本文档详细介绍了 djisdk 库的所有 API 接口、参数说明和使用示例。

## 📋 目录

- [核心类](#核心类)
  - [MQTTClient](#mqttclient)
  - [ServiceCaller](#servicecaller)
- [连接管理](#连接管理)
- [飞行控制](#飞行控制)
- [视频直播](#视频直播)
- [任务系统](#任务系统)
- [数据监控](#数据监控)
- [工具函数](#工具函数)

---

## 核心类

### MQTTClient

MQTT 连接管理和数据缓存的核心类。

#### 构造函数

```python
MQTTClient(gateway_sn: str, mqtt_config: Dict[str, Any])
```

**参数**：
- `gateway_sn`: 无人机网关序列号
- `mqtt_config`: MQTT连接配置
  - `host`: MQTT服务器地址
  - `port`: MQTT端口（通常1883）
  - `username`: 用户名
  - `password`: 密码
  - `enable_tls`: 是否启用TLS（可选，默认False）

#### 主要方法

```python
# 连接到MQTT服务器
client.connect()

# 断开连接
client.disconnect()

# 检查在线状态
is_online = client._is_online()

# 获取OSD数据频率
frequency = client._get_osd_frequency()
```

#### 数据属性

```python
# OSD飞行数据
client.osd_data = {
    'latitude': float,           # 纬度
    'longitude': float,          # 经度
    'height': float,             # 高度（米）
    'attitude_head': float,      # 航向角（度）
    'horizontal_speed': float,   # 水平速度（m/s）
    'speed_x': float,            # X轴速度
    'speed_y': float,            # Y轴速度
    'speed_z': float,            # Z轴速度
    'battery_percent': int,      # 电池百分比
    'down_distance': float,      # 下视距离
}

# 云台相机数据
client.camera_osd = {
    'payload_index': str,        # 相机索引（如"88-0-0"）
    'gimbal_pitch': float,       # 云台俯仰角
    'gimbal_roll': float,        # 云台横滚角
    'gimbal_yaw': float,         # 云台偏航角
}

# 飞行状态
client.drone_state = {
    'mode_code': int,            # 飞行模式代码
    'rth_altitude': float,       # 返航高度
    'distance_limit': float,     # 距离限制
    'height_limit': float,       # 高度限制
}

# Fly-to进度数据
client.flyto_progress = {
    'fly_to_id': str,            # 飞行任务ID
    'status': str,               # 状态（progress/ok/failed/cancel）
    'remaining_distance': float, # 剩余距离（米）
    'remaining_time': float,     # 剩余时间（秒）
}
```

#### 回调函数

```python
# 添加OSD数据回调
def my_osd_callback(osd_data):
    print(f"高度: {osd_data['height']}m")

client.osd_callbacks.append(my_osd_callback)

# 启用调试模式
client.enable_service_debug = True  # 打印完整JSON响应
```

---

### ServiceCaller

同步服务调用封装类。

#### 构造函数

```python
ServiceCaller(mqtt_client: MQTTClient, timeout: int = 10)
```

**参数**：
- `mqtt_client`: MQTTClient 实例
- `timeout`: 服务调用超时时间（秒）

#### 主要方法

```python
# 调用DJI服务（低级API）
result = caller.call(method: str, data: Dict[str, Any])

# 示例：手动调用服务
result = caller.call("drc_mode_enter", {
    "mqtt_broker": broker_config,
    "osd_frequency": 30
})
```

---

## 连接管理

### setup_drc_connection

一键建立完整 DRC 连接。

```python
setup_drc_connection(
    gateway_sn: str,
    mqtt_config: Dict[str, Any],
    user_id: str = "pilot",
    user_callsign: str = "Callsign",
    osd_frequency: int = 30,
    hsi_frequency: int = 10,
    heartbeat_interval: float = 1.0,
    wait_for_user: bool = True,
    skip_drc_setup: bool = False
) -> Tuple[MQTTClient, ServiceCaller, Optional[threading.Thread]]
```

**参数**：
- `gateway_sn`: 网关序列号
- `mqtt_config`: MQTT配置字典
- `user_id`: 用户ID
- `user_callsign`: 用户呼号（显示在遥控器上）
- `osd_frequency`: OSD数据频率（Hz）
- `hsi_frequency`: HSI数据频率（Hz）
- `heartbeat_interval`: 心跳间隔（秒）
- `wait_for_user`: 等待用户确认控制权
- `skip_drc_setup`: 仅连接MQTT，跳过DRC设置

**返回值**：
- `MQTTClient`: MQTT客户端实例
- `ServiceCaller`: 服务调用器实例
- `threading.Thread`: 心跳线程（或None）

**示例**：
```python
# 完整DRC连接
mqtt, caller, heartbeat = setup_drc_connection(
    gateway_sn='1ZNDH800017VMA',
    mqtt_config={
        'host': '192.168.31.73',
        'port': 1883,
        'username': 'dji',
        'password': 'lab605605'
    },
    user_callsign='我的无人机'
)

# 仅MQTT连接（不申请控制权）
mqtt, caller, _ = setup_drc_connection(
    gateway_sn='1ZNDH800017VMA',
    mqtt_config=mqtt_config,
    skip_drc_setup=True
)
```

### setup_multiple_drc_connections

并行建立多机 DRC 连接（性能提升3倍）。

```python
setup_multiple_drc_connections(
    uav_configs: List[Dict[str, str]],
    mqtt_config: Dict[str, Any],
    osd_frequency: int = 30,
    hsi_frequency: int = 10,
    heartbeat_interval: float = 1.0,
    skip_drc_setup: bool = False
) -> List[Tuple[MQTTClient, ServiceCaller, threading.Thread]]
```

**参数**：
- `uav_configs`: 无人机配置列表，每个包含：
  - `sn`: 网关序列号（必需）
  - `user_id`: 用户ID（可选）
  - `callsign`: 用户呼号（可选）
- 其他参数同 `setup_drc_connection`

**示例**：
```python
uav_configs = [
    {'sn': '1ZNDH800017VMA', 'callsign': 'Alpha-1'},
    {'sn': '1ZNDH800017VMB', 'callsign': 'Bravo-2'},
    {'sn': '1ZNDH800017VMC', 'callsign': 'Charlie-3'}
]

connections = setup_multiple_drc_connections(uav_configs, mqtt_config)

# 使用连接
for mqtt, caller, heartbeat in connections:
    # 控制每架无人机
    pass

# 清理资源
for mqtt, caller, heartbeat in connections:
    stop_heartbeat(heartbeat)
    mqtt.disconnect()
```

---

## 飞行控制

### fly_to_point

飞向指定坐标点。

```python
fly_to_point(
    caller: ServiceCaller,
    latitude: float,
    longitude: float,
    height: float,
    max_speed: int = 12,
    fly_to_id: Optional[str] = None
) -> str
```

**参数**：
- `caller`: 服务调用器
- `latitude`: 目标纬度（-90~90度）
- `longitude`: 目标经度（-180~180度）
- `height`: 目标高度（椭球高，WGS84模型）
- `max_speed`: 最大飞行速度（0-15 m/s）
- `fly_to_id`: 任务ID（可选，自动生成）

**返回值**：
- `str`: 飞行任务ID，可用于监控进度

**安全说明**：
- 无人机有20米最低安全高度保护
- 如果当前高度低于20米，会先上升至20米

**示例**：
```python
# 飞向天安门广场
fly_to_id = fly_to_point(
    caller,
    latitude=39.9041999,
    longitude=116.4073963,
    height=100.0,
    max_speed=10
)

# 监控飞行进度
import time
while True:
    progress = mqtt.flyto_progress
    if progress['fly_to_id'] == fly_to_id:
        print(f"剩余距离: {progress['remaining_distance']}m")
        print(f"剩余时间: {progress['remaining_time']}s")

        if progress['status'] in ['wayline_ok', 'wayline_failed']:
            break

    time.sleep(1)
```

### return_home

一键返航至起飞点。

```python
return_home(caller: ServiceCaller) -> Dict[str, Any]
```

**示例**：
```python
# 执行返航
return_home(caller)
print("返航指令已发送")
```

### send_stick_control

实时杆量控制（推荐5-10Hz频率）。

```python
send_stick_control(
    mqtt_client: MQTTClient,
    roll: int = 1024,
    pitch: int = 1024,
    throttle: int = 1024,
    yaw: int = 1024
) -> None
```

**参数**：
- `mqtt_client`: MQTT客户端（注意：不是ServiceCaller）
- `roll`: 横滚通道（364-1684，中值1024）
- `pitch`: 俯仰通道（364-1684，中值1024）
- `throttle`: 升降通道（364-1684，中值1024）
- `yaw`: 偏航通道（364-1684，中值1024）

**杆量说明**：
- `1024`: 中值（悬停）
- `1024 + 330`: 半杆
- `1024 + 660`: 满杆
- `1024 - 330`: 反向半杆
- `1024 - 660`: 反向满杆

**示例**：
```python
import time

# 向前飞行5秒
for _ in range(50):  # 10Hz频率
    send_stick_control(mqtt, pitch=1354)  # 前进半杆
    time.sleep(0.1)

# 悬停
send_stick_control(mqtt)  # 所有通道中值

# 向左飞行
send_stick_control(mqtt, roll=694)  # 左半杆

# 上升
send_stick_control(mqtt, throttle=1354)  # 上升半杆

# 顺时针旋转
send_stick_control(mqtt, yaw=1354)  # 右偏航半杆
```

---

## 视频直播

### change_live_lens

切换直播镜头类型。

```python
change_live_lens(
    caller: ServiceCaller,
    video_id: str,
    video_type: str = "normal"
) -> Dict[str, Any]
```

**参数**：
- `video_id`: 视频流ID，格式：`{sn}/{camera_index}/{video_index}`
- `video_type`: 镜头类型
  - `"normal"`: 默认镜头
  - `"thermal"`: 红外镜头
  - `"wide"`: 广角镜头
  - `"zoom"`: 变焦镜头

**示例**：
```python
# 切换到变焦镜头
change_live_lens(caller, "1ZNDH800017VMA/88-0-0/zoom-0", "zoom")

# 切换到红外镜头
change_live_lens(caller, "1ZNDH800017VMA/88-0-0/thermal-0", "thermal")
```

### set_live_quality

设置直播画质。

```python
set_live_quality(
    caller: ServiceCaller,
    video_id: str,
    video_quality: int
) -> Dict[str, Any]
```

**参数**：
- `video_quality`: 画质等级
  - `0`: 自适应
  - `1`: 流畅（960x540, 512Kbps）
  - `2`: 标清（1280x720, 1Mbps）
  - `3`: 高清（1280x720, 1.5Mbps）
  - `4`: 超清（1920x1080, 3Mbps）

**示例**：
```python
# 设置为超清画质
set_live_quality(caller, "1ZNDH800017VMA/88-0-0/normal-0", 4)

# 设置为自适应
set_live_quality(caller, "1ZNDH800017VMA/88-0-0/normal-0", 0)
```

### start_live_push / stop_live_push

开始/停止推流到自定义服务器。

```python
start_live_push(
    caller: ServiceCaller,
    url: str,
    video_id: str,
    url_type: int = 0,
    video_quality: int = 0
) -> Dict[str, Any]

stop_live_push(caller: ServiceCaller, video_id: str) -> Dict[str, Any]
```

**参数**：
- `url`: 推流URL
- `url_type`: 推流协议
  - `0`: RTMP
  - `1`: RTSP
  - `2`: GB28181

**示例**：
```python
# 开始RTMP推流
start_live_push(
    caller,
    url="rtmp://192.168.31.73:1935/live/stream1",
    video_id="1ZNDH800017VMA/88-0-0/normal-0",
    url_type=0,  # RTMP
    video_quality=4  # 超清
)

# 停止推流
stop_live_push(caller, "1ZNDH800017VMA/88-0-0/normal-0")
```

---

## 任务系统

### MissionRunner

任务执行引擎，支持串行和并行任务执行。

```python
from djisdk import MissionRunner

# 创建任务运行器
runner = MissionRunner(missions: List[Mission])

# 执行所有任务
runner.run()

# 并行运行多个任务
run_parallel_missions(missions: List[Mission])
```

### create_trajectory_mission

创建轨迹飞行任务。

```python
create_trajectory_mission(
    mqtt: MQTTClient,
    caller: ServiceCaller,
    trajectory_file: str
) -> Mission
```

**轨迹文件格式（CSV）**：
```csv
latitude,longitude,height,speed,action
39.042751,117.723825,50,5,0
39.043122,117.724156,60,8,1
39.042445,117.725234,55,6,0
```

**字段说明**：
- `latitude`: 纬度
- `longitude`: 经度
- `height`: 高度（米）
- `speed`: 飞行速度（m/s）
- `action`: 动作类型（0=飞行，1=悬停）

**示例**：
```python
# 加载并执行轨迹
mission = create_trajectory_mission(mqtt, caller, "waypoints.csv")
runner = MissionRunner([mission])
runner.run()
```

### create_takeoff_mission

创建起飞任务。

```python
create_takeoff_mission(
    mqtt: MQTTClient,
    caller: ServiceCaller,
    target_height: float = 50.0
) -> Mission
```

---

## 数据监控

### 实时数据访问

```python
# OSD飞行数据
position = (mqtt.osd_data['latitude'], mqtt.osd_data['longitude'])
height = mqtt.osd_data['height']
battery = mqtt.osd_data['battery_percent']
heading = mqtt.osd_data['attitude_head']

# 云台角度
gimbal_pitch = mqtt.camera_osd['gimbal_pitch']
gimbal_yaw = mqtt.camera_osd['gimbal_yaw']

# 飞行状态
mode = mqtt.drone_state['mode_code']
rth_alt = mqtt.drone_state['rth_altitude']

# 飞行进度
if mqtt.flyto_progress['fly_to_id']:
    remaining_dist = mqtt.flyto_progress['remaining_distance']
    remaining_time = mqtt.flyto_progress['remaining_time']
    status = mqtt.flyto_progress['status']
```

### 连接状态监控

```python
# 检查在线状态
if mqtt._is_online():
    print("无人机在线")
else:
    print("无人机离线")

# OSD数据频率
freq = mqtt._get_osd_frequency()
print(f"OSD频率: {freq:.1f}Hz")

# 添加数据回调
def data_monitor(osd_data):
    battery = osd_data.get('battery_percent', 0)
    if battery < 20:
        print("⚠️ 电量低警告")

mqtt.osd_callbacks.append(data_monitor)
```

---

## 工具函数

### wait_for_condition

等待指定条件成立。

```python
from djisdk import wait_for_condition

# 等待到达指定高度
success = wait_for_condition(
    lambda: mqtt.osd_data['height'] > 50,
    timeout=30,
    interval=0.5
)

# 等待电量充足
success = wait_for_condition(
    lambda: mqtt.osd_data['battery_percent'] > 50,
    timeout=60
)
```

### monitor_flyto_progress

监控fly_to_point进度。

```python
from djisdk import monitor_flyto_progress

fly_to_id = fly_to_point(caller, lat, lon, height)

# 阻塞监控直到完成
result = monitor_flyto_progress(mqtt, fly_to_id, timeout=120)

if result['success']:
    print("飞行完成")
else:
    print(f"飞行失败: {result['reason']}")
```

### start_heartbeat / stop_heartbeat

心跳管理（通常由setup_drc_connection自动处理）。

```python
from djisdk import start_heartbeat, stop_heartbeat

# 手动启动心跳
heartbeat_thread = start_heartbeat(mqtt, interval=0.2)

# 停止心跳
stop_heartbeat(heartbeat_thread)
```

---

## 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| -1 | 服务调用失败 | 检查网络连接和服务器状态 |
| 314001 | 未获得控制权 | 在DJI Pilot APP上确认控制权申请 |
| 314002 | 控制权已被其他设备占用 | 等待其他设备释放或手动接管 |
| 314003 | DRC模式进入失败 | 检查MQTT配置和网络连接 |
| 341001 | 飞行指令被拒绝 | 检查飞行模式和安全限制 |
| 341002 | 无人机未起飞 | 先执行起飞或切换到适当模式 |

---

## 调试技巧

### 启用详细日志

```python
# 启用服务调试
mqtt.enable_service_debug = True

# 输出将包含完整的JSON响应
```

### 监控所有数据

```python
def debug_callback(osd_data):
    print(f"OSD: {osd_data}")

def debug_message_handler(client, userdata, msg):
    import json
    try:
        payload = json.loads(msg.payload.decode())
        print(f"收到消息: {msg.topic} -> {payload}")
    except:
        pass

mqtt.osd_callbacks.append(debug_callback)
mqtt.client.on_message = debug_message_handler
```

### 性能分析

```python
import time

start_time = time.time()
result = caller.call("some_service", data)
duration = time.time() - start_time

print(f"服务调用耗时: {duration:.2f}秒")
```

---

**注意**：本文档覆盖了djisdk的主要API。对于特定的高级功能或边缘案例，请参考源代码或联系开发团队。