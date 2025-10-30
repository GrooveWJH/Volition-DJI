# Control Module - 使用指南

PID控制模块，用于DJI无人机的平面定位和Yaw角控制。

## 📋 目录结构

```
control/
├── __init__.py
├── config.py           # 配置参数（PID增益、阈值等）
├── pid.py              # PID控制器基础类
├── controller.py       # 平面、Yaw控制器
├── logger.py           # 数据记录器（支持PID分量记录）
├── visualize.py        # 数据可视化工具
├── main.py             # 平面+Yaw控制主程序
├── yaw_main.py         # Yaw单独控制主程序
└── README.md           # 本文档
```

## 🚀 快速开始

### 1️⃣ 运行平面位置+Yaw角控制

**测试场景**: 无人机按航点顺序飞行，同时控制XY位置和Yaw角度

```bash
# 从pythonSDK目录运行
python control/main.py

# 或从control目录运行
cd control
python main.py
```

**数据保存位置**: `data/<timestamp>/control_data.csv`

**数据字段**:
- 位置: `target_x`, `target_y`, `current_x`, `current_y`, `distance`
- 角度: `target_yaw`, `current_yaw`, `error_yaw`
- 控制输出: `roll_offset`, `pitch_offset`, `yaw_offset`, `roll_absolute`, `pitch_absolute`, `yaw_absolute`
- **PID分量**: `x_pid_p`, `x_pid_i`, `x_pid_d` (X轴), `y_pid_p`, `y_pid_i`, `y_pid_d` (Y轴), `yaw_pid_p`, `yaw_pid_i`, `yaw_pid_d` (Yaw)
- 其他: `timestamp`, `waypoint_index`

---

### 2️⃣ 运行Yaw角单独控制

**测试场景**: 无人机只旋转到目标角度，不改变位置

```bash
# 从pythonSDK目录运行
python control/yaw_main.py

# 或从control目录运行
cd control
python yaw_main.py
```

**数据保存位置**: `data/yaw/<timestamp>/yaw_control_data.csv`

**数据字段**:
- 角度: `target_yaw`, `current_yaw`, `error_yaw`
- 控制输出: `yaw_offset`, `yaw_absolute`
- **PID分量**: `yaw_pid_p`, `yaw_pid_i`, `yaw_pid_d`
- 其他: `timestamp`, `target_index`

---

## 📊 数据可视化

### 方法1: 指定时间戳目录

```bash
# 平面+Yaw数据可视化
python control/visualize.py data/20241030_143022

# Yaw单独数据可视化
python control/visualize.py data/yaw/20241030_143500
```

### 方法2: 使用latest快捷方式

每次控制结束后，数据会自动复制到 `latest` 目录：

```bash
# 查看最新的平面+Yaw测试数据
python control/visualize.py data/latest

# 查看最新的Yaw单独测试数据
python control/visualize.py data/yaw/latest
```

### 可视化输出

#### 平面+Yaw控制 (8个子图)
1. **X轴跟踪** - 目标X vs 当前X
2. **Y轴跟踪** - 目标Y vs 当前Y
3. **Yaw角跟踪** - 目标Yaw vs 当前Yaw
4. **距离误差** - 到目标点的欧氏距离
5. **XY杆量输出** - Roll和Pitch杆量
6. **Yaw杆量输出** - Yaw杆量
7. **X轴PID分量** - P项(红)、I项(绿)、D项(蓝)
8. **Y轴PID分量** - P项(红)、I项(绿)、D项(蓝)

#### Yaw单独控制 (3个子图)
1. **Yaw角跟踪** - 目标Yaw vs 当前Yaw
2. **Yaw杆量输出** - 杆量值和1024中位线
3. **Yaw PID分量** - P项(红)、I项(绿)、D项(蓝)

### 输出文件

- **HTML文件**: `<data_dir>/plane_yaw_analysis.html` 或 `yaw_only_analysis.html`
- **自动打开浏览器**: 图表会在默认浏览器中打开
- **交互式**: 支持缩放、平移、悬停查看数值

---

## ⚙️ 配置参数

编辑 `control/config.py` 修改参数：

### 平面+Yaw控制参数

