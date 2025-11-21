# DJI Cloud API Python SDK

> **设计哲学**: "简洁实用，拒绝过度工程化" - 专业级无人机控制库

一个功能全面的 DJI 无人机云端控制 Python 库，支持远程控制 (DRC)、实时视频、飞行任务、多机编队等功能。采用模块化设计，从简单控制到复杂任务编排都能轻松应对。

## 🚀 快速开始

### 安装依赖

```bash
pip install paho-mqtt rich
```

### 5 分钟上手：从连接到飞行

```python
from djisdk import setup_drc_connection, fly_to_point, return_home, stop_heartbeat

# 1. 一键建立 DRC 连接（包含控制权、心跳等完整流程）
mqtt_config = {
    'host': '192.168.31.73',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

mqtt, caller, heartbeat = setup_drc_connection(
    gateway_sn='1ZNDH800017VMA',
    mqtt_config=mqtt_config,
    user_callsign='我的呼号'
)

# 2. 飞向目标点
fly_to_point(caller, latitude=39.0427514, longitude=117.7238255, height=100.0)

# 3. 返航
return_home(caller)

# 4. 清理资源
stop_heartbeat(heartbeat)
mqtt.disconnect()
```

## 📋 功能特性

### ✅ 完整的 DRC 控制
- **连接管理**: 一键建立 MQTT 连接、控制权申请、DRC 模式、心跳维持
- **飞行控制**: 一键返航、定点飞行、实时杆量控制
- **多机支持**: 并行控制多架无人机，3倍性能提升

### ✅ 专业视频直播
- **多镜头支持**: 红外、广角、变焦镜头自由切换
- **画质控制**: 5级清晰度设置（自适应~超清）
- **推流管理**: RTMP/RTSP 推流到自定义服务器

### ✅ 高级飞行任务
- **轨迹飞行**: 加载CSV轨迹文件，精准路径飞行
- **任务编排**: 起飞→轨迹→降落的完整任务链
- **并行执行**: 多架无人机同时执行不同任务

### ✅ 智能数据管理
- **实时监控**: OSD数据（位置、姿态、电量）实时缓存
- **状态追踪**: 飞行模式、云台角度、飞行进度
- **频率监控**: 自动检测 OSD 数据频率和连接状态

## 📚 核心 API

### 🔗 连接与控制权

```python
from djisdk import setup_drc_connection, setup_multiple_drc_connections

# 单机连接
mqtt, caller, heartbeat = setup_drc_connection(gateway_sn, mqtt_config)

# 多机并行连接（推荐：3倍性能提升）
uav_configs = [
    {'sn': '1ZNDH800017VMA', 'callsign': 'Alpha-1'},
    {'sn': '1ZNDH800017VMB', 'callsign': 'Bravo-2'},
    {'sn': '1ZNDH800017VMC', 'callsign': 'Charlie-3'}
]
connections = setup_multiple_drc_connections(uav_configs, mqtt_config)
```

### 🛩️ 飞行控制

```python
from djisdk import fly_to_point, return_home, send_stick_control

# 高级飞行：飞向指定坐标
fly_to_id = fly_to_point(
    caller,
    latitude=39.042751,
    longitude=117.723825,
    height=100.0,       # 椭球高度（米）
    max_speed=12        # 最大速度（m/s）
)

# 一键返航
return_home(caller)

# 实时杆量控制（5-10Hz 推荐频率）
import time
for _ in range(50):  # 控制5秒
    send_stick_control(mqtt, pitch=1200, roll=1024, throttle=1024, yaw=1024)  # 前进
    time.sleep(0.1)
```

### 📹 视频直播控制

```python
from djisdk import change_live_lens, set_live_quality, start_live_push, stop_live_push

# 切换到变焦镜头
change_live_lens(caller, video_id="1ZNDH800017VMA/88-0-0/zoom-0", video_type="zoom")

# 设置超清画质
set_live_quality(caller, video_id="1ZNDH800017VMA/88-0-0/zoom-0", video_quality=4)

# 推流到服务器
start_live_push(
    caller,
    url="rtmp://192.168.31.73:1935/live/stream1",
    video_id="1ZNDH800017VMA/88-0-0/zoom-0"
)

# 停止推流
stop_live_push(caller, video_id="1ZNDH800017VMA/88-0-0/zoom-0")
```

### 📊 数据监控

```python
# 实时 OSD 数据
print(f"位置: {mqtt.osd_data['latitude']}, {mqtt.osd_data['longitude']}")
print(f"高度: {mqtt.osd_data['height']}m")
print(f"电量: {mqtt.osd_data['battery_percent']}%")
print(f"航向: {mqtt.osd_data['attitude_head']}°")

# 云台信息
print(f"云台俯仰角: {mqtt.camera_osd['gimbal_pitch']}°")

# 飞行进度（fly_to_point 后）
if mqtt.flyto_progress['fly_to_id']:
    print(f"剩余距离: {mqtt.flyto_progress['remaining_distance']}m")
    print(f"剩余时间: {mqtt.flyto_progress['remaining_time']}s")
```

