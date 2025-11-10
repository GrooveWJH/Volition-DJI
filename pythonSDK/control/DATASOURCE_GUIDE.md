# 数据源配置指南

## 概述

控制系统现在支持灵活的数据源配置，允许你选择位置数据和航向角数据的来源：

- **位置数据源**：VRPN（动捕系统）或 UWB（超宽带定位）
- **航向角数据源**：VRPN（动捕系统）或无人机自身姿态（MQTT OSD数据）

## 配置方法

所有数据源配置都在 `control/config.py` 文件中：

```python
# ========== 数据源配置 ==========
# 几何定位源选择: 'vrpn' 或 'uwb'
POSITION_SOURCE = 'vrpn'  # 位置数据来源

# UWB 设备配置（当 POSITION_SOURCE = 'uwb' 时使用）
UWB_DEVICE = 'uwb://192.168.31.200:8888/drone1'  # UWB 设备地址

# 航向角数据源选择: 'vrpn' 或 'drone'
YAW_SOURCE = 'vrpn'  # 'vrpn' = 从动捕系统获取, 'drone' = 从无人机自身获取
```

## 使用场景

### 场景 1: 纯 VRPN（默认）

适用于有动捕系统的实验室环境。

```python
POSITION_SOURCE = 'vrpn'
YAW_SOURCE = 'vrpn'
```

**特点**：
- ✅ 位置和航向角都来自动捕系统
- ✅ 高精度、低延迟
- ✅ 数据同步性好
- ❌ 需要动捕设备和标定

**使用程序**：
```bash
python control/plane_main.py   # 位置控制
python control/yaw_main.py     # 航向角控制
```

---

### 场景 2: UWB 位置 + 无人机航向角

适用于户外或无动捕环境，使用 UWB 定位系统。

```python
POSITION_SOURCE = 'uwb'
YAW_SOURCE = 'drone'
```

**特点**：
- ✅ 不依赖动捕系统
- ✅ 适合户外大范围飞行
- ✅ 成本较低
- ⚠️ UWB 精度略低于 VRPN
- ⚠️ 航向角来自无人机磁罗盘（可能有磁偏角）

**使用程序**：
```bash
python control/plane_main.py   # 位置控制（UWB）
python control/yaw_main.py     # 航向角控制（无人机）
```

---

### 场景 3: VRPN 位置 + 无人机航向角

混合模式，适用于动捕系统不稳定或航向角标定不准确的情况。

```python
POSITION_SOURCE = 'vrpn'
YAW_SOURCE = 'drone'
```

**特点**：
- ✅ 位置高精度（VRPN）
- ✅ 航向角独立（无需标定动捕四元数）
- ⚠️ 数据来自不同系统，需注意同步性

---

### 场景 4: UWB 位置 + VRPN 航向角

适用于需要 VRPN 高精度航向角但位置覆盖范围有限的情况。

```python
POSITION_SOURCE = 'uwb'
YAW_SOURCE = 'vrpn'
```

**特点**：
- ✅ 大范围飞行（UWB）
- ✅ 高精度航向角（VRPN）
- ⚠️ 需要同时部署 UWB 和 VRPN
- ⚠️ 数据来自不同系统

---

## UWB 配置指南

### 1. 修改 UWB 设备地址

在 `control/config.py` 中：

```python
UWB_DEVICE = 'uwb://192.168.31.200:8888/drone1'
```

格式：`uwb://<host>:<port>/<device_name>`

### 2. 实现 UWB 客户端

项目提供了 UWB 客户端模板（`uwb.py`），你需要根据实际 UWB 系统修改通信协议。

**模板位置**：`uwb.py`

**需要修改的部分**：`_receive_loop()` 方法

#### 示例 1: UDP 接收（默认模板）

```python
# uwb.py: _receive_loop() 方法
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', self.port))

while self._running:
    data, addr = sock.recvfrom(1024)
    message = data.decode('utf-8').strip()
    # 解析格式: "drone1,1.23,4.56,0.50"
    parts = message.split(',')
    if len(parts) >= 4 and parts[0] == self.device_name:
        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        self.position = (x, y, z)
```

#### 示例 2: TCP 客户端

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((self.host, self.port))

while self._running:
    data = sock.recv(1024)
    # 解析数据...
```

#### 示例 3: HTTP 轮询

```python
import requests

while self._running:
    response = requests.get(f"http://{self.host}:{self.port}/position/{self.device_name}")
    data = response.json()
    self.position = (data['x'], data['y'], data['z'])
    time.sleep(0.1)
```

### 3. 测试 UWB 客户端

```bash
# 测试 Mock UWB（固定位置）
python -c "from uwb import MockUWBClient; c = MockUWBClient('drone1', 1.0, 2.0, 0.5); print(c.get_position()); c.stop()"

# 测试真实 UWB（需要先修改实现）
python uwb.py
```

### 4. 在控制程序中使用 UWB

**方式 1: 使用 Mock UWB（测试）**

`control/plane_main.py` 中已默认使用 Mock UWB：

```python
uwb_client = MockUWBClient('drone1', x=0.0, y=0.0, z=0.5)
```

**方式 2: 使用真实 UWB**

修改 `control/plane_main.py` 第 126 行：

```python
# 替换这一行:
uwb_client = MockUWBClient('drone1', x=0.0, y=0.0, z=0.5)

