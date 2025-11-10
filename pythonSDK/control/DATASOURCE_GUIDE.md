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

### 1. 准备工作

确保：
- ✅ UWB 设备已连接到串口 `/dev/ttyACM0`
- ✅ 串口权限已配置（参考 `uwb/SERIAL_PERMISSION_FIX.md`）
- ✅ 已安装依赖: `pip install pyserial numpy`

### 2. 配置 control/config.py

```python
# 使用 UWB 定位 + 无人机航向角
POSITION_SOURCE = 'uwb'
YAW_SOURCE = 'drone'

# UWB 目标节点 ID (TAG 节点通常是 2)
UWB_DEVICE = '2'
```

**UWB_DEVICE 配置说明**：
- 格式：字符串或整数的节点 ID
- 示例：`'2'`, `2`, `'3'`
- 对应 UWB TAG 节点的 ID（可通过 `python uwb/getdata.py` 查看）

### 3. 测试 UWB 连接

**步骤 1：测试串口读取**

```bash
# 测试原始数据读取（30Hz打印）
python uwb/getdata.py

# 测试带平滑的数据读取（30Hz打印，实时显示原始和平滑数据）
python uwb/getdata_smoothed.py
```

**预期输出**：
```
[10:30:15] Frame #1 (TAG) | Anchors: 4 | Tags: 1 | Voltage: 3.87V
  [TAG    ] ID= 2 | XYZ = ( 1.234,  0.567,  0.050)m | Dist = 2.45m
```

**步骤 2：测试 uwb_client.py**

```bash
# 测试 uwb_client 模块（后台线程读取 + 平滑）
python uwb_client.py
```

**预期输出**：
```
[UWB] Client started: /dev/ttyACM0 @ 1500000
[UWB] Target node ID: 2
[UWB] Smoothing: enabled

Reading UWB position data (Ctrl+C to stop)...

[0123] Position: ( 1.2340,  0.5670,  0.0500)m
```

### 4. 在控制程序中使用 UWB

```bash
# 确保 config.py 配置正确
python control/plane_main.py
```

**程序会自动**：
1. 从串口 `/dev/ttyACM0` 读取 UWB 数据
2. 过滤目标节点 ID (例如 2)
3. 应用移动平均滤波（X轴5点，Y轴3点，Z轴3点）
4. 剔除异常值（3σ原则）
5. 提供 `datasource.get_position()` 接口

**控制程序输出示例**：
```
━━━ 步骤 1/3: 连接位置数据源 (UWB) ━━━
[UWB] Client started: /dev/ttyACM0 @ 1500000
[UWB] Target node ID: 2
[UWB] Smoothing: enabled
✓ UWB客户端已启动: 节点 ID=2, 平滑=ON
提示: UWB 从串口 /dev/ttyACM0 读取数据

━━━ 步骤 2/3: 连接MQTT ━━━
✓ MQTT已连接: 192.168.31.73:1883

━━━ 步骤 3/3: 启动心跳 ━━━
✓ 心跳已启动 (5.0Hz)

━━━ 创建数据源接口 ━━━
✓ 数据源已创建: 位置=UWB
```

### 5. UWB 技术细节

#### 数据源

- **串口**: `/dev/ttyACM0`
- **波特率**: 1500000
- **协议**: 896 字节帧，包含 30 个节点数据
- **更新频率**: ~100Hz（原始数据）

#### 平滑算法

基于 `uwb/statistics.py` 的实测统计数据：

| 轴 | 标准差 σ | 滤波窗口 | 异常值阈值 (3σ) |
|----|---------|---------|-----------------|
| X  | 28.6mm  | 5 点    | 85.8mm          |
| Y  | 12.9mm  | 3 点    | 38.7mm          |
| Z  | 未测量  | 3 点    | 50.0mm          |

**平滑流程**：
1. 异常值检测（与历史均值比较）
2. 异常值替换（使用上一个有效值）
3. 移动平均滤波（滑动窗口）

#### 节点角色