```python
# PID增益 (XY平面)
KP_XY = 150.0   # 比例增益
KI_XY = 0.0     # 积分增益
KD_XY = 200.0   # 微分增益

# PID增益 (Yaw角)
KP_YAW = 8.0
KI_YAW = 0.5
KD_YAW = 15.0

# 控制阈值
TOLERANCE_XY = 0.05          # XY到达阈值 (米)
TOLERANCE_YAW = 3.0          # Yaw到达阈值 (度)
ARRIVAL_STABLE_TIME = 1.5    # 稳定时间 (秒)

# 航点定义
WAYPOINTS = [
    (0.0, 0.0),    # 航点0
    (0.5, 0.0),    # 航点1
    (0.5, 0.5),    # 航点2
    (0.0, 0.5),    # 航点3
]

# 控制频率
CONTROL_FREQUENCY = 50  # Hz
```

### Yaw单独控制参数

```python
# PID增益 (Yaw角)
KP_YAW_ONLY = 3.0    # 比例增益
KI_YAW_ONLY = 0.0    # 积分增益（禁用以避免振荡）
KD_YAW_ONLY = 50.0   # 微分增益（强阻尼）

# 目标角度序列
TARGET_YAWS = [0, 90, 180, -90]  # 度

# 控制频率
CONTROL_FREQUENCY_YAW = 60  # Hz

# 控制阈值
TOLERANCE_YAW_ONLY = 1.0         # 到达阈值 (度)
ARRIVAL_STABLE_TIME = 2.0        # 稳定时间 (秒)
MAX_YAW_STICK_OUTPUT = 660       # 最大杆量偏移
```

---

## 🎯 PID调参指南

### 理解PID三个分量

从可视化图表的PID分量子图中观察：

- **P项 (红色)**:
  - 与误差成正比
  - 如果P项过大 → 系统过冲、震荡
  - 如果P项过小 → 响应缓慢

- **I项 (绿色)**:
  - 累积历史误差
  - 如果I项持续增长 → 可能导致超调和振荡
  - 如果存在稳态误差 → 适当增加Ki

- **D项 (蓝色)**:
  - 误差变化率（阻尼作用）
  - 如果D项剧烈波动 → Kd可能过大，对噪声敏感
  - 如果震荡严重 → 增加Kd以增强阻尼

### 调参步骤

1. **从P项开始**:
   ```python
   KP = 3.0, KI = 0.0, KD = 0.0
   ```
   观察是否能接近目标，允许一定过冲

2. **增加D项消除震荡**:
   ```python
   KP = 3.0, KI = 0.0, KD = 50.0
   ```
   观察PID分量图，D项应该抑制P项的剧烈变化

3. **谨慎启用I项**:
   ```python
   KP = 3.0, KI = 0.1, KD = 50.0
   ```
   只有在存在持续稳态误差时才启用

### 常见问题诊断

| 现象 | PID分量特征 | 解决方案 |
|------|-------------|----------|
| 严重过冲 | P项过大，D项不足 | 减小Kp，增大Kd |
| 持续震荡 | P项和I项相互作用 | 减小Kp，禁用Ki (设为0) |
| 响应缓慢 | P项、D项都很小 | 增大Kp |
| 稳态误差 | P项接近0，但仍有误差 | 启用Ki (从小值开始，如0.1) |
| 噪声敏感 | D项剧烈波动 | 减小Kd，或使用滤波 |

---

## 📁 数据目录结构

```
data/
├── 20241030_143022/              # 平面+Yaw测试1
│   ├── control_data.csv          # 原始数据
│   └── plane_yaw_analysis.html   # 可视化结果
├── 20241030_145500/              # 平面+Yaw测试2
│   ├── control_data.csv
│   └── plane_yaw_analysis.html
├── latest/                       # 最新平面+Yaw测试（自动复制）
│   ├── control_data.csv
│   └── plane_yaw_analysis.html
└── yaw/
    ├── 20241030_143500/          # Yaw测试1
    │   ├── yaw_control_data.csv
    │   └── yaw_only_analysis.html
    ├── 20241030_150000/          # Yaw测试2
    │   ├── yaw_control_data.csv
    │   └── yaw_only_analysis.html
    └── latest/                   # 最新Yaw测试（自动复制）
        ├── yaw_control_data.csv
        └── yaw_only_analysis.html
```

---

## 🔧 高级用法

### 从代码中使用控制器

