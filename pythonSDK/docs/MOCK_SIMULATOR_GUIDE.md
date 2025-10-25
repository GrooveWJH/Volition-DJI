# 无人机模拟器使用指南

## 功能介绍

在没有真实无人机时，使用模拟器生成伪造数据用于GUI调试。

**特点：**
- ✅ 几乎真实的飞行数据（圆形轨迹、动态速度、电池消耗）
- ✅ 支持多架无人机（不同轨迹）
- ✅ 零侵入设计（display.py 无需修改）
- ✅ 简单开关（一个环境变量）
- ✅ 向后兼容（默认使用真实连接）

---

## 快速开始

### 启用模拟器模式

```bash
USE_MOCK_DRONE=1 python main.py
```

### 使用真实无人机（默认）

```bash
python main.py
# 或显式禁用
USE_MOCK_DRONE=0 python main.py
```

---

## 模拟数据说明

### GPS 位置
- **轨迹**：圆形飞行，半径约50米，周期约60秒
- **起飞点**：深圳大学城附近（22.538°N, 113.938°E）
- **高度**：正弦波浮动，20±5米（距起飞点）

### 速度数据
- **水平速度**：约5.5 m/s（与圆形轨迹一致）
- **垂直速度**：随高度变化动态计算（数学准确）

### 姿态数据
- **航向角**：跟随飞行方向（0-360°）

### 电池数据
- **消耗**：每分钟下降1%
- **最低电量**：20%（安全着陆电量）

### HSI 数据
- **测高值**：与相对高度一致（厘米单位）
- **传感器状态**：始终正常

### 多机支持
- 每架无人机间隔约100米起飞点
- 相位偏移72°（5架均匀分布）
- 不同的飞行轨迹和航向

---

## 技术实现

### 架构设计

```
djisdk/
└── mock/
    ├── __init__.py         # 导出接口
    └── mock_drone.py       # Mock 类实现（约300行）
        ├── MockMQTTClient      # 模拟 MQTT 客户端
        ├── MockServiceCaller   # 模拟服务调用器
        ├── MockHeartbeatThread # 模拟心跳线程
        └── create_mock_connections()  # 工厂函数
```

### 设计原则（Linus "Good Taste"）

1. **鸭子类型** - 直接实现接口，无需继承
2. **纯函数计算** - 所有数据基于 `time.time()` 计算
3. **无后台线程** - 按需计算，节省资源
4. **零侵入** - GUI 完全无感知

### 数据生成公式

**位置（圆形轨迹）：**
```python
angle = angular_velocity * t + phase_offset
latitude = base_lat + radius * sin(angle)
longitude = base_lon + radius * cos(angle)
height = base_height + 20 + 5 * sin(0.05 * t)
```

**速度（位置的导数）：**
```python
speed_x = radius * angular_velocity * 111000 * cos(angle)
speed_y = -radius * angular_velocity * 111000 * sin(angle)
speed_z = 5 * 0.05 * cos(0.05 * t)
```

**航向角：**
```python
heading = degrees(angle) % 360
```

---

## 测试验证

### 运行接口测试

```bash
python test_mock.py
```

**验证内容：**
- ✅ 所有接口返回正确类型
- ✅ 数据在合理范围内
- ✅ 数据动态变化（1秒后位置、航向变化）
- ✅ 多机轨迹差异（位置、航向不同）

### 运行向后兼容测试

```bash
python test_backward_compat.py
```

**验证内容：**
- ✅ 未设置环境变量 → 真实模式
- ✅ `USE_MOCK_DRONE=0` → 真实模式
- ✅ `USE_MOCK_DRONE=1` → 模拟器模式
- ✅ 其他值 → 真实模式

---

## 代码修改摘要

### main.py（仅15行修改）

```python
import os

# 检查是否使用模拟器
USE_MOCK = os.getenv('USE_MOCK_DRONE', '0') == '1'

if USE_MOCK:
    from djisdk.mock import create_mock_connections
    console.print("[yellow]⚠ 模拟器模式已启用[/yellow]")
    connections = create_mock_connections(UAV_CONFIGS)
else:
    connections = setup_multiple_drc_connections(...)
```

### display.py（零修改）

完全无需修改，继续调用 `mqtt.get_xxx()` 方法。

---

## 常见问题

**Q: 模拟器数据每次运行都一样吗？**
A: 不一样。数据基于 `time.time()` 计算，每次启动时间不同，轨迹起始点也不同。

**Q: 可以模拟多少架无人机？**
A: 理论上无限制，每架无人机通过 `phase_offset` 区分轨迹。

**Q: 模拟器消耗多少资源？**
A: 极少。无后台线程，纯数学计算（sin/cos），30Hz 调用无压力。

**Q: 如何修改飞行轨迹？**
A: 编辑 `djisdk/mock/mock_drone.py` 中的 `flight_radius`, `angular_velocity`, `vertical_amplitude` 等参数。

**Q: 向后兼容吗？**
A: 完全兼容。默认行为（不设置环境变量）仍然使用真实无人机连接。

---

## 示例输出

### 模拟器模式

```
───────────────────────────────── 建立多机连接 ─────────────────────────────────
⚠ 模拟器模式已启用（USE_MOCK_DRONE=1）
数据将由模拟器生成，不连接真实无人机

✓ 所有无人机已就绪 (2 架)
监控运行中... (按 Ctrl+C 退出)

┌─────── 无人机 #1 ───────┐  ┌─────── 无人机 #2 ───────┐
│ 序列号:     9N9CN2J0012CXY │  │ 序列号:     9N9CN8400164WH │
│ 纬度:       22.53800500°   │  │ 纬度:       22.53948900°   │
│ 经度:       113.93849700°  │  │ 经度:       113.93910600°  │
│ 航向角:     5.8°           │  │ 航向角:     77.8°          │
│ 电池电量:   ██████████ 100%│  │ 电池电量:   ██████████ 100%│
└──────────────────────────┘  └──────────────────────────┘
```

---

## 总结

✅ **极简设计** - 仅300行代码，3个Mock类
✅ **零侵入** - GUI无需任何修改
✅ **数学准确** - 速度是位置的导数，数据自洽
✅ **多机支持** - 不同轨迹，真实差异
✅ **向后兼容** - 默认行为不变

**使用方法：**
```bash
USE_MOCK_DRONE=1 python main.py  # 模拟器模式
python main.py                   # 真实无人机模式（默认）
```