| 角色    | ID 范围 | 说明 |
|---------|---------|------|
| ANCHOR  | 固定    | 基站，提供参考位置 |
| TAG     | 2, 3, …  | 移动标签，需要定位的目标 |
| CONSOLE | 1       | 控制台 |

通常**无人机使用 TAG 节点 (ID=2)**。

### 6. 故障排查

#### 问题 1: 串口权限错误

```
[UWB] ERROR: Failed to open serial port: [Errno 13] Permission denied: '/dev/ttyACM0'
```

**解决方案**：
```bash
# 方案 1: 临时添加权限
sudo chmod 666 /dev/ttyACM0

# 方案 2: 永久添加用户到 dialout 组（推荐）
sudo usermod -aG dialout $USER
# 注销并重新登录

# 方案 3: 使用 udev 规则（参考 uwb/SERIAL_PERMISSION_FIX.md）
```

#### 问题 2: 没有数据输出

```
[0000] Waiting for UWB data...
```

**检查清单**：
- [ ] UWB 设备是否已连接到 `/dev/ttyACM0`
  ```bash
  ls -l /dev/ttyACM*
  ```
- [ ] UWB 设备是否已开机
- [ ] 节点 ID 是否正确
  ```bash
  # 运行 getdata.py 查看所有节点 ID
  python uwb/getdata.py
  ```
- [ ] 串口是否被其他程序占用
  ```bash
  lsof /dev/ttyACM0
  ```

#### 问题 3: 位置数据跳变

如果位置数据不稳定、频繁跳变：

**原因**：
- UWB 信号遮挡
- 多径效应
- 基站位置变化

**解决方案**：
1. 调整平滑参数（`uwb_client.py` 中的滤波窗口）
2. 检查 UWB 基站布局
3. 参考 `uwb/滤波器参数调节指南.md`

#### 问题 4: 航向角不准确

因为 UWB 只提供位置，航向角来自无人机磁罗盘。

**现象**：
- 位置控制正常，航向角控制不准确
- 航向角漂移

**解决方案**：
- 校准无人机磁罗盘
- 使用 VRPN 作为航向角数据源（如果可用）
  ```python
  POSITION_SOURCE = 'uwb'
  YAW_SOURCE = 'vrpn'  # 使用 VRPN 航向角
  ```
- 调整 Yaw PID 参数以适应磁罗盘精度

### 7. 高级配置

#### 修改目标节点 ID

如果需要跟踪不同的 TAG 节点：

```python
# control/config.py
UWB_DEVICE = '3'  # 跟踪 ID=3 的节点
```

#### 禁用平滑（获取原始数据）

编辑 `control/plane_main.py`:

```python
# 第 139 行附近
uwb_client = UWBClient(target_node_id=node_id, use_smoothing=False)  # 禁用平滑
```

#### 调整平滑参数

编辑 `uwb_client.py`:

```python
# 第 37-42 行
FILTER_WINDOW_X = 7      # 增大窗口 = 更平滑但延迟更大
FILTER_WINDOW_Y = 5
OUTLIER_THRESHOLD_X = 0.120  # 增大阈值 = 容忍更大的跳变
```

### 8. 性能优化

#### 控制延迟

| 组件 | 延迟 | 说明 |
|------|------|------|
| UWB 数据更新 | ~10ms | 100Hz 更新率 |
| 串口读取 | ~5ms | 后台线程 |
| 平滑滤波 | 20-50ms | 取决于窗口大小 |
| 控制循环 | 20ms | 50Hz |
| **总延迟** | **~55-85ms** | 可接受 |

如果需要更低延迟：
- 减小平滑窗口 (`FILTER_WINDOW_X/Y`)
- 禁用平滑 (`use_smoothing=False`)
- 增加控制频率 (`CONTROL_FREQUENCY = 100`)

#### 数据质量

| 指标 | UWB (带平滑) | VRPN |
|------|--------------|------|
| 更新率 | ~100Hz | ~120Hz |
| 位置精度 | 10-30mm | 1-5mm |
| 延迟 | ~55-85ms | ~10-20ms |
| 覆盖范围 | 大 (100m+) | 小 (10m) |
| 室外可用 | ✅ | ❌ |

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
