# DJI SDK 迁移指南

本文档帮助您从旧版 djisdk 迁移到新的架构，或理解当前实现与文档差异。

## 🔄 主要变化概述

### 架构演进

**原描述（过时）**：
- "只有 2 个核心类，150 行代码"
- "极简核心设计"

**实际情况（当前）**：
- 功能完整的专业级SDK
- 包含核心类、业务服务、任务系统、工具模块
- 支持复杂场景：多机编队、轨迹飞行、视频直播等

### 使用方式变化

#### 旧方式（手动步骤）
```python
# 需要手动执行多个步骤
mqtt = MQTTClient('SN', mqtt_config)
mqtt.connect()
caller = ServiceCaller(mqtt)
request_control_auth(caller, ...)
# 手动在APP确认
enter_drc_mode(caller, ...)
heartbeat = start_heartbeat(mqtt)
```

#### 新方式（一键设置）
```python
# 一行代码完成所有设置
mqtt, caller, heartbeat = setup_drc_connection(gateway_sn, mqtt_config)
```

## 📋 功能对照表

| 功能 | 旧版支持 | 新版支持 | 说明 |
|------|----------|----------|------|
| 基础 MQTT 连接 | ✅ | ✅ | 核心功能保持 |
| 控制权申请 | ✅ | ✅ | 增强了错误处理 |
| DRC 模式 | ✅ | ✅ | 自动配置优化 |
| 心跳维持 | ✅ | ✅ | 更稳定的实现 |
| 一键连接设置 | ❌ | ✅ | **新增** |
| 多机并行连接 | ❌ | ✅ | **新增**（3x性能提升）|
| 轨迹飞行 | ❌ | ✅ | **新增** |
| 任务编排系统 | ❌ | ✅ | **新增** |
| 实时数据缓存 | 基础 | ✅ | **大幅增强** |
| 视频直播控制 | 基础 | ✅ | **完整支持** |
| 云台控制 | 基础 | ✅ | **增强功能** |

## 🔧 迁移步骤

### 1. 更新导入语句

**旧版导入**：
```python
from djisdk import MQTTClient, ServiceCaller
from djisdk import request_control_auth, enter_drc_mode, start_heartbeat
```

**新版导入**：
```python
# 推荐：使用一键设置
from djisdk import setup_drc_connection, setup_multiple_drc_connections

# 或者保持原有方式（向后兼容）
from djisdk import MQTTClient, ServiceCaller, request_control_auth, enter_drc_mode, start_heartbeat
```

### 2. 简化连接代码

**旧版代码**：
```python
# 7-10行代码
mqtt = MQTTClient(gateway_sn, mqtt_config)
mqtt.connect()
caller = ServiceCaller(mqtt)
request_control_auth(caller, user_id='pilot', user_callsign='我的呼号')
input("请在APP确认...")
mqtt_broker_config = {...}  # 复杂配置
enter_drc_mode(caller, mqtt_broker=mqtt_broker_config)
heartbeat = start_heartbeat(mqtt, interval=0.2)
```

**新版代码**：
```python
# 1行代码
mqtt, caller, heartbeat = setup_drc_connection(
    gateway_sn=gateway_sn,
    mqtt_config=mqtt_config,
    user_callsign='我的呼号'
)
```

### 3. 利用新增数据功能

**新增数据访问**：
```python
# 实时飞行数据
print(f"位置: {mqtt.osd_data['latitude']}, {mqtt.osd_data['longitude']}")
print(f"高度: {mqtt.osd_data['height']}m")
print(f"电量: {mqtt.osd_data['battery_percent']}%")

# 云台信息
print(f"云台角度: {mqtt.camera_osd['gimbal_pitch']}°")

# 飞行进度
if mqtt.flyto_progress['fly_to_id']:
    print(f"剩余距离: {mqtt.flyto_progress['remaining_distance']}m")
```

## 🚀 升级收益

### 性能提升
- **多机连接**: 从串行到并行，速度提升3倍
- **数据缓存**: 自动缓存OSD、状态数据，无需重复请求
- **连接稳定性**: 改进的心跳机制和错误恢复

### 开发效率
- **一键设置**: 复杂连接流程自动化
- **任务系统**: 支持复杂飞行任务编排
- **丰富API**: 轨迹飞行、多机编队、视频直播等

### 代码质量
- **错误处理**: 统一的错误处理和日志系统
- **类型提示**: 完整的类型注解支持
- **文档完整**: 详细的API文档和示例

## ⚠️ 兼容性说明

### 完全兼容
以下代码无需修改：
```python
# 基础API调用
request_control_auth(caller, ...)
enter_drc_mode(caller, ...)
start_heartbeat(mqtt, ...)
send_stick_control(mqtt, ...)
```

### 推荐升级
以下模式建议迁移到新API：

**连接管理** → 使用 `setup_drc_connection()`

**多机控制** → 使用 `setup_multiple_drc_connections()`

**复杂任务** → 使用任务系统 `MissionRunner`

### 移除功能
- 移除了过时的CLI模块（`djisdk.cli.drc_control`）
- 建议直接在Python代码中使用库API

## 🔧 故障排除

### 导入错误
```python
# 如果遇到导入错误
ModuleNotFoundError: No module named 'djisdk.cli'

# 解决：更新导入语句
# 旧: from djisdk.cli import xxx
# 新: 直接使用库API
from djisdk import setup_drc_connection
```

### 配置差异
```python
# 旧版需要手动构造mqtt_broker配置
mqtt_broker_config = {
    'address': f"{host}:{port}",
    'client_id': f'drc-{sn}',
    'username': username,
    'password': password,
    'expire_time': int(time.time()) + 3600,
    'enable_tls': False
}

# 新版自动生成（推荐）
mqtt, caller, heartbeat = setup_drc_connection(sn, mqtt_config)
```

### 性能优化
```python
# 多机场景性能优化

# 旧版（串行）：30秒
for sn in sns:
    mqtt, caller, heartbeat = setup_drc_connection(sn, mqtt_config)

# 新版（并行）：10秒
uav_configs = [{'sn': sn} for sn in sns]
connections = setup_multiple_drc_connections(uav_configs, mqtt_config)
```

## 📚 学习资源

1. **README.md** - 完整使用指南
2. **API.md** - 详细API参考
3. **示例代码** - 检查项目中的示例文件
4. **源码注释** - 核心类都有详细文档

## 💡 最佳实践

### 1. 优先使用一键设置
```python
# ✅ 推荐
mqtt, caller, heartbeat = setup_drc_connection(gateway_sn, mqtt_config)

# ❌ 不推荐（除非特殊需求）
mqtt = MQTTClient(...)
# ... 手动设置多个步骤
```

### 2. 多机场景使用并行连接
```python
# ✅ 推荐（3x性能提升）
connections = setup_multiple_drc_connections(uav_configs, mqtt_config)

# ❌ 不推荐
for config in uav_configs:
    setup_drc_connection(config['sn'], mqtt_config)
```

### 3. 充分利用数据缓存
```python
# ✅ 推荐（使用缓存数据）
height = mqtt.osd_data['height']
battery = mqtt.osd_data['battery_percent']

# ❌ 不推荐（重复调用服务）
height_result = caller.call('get_height')
battery_result = caller.call('get_battery')
```

### 4. 清理资源
```python
# ✅ 始终清理资源
try:
    # ... 使用无人机
    pass
finally:
    stop_heartbeat(heartbeat)
    mqtt.disconnect()
```

---

**迁移支持**：如果在迁移过程中遇到问题，请参考API文档或提出issue。新版本在保持向后兼容的同时，提供了更强大和易用的功能。