# 改为:
uwb_client = UWBClient('drone1', host='192.168.31.200', port=8888)
```

---

## 程序兼容性

| 程序 | 使用位置数据 | 使用航向角数据 | 备注 |
|------|-------------|---------------|------|
| `control/plane_main.py` | ✅ | ❌ | 只控制位置，不控制航向角 |
| `control/yaw_main.py` | ❌ | ✅ | 只控制航向角，不控制位置 |
| `control/main.py` | ✅ | ✅ | 暂时禁用（待重构） |

---

## 数据源架构

### 统一接口

所有数据源都实现了统一的接口（`control/datasource.py`）：

```python
class DataSource(ABC):
    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """获取位置 (x, y, z)"""
        pass

    def get_yaw(self) -> Optional[float]:
        """获取航向角（度）"""
        pass

    def stop(self):
        """停止数据源"""
        pass
```

### 数据源类型

1. **VRPNDataSource**: 位置 + 航向角都来自 VRPN
2. **UWBDataSource**: 位置来自 UWB，航向角来自无人机
3. **HybridDataSource**: 位置和航向角来自不同源

### 工厂函数

使用 `create_datasource()` 自动创建合适的数据源：

```python
from control.datasource import create_datasource

datasource = create_datasource(
    position_source='uwb',
    yaw_source='drone',
    vrpn_client=None,
    mqtt_client=mqtt_client,
    uwb_client=uwb_client
)

# 获取数据
position = datasource.get_position()  # (x, y, z)
yaw = datasource.get_yaw()           # 度数
```

---

## 故障排查

### 问题 1: UWB 数据不可用

```python
position = datasource.get_position()
if position is None:
    print("UWB数据不可用，检查:")
    print("1. UWB设备是否开启")
    print("2. 网络连接是否正常")
    print("3. uwb.py 中的通信协议是否正确")
```

**解决方案**：
- 检查 UWB 设备电源和网络连接
- 运行 `python uwb.py` 测试 UWB 客户端
- 检查 `_receive_loop()` 方法中的数据解析逻辑

---

### 问题 2: 航向角来自无人机时精度不准

无人机的磁罗盘可能受到磁场干扰，导致航向角不准确。

**解决方案**：
- 在无干扰环境校准磁罗盘
- 使用 VRPN 作为航向角数据源
- 调整 PID 参数以适应磁罗盘精度

---

### 问题 3: 数据源切换后程序报错

```
ValueError: 使用VRPN数据源时必须提供vrpn_client
```

**解决方案**：
- 检查 `config.py` 中的配置是否正确
- 确保对应的客户端已创建并传递给 `create_datasource()`

---

## 最佳实践

### 1. 测试流程

1. **配置阶段**：在 `config.py` 中设置数据源
2. **验证阶段**：先使用 Mock UWB 测试控制逻辑
3. **部署阶段**：切换到真实 UWB 并测试数据可用性
4. **飞行阶段**：在安全环境下测试控制性能

### 2. 性能优化

- **数据频率**：确保数据源频率 ≥ 控制频率（默认 50Hz）
- **数据延迟**：UWB 延迟通常高于 VRPN，可能需要调整 PID 参数
- **数据同步**：使用混合数据源时注意时间戳对齐

### 3. 安全建议

- ⚠️ 首次使用新数据源时，保持手动遥控器待命
- ⚠️ 在小范围内测试控制响应
- ⚠️ 设置合理的 `MAX_STICK_OUTPUT` 限幅（默认 150，半杆量）
- ⚠️ 监控控制日志，及时发现数据异常

---

## 示例配置

### 实验室环境（VRPN）

```python
# control/config.py
POSITION_SOURCE = 'vrpn'
YAW_SOURCE = 'vrpn'
VRPN_DEVICE = 'Drone001@192.168.31.100'
```

### 户外环境（UWB）

```python
# control/config.py
POSITION_SOURCE = 'uwb'
YAW_SOURCE = 'drone'
UWB_DEVICE = 'uwb://192.168.31.200:8888/drone1'

# plane_main.py (第126行)
uwb_client = UWBClient('drone1', host='192.168.31.200', port=8888)
```

### 混合环境（VRPN 位置 + 无人机航向角）

```python
# control/config.py
POSITION_SOURCE = 'vrpn'
YAW_SOURCE = 'drone'
VRPN_DEVICE = 'Drone001@192.168.31.100'
```

---

## 总结

- ✅ 支持 4 种数据源组合（VRPN/UWB × VRPN/Drone）
- ✅ 统一接口，代码无需大改
- ✅ 提供 UWB 客户端模板
- ✅ 兼容现有控制程序
- ✅ 灵活配置，适应不同场景

**下一步**：根据你的实际 UWB 系统修改 `uwb.py`，然后运行 `python control/plane_main.py` 测试！
