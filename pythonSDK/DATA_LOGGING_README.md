# PID控制数据记录与可视化

## 📊 功能概述

自动记录PID控制过程中的所有关键数据，并提供交互式可视化分析工具。

### 数据记录内容
- 时间戳
- 目标位置 (target_x, target_y)
- 实际位置 (current_x, current_y)
- 位置误差 (error_x, error_y)
- 距离目标的距离
- PID输出杆量 (roll_offset, pitch_offset)
- 绝对杆量值 (roll_absolute, pitch_absolute)
- 当前航点索引

### 可视化输出
4个子图同时展示：
1. **X位置跟踪** - 目标vs实际X位置
2. **Y位置跟踪** - 目标vs实际Y位置
3. **Roll杆量输出** - 横滚通道控制量
4. **Pitch杆量输出** - 俯仰通道控制量

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install pandas plotly kaleido
```

### 2. 运行控制程序（自动记录数据）

```bash
python control.py
```

数据将自动保存到 `data/YYYYMMDD_HHMMSS/` 目录。

### 3. 可视化数据

运行后，程序会显示数据保存位置，例如：
```
✓ 数据已保存至: data/20240315_143022
```

使用该路径进行可视化：

```bash
# 生成静态交互式图表
python plot_pid_data.py data/20240315_143022
```

这将：
- 在浏览器中打开交互式图表
- 同时保存HTML文件到数据目录 (`pid_analysis.html`)

---

## 📁 数据目录结构

```
data/
├── 20240315_143022/          # 时间戳目录
│   ├── control_data.csv      # 原始CSV数据
│   └── pid_analysis.html     # 生成的可视化HTML（运行绘图后）
├── 20240315_150530/
│   ├── control_data.csv
│   └── pid_analysis.html
└── ...
```

---

## 📈 使用示例

### 示例1: 完整流程

```bash
# 1. 启动无人机，运行控制程序
python control.py

# 输出:
# ✓ 数据记录已启用: data/20240315_143022
# ...
# （Ctrl+C退出后）
# ✓ 数据已保存至: data/20240315_143022

# 2. 分析数据
python plot_pid_data.py data/20240315_143022

# 输出:
# ✓ 已加载数据: 1523 条记录
# ✓ 图表已保存: data/20240315_143022/pid_analysis.html
# 正在浏览器中打开图表...
```

### 示例2: 禁用数据记录

如果不需要记录数据，修改 `control.py`:

```python
ENABLE_DATA_LOGGING = False  # 改为False
```

---

## 📊 图表功能

### 交互功能
- **缩放**: 鼠标滚轮或框选区域
- **平移**: 拖动图表
- **悬停**: 显示精确数值
- **图例点击**: 隐藏/显示数据线
- **统一悬停**: 4个子图同步显示同一时刻的数据

### 数据分析要点

**位置跟踪图（上排）**：
- 虚线 = 目标位置
- 实线 = 实际位置
- 观察实际位置是否能快速跟随目标
- 分析超调、振荡、稳态误差

**杆量输出图（下排）**：
- 中立线 = 1024（悬停状态）
- 蓝色区域 = PID控制输出
- 观察杆量变化的平滑性
- 分析是否频繁触碰限幅（±330）

---

## 🔧 PID调参建议

根据可视化结果调整PID参数：

| 观察现象 | 可能原因 | 调整方案 |
|---------|---------|---------|
| **实际位置追不上目标** | Kp太小 | 增大 `KP` |
| **到达目标后振荡** | Kp太大，Kd太小 | 减小 `KP`，增大 `KD` |
| **杆量输出过小（接近1024）** | 整体增益不足 | 同时增大 `KP` 和 `KD` |
| **杆量频繁触碰限幅** | 增益过大或限幅太小 | 减小 `KP`，或增大 `MAX_STICK_OUTPUT` |
| **稳态误差（始终偏离目标）** | Ki太小或为0 | 增大 `KI` |
| **抖动严重** | Kd太大 | 减小 `KD` |

---

## 💡 高级用法

### 比较多次实验

```bash
# 实验1: 原始参数
python control.py
# 数据保存至: data/20240315_143022

# 实验2: 调整参数后
# （修改 control.py 中的 KP, KI, KD）
python control.py
# 数据保存至: data/20240315_150530

# 分别查看两次实验结果
python plot_pid_data.py data/20240315_143022
python plot_pid_data.py data/20240315_150530
```

### 导出高清图片

在浏览器中打开HTML后，点击右上角相机图标即可保存PNG/SVG格式。

---

## 🐛 故障排查

### 问题1: 找不到数据文件
```
✗ 数据文件不存在: data/xxx/control_data.csv
```
**解决**: 确保路径正确，先运行 `control.py` 生成数据。

### 问题2: pandas/plotly未安装
```
ModuleNotFoundError: No module named 'pandas'
```
**解决**: `pip install pandas plotly`

### 问题3: 图表不显示
**解决**: 检查浏览器是否打开，或直接打开生成的HTML文件。

---

## 📝 CSV数据格式

可以直接用Excel/Python/MATLAB等工具读取 `control_data.csv`:

```csv
timestamp,target_x,target_y,current_x,current_y,error_x,error_y,distance,roll_offset,pitch_offset,roll_absolute,pitch_absolute,waypoint_index
1710489622.123,0.0,0.0,-0.15,0.08,0.15,-0.08,0.171,-26.4,49.8,998,1074,0
1710489622.143,0.0,0.0,-0.14,0.07,0.14,-0.07,0.157,-23.1,46.2,1001,1070,0
...
```

所有字段都是浮点数，便于后续处理和分析。