## 🎯 高级应用场景

### 场景 1：多机编队飞行

```python
from djisdk import setup_multiple_drc_connections, create_trajectory_mission, run_parallel_missions

# 1. 并行建立连接
uav_configs = [
    {'sn': 'UAV001', 'callsign': 'Leader'},
    {'sn': 'UAV002', 'callsign': 'Wingman-1'},
    {'sn': 'UAV003', 'callsign': 'Wingman-2'}
]
connections = setup_multiple_drc_connections(uav_configs, mqtt_config)

# 2. 创建不同轨迹任务
missions = []
for i, (mqtt, caller, heartbeat) in enumerate(connections):
    trajectory_file = f"formation_path_{i+1}.csv"
    mission = create_trajectory_mission(mqtt, caller, trajectory_file)
    missions.append(mission)

# 3. 同时执行所有任务
run_parallel_missions(missions)
```

### 场景 2：自动巡检任务

```python
import time
from djisdk import setup_drc_connection, fly_to_point, change_live_lens, wait_for_condition

# 建立连接
mqtt, caller, heartbeat = setup_drc_connection(gateway_sn, mqtt_config)

# 巡检点列表
inspection_points = [
    (39.042751, 117.723825, 50),   # 检查点1
    (39.043122, 117.724156, 60),   # 检查点2
    (39.042445, 117.725234, 55),   # 检查点3
]

for i, (lat, lon, height) in enumerate(inspection_points, 1):
    print(f"飞往检查点 {i}...")

    # 飞往检查点
    fly_to_point(caller, lat, lon, height, max_speed=8)

    # 等待到达 (实际应用中可监控 flyto_progress)
    time.sleep(30)

    # 切换到变焦镜头进行检查
    change_live_lens(caller, video_id=f"{gateway_sn}/88-0-0/zoom-0", video_type="zoom")

    # 停留5秒进行观察
    time.sleep(5)

    print(f"检查点 {i} 完成")

# 返航
return_home(caller)
```

### 场景 3：CSV轨迹飞行

```python
# waypoints.csv 内容：
# latitude,longitude,height,speed,action
# 39.042751,117.723825,50,5,0
# 39.043122,117.724156,60,8,1
# 39.042445,117.725234,55,6,0

from djisdk import MissionRunner, load_trajectory, create_trajectory_mission

# 加载轨迹
waypoints = load_trajectory("waypoints.csv")
print(f"加载了 {len(waypoints)} 个航点")

# 创建并执行轨迹任务
mission = create_trajectory_mission(mqtt, caller, "waypoints.csv")
runner = MissionRunner([mission])
runner.run()
```

## 🔧 扩展开发

### 添加新的 DJI 服务

在 `djisdk/services/commands.py` 中添加新服务**超级简单**：

```python
# djisdk/services/commands.py

def send_custom_command(caller: ServiceCaller, param1: str, param2: int) -> Dict[str, Any]:
    """自定义 DJI 服务调用"""
    console.print(f"[cyan]发送自定义指令: {param1}[/cyan]")
    return _call_service(
        caller,
        "your_dji_method_name",        # DJI 官方方法名
        {"param1": param1, "param2": param2},  # 请求参数
        "自定义指令执行成功"                    # 成功提示
    )
```

然后在 `services/__init__.py` 和 `djisdk/__init__.py` 中导出即可使用。

**优势**：
- ✅ **零重复代码** - 复用 `_call_service()` 通用包装
- ✅ **统一错误处理** - 自动处理异常和响应码检查
- ✅ **统一日志风格** - Rich 彩色输出，调试友好
- ✅ **向后兼容** - 新服务不影响现有代码

## 📁 架构设计

### 🏗️ 目录结构

```
djisdk/
├── core/                          # 核心层（连接与服务调用）
│   ├── mqtt_client.py            # MQTT连接管理 + 数据缓存
│   └── service_caller.py         # 同步服务调用封装
├── services/                      # 业务层（DJI服务）
│   ├── commands.py               # 统一服务调用（控制权/DRC/直播/飞行）
│   ├── connection_manager.py     # 多机连接管理
│   ├── drc_commands.py          # DRC下行指令（杆量/云台）
│   └── heartbeat.py             # 心跳维持线程
├── primitives/                   # 基础操作原语
│   ├── stick.py                 # 杆量控制工具
│   ├── waypoint.py              # 航点飞行工具
│   └── wait.py                  # 等待条件工具
├── tasks/                       # 高级任务编排
│   ├── runner.py                # 任务执行引擎
│   ├── takeoff.py               # 起飞任务
│   ├── trajectory.py            # 轨迹飞行任务
│   ├── ivas_executor.py         # IVAS集成执行器
│   └── display.py               # 任务状态显示
├── mock/                        # 模拟与测试
│   └── mock_drone.py            # 无人机模拟器
├── utils.py                     # 通用工具函数
├── live_utils.py               # 直播相关工具
└── README.md                   # 本文档
```

### 🔄 数据流架构