```python
from control.controller import PlaneYawController, YawOnlyController
from control.logger import DataLogger

# 平面+Yaw控制器
controller = PlaneYawController(
    kp_xy=150.0, ki_xy=0.0, kd_xy=200.0,
    kp_yaw=8.0, ki_yaw=0.5, kd_yaw=15.0,
    output_limit=660
)

# 计算控制输出（返回PID分量）
roll_offset, pitch_offset, yaw_offset, pid_components = controller.compute(
    target_x=0.5, target_y=0.5, target_yaw=90.0,
    current_x=0.3, current_y=0.2, current_yaw=45.0,
    current_time=time.time()
)

# PID分量结构
# pid_components = {
#     'x': (p_term, i_term, d_term),
#     'y': (p_term, i_term, d_term),
#     'yaw': (p_term, i_term, d_term)
# }

# 数据记录器（支持PID分量）
logger = DataLogger(enabled=True, field_set='plane_yaw')
logger.log(
    timestamp=current_time,
    target_x=0.5, current_x=0.3, error_x=0.2,
    # ... 其他字段 ...
    x_pid_p=pid_components['x'][0],
    x_pid_i=pid_components['x'][1],
    x_pid_d=pid_components['x'][2],
    # ... 其他PID分量 ...
)
logger.close()  # 自动创建latest副本
```

### 自定义字段记录

```python
# 定义自定义字段
custom_fields = [
    'timestamp', 'my_data1', 'my_data2', 'my_pid_p', 'my_pid_i', 'my_pid_d'
]

logger = DataLogger(
    enabled=True,
    field_set=custom_fields,  # 传入自定义字段列表
    csv_name='my_data.csv',
    subdir='my_experiments'
)

logger.log(
    timestamp=time.time(),
    my_data1=123.456,
    my_data2=789.012,
    my_pid_p=10.0,
    my_pid_i=0.5,
    my_pid_d=2.0
)
```

---

## 📝 常见问题

### Q1: 为什么有两个测试程序？

- **`main.py`**: 测试XY平面移动 + Yaw角度控制（复杂场景）
- **`yaw_main.py`**: 只测试Yaw角度控制（简化调参）

建议先用 `yaw_main.py` 调好Yaw的PID参数，再用 `main.py` 测试完整功能。

### Q2: latest目录有什么用？

每次测试结束后，数据自动复制到 `latest` 目录，方便快速查看最新结果：

```bash
# 不用记住时间戳，直接查看最新数据
python control/visualize.py data/latest
python control/visualize.py data/yaw/latest
```

### Q3: 如何关闭数据记录？

编辑 `control/config.py`:

```python
ENABLE_DATA_LOGGING = False  # 改为False
```

### Q4: PID分量图表看不到线？

可能是PID参数为0或数据未记录。检查：

1. 确保使用的是新版本代码（支持PID分量记录）
2. 查看CSV文件是否包含 `*_pid_p`, `*_pid_i`, `*_pid_d` 列
3. 检查PID参数不全为0

### Q5: 如何修改控制频率？

编辑 `control/config.py`:

```python
CONTROL_FREQUENCY = 50      # 平面+Yaw控制频率 (Hz)
CONTROL_FREQUENCY_YAW = 60  # Yaw单独控制频率 (Hz)
```

注意：频率过高可能导致系统负载增加，频率过低会降低控制精度。

---

## 🎓 技术说明

### 坐标系统

- **世界坐标系**: VRPN动捕系统提供的全局坐标
- **机体坐标系**: 无人机本体坐标系，随Yaw角旋转
- **Yaw角约定**: 逆时针旋转为正（右手坐标系，Z轴向上）

### 控制映射

```
世界坐标误差 → 机体坐标误差 → 杆量控制

X轴 (前方向) → Pitch杆量 (正值前进)
Y轴 (左方向) → Roll杆量 (负值向左)
Yaw角 (逆时针) → Yaw杆量 (负值逆时针)
```

### 杆量范围

- **中立位置**: 1024
- **最大偏移**: ±660
- **有效范围**: 364 ~ 1684

---

## 📚 参考资料

- **PID控制原理**: `control/pid.py` - 带积分限幅的标准PID实现
- **坐标变换**: `control/controller.py:100-133` - 世界系到机体系的旋转矩阵
- **角度归一化**: `control/controller.py:25-39` - 处理±180°边界
- **数据记录**: `control/logger.py` - 支持自定义字段的参数化记录器
- **可视化**: `control/visualize.py` - 自动检测数据类型的通用绘图工具

---

**最后更新**: 2024-10-30
**版本**: 2.0 (支持PID分量可视化 + latest快捷方式)