```
用户代码
    ↓
业务函数 (commands.py)
    ↓
_call_service() 通用包装
    ↓
ServiceCaller (同步调用)
    ↓
MQTTClient (连接管理)
    ↓
DJI Cloud API (MQTT)
```

**核心优势**：

1. **极简核心** - 只有 `MQTTClient` + `ServiceCaller` 两个核心类
2. **消除重复** - `_call_service()` 包装消除90%重复代码
3. **数据缓存** - 自动缓存 OSD、状态、拓扑数据供实时查询
4. **任务导向** - 从单一指令到复杂任务编排的完整支持

### 💡 设计亮点

#### 1️⃣ 智能数据管理

```python
# 自动缓存所有重要数据
print(mqtt.osd_data)        # 实时飞行数据
print(mqtt.camera_osd)      # 云台信息
print(mqtt.drone_state)     # 飞行模式等状态
print(mqtt.flyto_progress)  # 飞行进度
print(mqtt.topo_data)       # 设备拓扑
```

#### 2️⃣ 任务编排系统

```python
# 复杂任务可拆解为简单步骤
mission = create_trajectory_mission(mqtt, caller, "path.csv")
runner = MissionRunner([mission])
runner.run()  # 自动执行：起飞 → 轨迹飞行 → 降落
```

#### 3️⃣ 并行优化

```python
# 多机连接：串行 vs 并行
# 串行：30秒 (10s×3)
for sn in sns:
    setup_drc_connection(sn, mqtt_config)

# 并行：10秒 (同时连接)
connections = setup_multiple_drc_connections(uav_configs, mqtt_config)
```

## 🐛 调试与监控

### 日志系统

所有输出通过 `rich.console` 彩色显示：

- 🔵 **蓝色** `[cyan]` - 发送请求
- 🟢 **绿色** `[green]` - 成功响应
- 🔴 **红色** `[red]` - 错误/异常
- 🟡 **黄色** `[yellow]` - 警告信息
- 🔸 **灰色** `[dim]` - 调试详情

### 数据监控

```python
# 启用调试模式
mqtt.enable_service_debug = True  # 打印完整响应JSON

# 添加 OSD 回调
def monitor_osd(osd_data):
    print(f"高度: {osd_data['height']:.1f}m")

mqtt.osd_callbacks.append(monitor_osd)

# 检查连接状态
import time
print(f"OSD频率: {mqtt._get_osd_frequency():.1f}Hz")
print(f"连接状态: {'在线' if mqtt._is_online() else '离线'}")
```

## 🔧 配置指南

### 基础配置

```python
# MQTT 连接配置
mqtt_config = {
    'host': '192.168.31.73',      # MQTT服务器地址
    'port': 1883,                 # MQTT端口
    'username': 'dji',            # 用户名
    'password': 'lab605605',      # 密码
    'enable_tls': False           # 是否启用TLS加密
}

# DRC 连接配置
setup_drc_connection(
    gateway_sn='1ZNDH800017VMA',  # 网关序列号
    mqtt_config=mqtt_config,
    user_callsign='我的呼号',      # 显示在遥控器上的呼号
    osd_frequency=30,             # OSD数据频率(Hz)
    hsi_frequency=10,             # HSI数据频率(Hz)
    heartbeat_interval=0.2,       # 心跳间隔(秒)
    wait_for_user=True            # 等待用户确认控制权
)
```

### 高级配置

```python
# 多机配置
uav_configs = [
    {
        'sn': '1ZNDH800017VMA',
        'user_id': 'pilot1',      # 用户ID
        'callsign': 'Alpha-Leader' # 呼号
    },
    {
        'sn': '1ZNDH800017VMB',
        'user_id': 'pilot2',
        'callsign': 'Bravo-Wing'
    }
]
```

## ⚠️ 重要说明

### 安全注意事项

1. **控制权管理**:
   - 必须在 DJI Pilot APP 上手动确认控制权
   - 遥控器始终保持最高优先级（紧急接管）

2. **飞行安全**:
   - 飞机有20米最低安全高度保护
   - 建议在空旷区域进行测试
   - 保持网络连接稳定，监控心跳状态

3. **资源管理**:
   - 使用完毕后及时断开连接
   - 多机应用注意 client_id 冲突

### 性能优化建议

1. **杆量控制**: 保持5-10Hz频率，过高会增加网络负担
2. **多机连接**: 优先使用 `setup_multiple_drc_connections()`
3. **数据监控**: 根据需要设置合适的 OSD 频率

## 📦 编程接口总览

```python
# 核心
from djisdk import MQTTClient, ServiceCaller

# 连接管理
from djisdk import setup_drc_connection, setup_multiple_drc_connections

# 飞行控制
from djisdk import fly_to_point, return_home, send_stick_control

# 视频直播
from djisdk import change_live_lens, set_live_quality, start_live_push, stop_live_push

# 任务系统
from djisdk import MissionRunner, create_trajectory_mission, load_trajectory

# 工具函数
from djisdk import wait_for_condition, monitor_flyto_progress
```

## ⚖️ 许可证

MIT

---

**"代码即文档，简洁即优雅"** - djisdk 团队

欢迎贡献代码或提出改进建议！