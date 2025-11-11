# MPC控制系统 - 详细操作指南

## ⚠️ 重要提示

**本指南专为2m半径动捕场地设计，所有参数和操作流程已针对受限空间优化**

### 安全守则
1. **始终手持遥控器**，随时准备切换到手动模式
2. **实验前确认安全人员到位**
3. **保持动捕系统稳定运行**
4. **确保急停按钮可及**
5. **首次运行务必有经验人员在场**

---

## 目录

1. [实验前准备](#1-实验前准备)
2. [环境配置与参数调整](#2-环境配置与参数调整)
3. [系统启动流程](#3-系统启动流程)
4. [系统辨识阶段](#4-系统辨识阶段)
5. [MPC控制阶段](#5-mpc控制阶段)
6. [异常处理预案](#6-异常处理预案)
7. [实验后处理](#7-实验后处理)
8. [故障排查手册](#8-故障排查手册)

---

## 1. 实验前准备

### 1.1 硬件检查清单

| 项目 | 检查内容 | 预期状态 | 异常处理 |
|------|---------|---------|---------|
| **无人机** | 电池电量 | ≥80% | 更换电池，务必使用满电电池 |
| | 螺旋桨 | 无损伤、紧固 | 更换损坏螺旋桨 |
| | IMU校准 | 最近7天内 | 重新校准IMU |
| | 飞控固件 | 最新版本 | 升级固件 |
| **动捕系统** | 相机连接 | 全部在线 | 重启动捕服务器 |
| | 标定质量 | <0.5mm误差 | 重新标定场地 |
| | 标记点识别 | 稳定识别无人机 | 调整标记点位置/亮度 |
| | 坐标系方向 | X-前, Y-左, Z-上 | 检查坐标系设置 |
| **通信系统** | MQTT broker | 192.168.31.73:1883可达 | 检查网络连接 |
| | 网络延迟 | <50ms | 检查网络拓扑，移除干扰源 |
| | VRPN服务器 | 192.168.31.100:3883可达 | 重启VRPN服务 |
| **地面站电脑** | Python环境 | 3.8+ | 重新安装Python |
| | 依赖包 | numpy, scipy, rich等 | `pip install -r requirements.txt` |
| | 磁盘空间 | >1GB可用 | 清理日志文件 |

### 1.2 软件准备

```bash
# 1. 激活Python虚拟环境（如有）
source venv/bin/activate

# 2. 验证依赖包
python -c "import numpy, scipy, rich, zmq; print('All dependencies OK')"

# 3. 检查代码版本
git log -1 --oneline

# 4. 测试VRPN连接
python vrpn_test.py
# 预期输出：应看到无人机位置数据流（刷新频率100Hz）
```

**预期输出示例：**
```
VRPN Connected: Drone001@192.168.31.100
Position: (0.12, -0.05, 0.98) m
Orientation: (0.0, 1.5, 180.2) deg
Update rate: 98.3 Hz
```

**异常情况处理：**
- 若无数据：检查VRPN服务器运行状态，重启服务
- 若更新率<50Hz：检查网络负载，关闭无关应用
- 若位置跳变：检查标记点遮挡，调整无人机位置

### 1.3 场地准备

```
┌────────────────────────────────┐
│    动捕场地布局 (2m半径)       │
│                                │
│           ↑ Y (左)             │
│           │                    │
│           │                    │
│       ●───┼───●  1m           │
│           │                    │
│    ───────○──────→ X (前)     │
│           │(0,0)               │
│           │                    │
│       ●───┼───●  1m           │
│           │                    │
│                                │
│  ○ = 起飞点 (中心)             │
│  ● = 安全边界标记               │
└────────────────────────────────┘
```

**场地检查：**
1. 清空场地内所有障碍物（2m半径内）
2. 在边界位置放置视觉标记锥（便于判断无人机位置）
3. 确认光线充足但无直射阳光（影响动捕）
4. 设置安全警戒线（3m半径，禁止无关人员进入）

### 1.4 配置文件准备

**针对2m半径场地的关键参数调整：**

编辑 `control/config.py`:

```python
# ========== 安全限制配置（2m半径场地）==========

# 航点配置 - 使用保守的航点
WAYPOINTS = [
    (0.0, 0.0),   # 中心点（起飞位置）
    (0.5, 0.0),   # 前方50cm
    (0.0, 0.5),   # 左侧50cm
    (-0.5, 0.0),  # 后方50cm
]

# ⚠️ 禁用随机航点（避免越界）
PLANE_USE_RANDOM_WAYPOINTS = False
PLANE_AUTO_NEXT_WAYPOINT = False  # 手动确认每个航点

# 控制参数 - 降低增益以减少过冲
KP_XY = 300.0   # 降低至300（原400）
KI_XY = 15.0    # 降低至15（原20）
KD_XY = 12.0    # 提高至12（原10），增强阻尼

# 杆量限幅 - 进一步限制以防止激进动作
MAX_STICK_OUTPUT = 100  # 降低至100（原150）

# 阈值设置
TOLERANCE_XY = 0.08  # 收紧至8cm（原10cm）
PLANE_ARRIVAL_STABLE_TIME = 1.5  # 延长至1.5秒（原1.0秒）
```

**系统辨识参数调整（针对受限空间）：**

编辑 `control_mpc/system_id.py` 的激励幅值（第54行）:

```python
# 系统辨识 - 降低激励幅值以防越界
self.excitation_amplitude = 30.0  # 降低至30（原50）
```

编辑 `control_mpc/mpc_main.py` 的辨识时间（第73行）:

```python
# 缩短辨识时间以减少移动距离
self.identification_duration = 10.0  # 保持10秒（可考虑降至8秒）
```

---

## 2. 环境配置与参数调整

### 2.1 确认配置文件

**必须检查的配置项：**

```bash
# 打开配置文件
code control/config.py  # 或使用 vim/nano

# 检查以下关键参数：
# 1. GATEWAY_SN - 无人机序列号
# 2. VRPN_DEVICE - 动捕设备名称
# 3. MQTT_CONFIG['host'] - MQTT服务器地址
# 4. WAYPOINTS - 目标航点（确保在安全范围内）
# 5. MAX_STICK_OUTPUT - 杆量限幅
# 6. TOLERANCE_XY - 到达阈值
```

### 2.2 参数验证脚本

创建并运行参数验证脚本：

```bash
# 验证航点是否在安全范围内
python -c "
import sys
sys.path.insert(0, '.')
from control.config import WAYPOINTS

safe_radius = 1.5  # 预留0.5m安全余量

for i, (x, y) in enumerate(WAYPOINTS):
    dist = (x**2 + y**2)**0.5
    status = '✓' if dist <= safe_radius else '✗ 危险！'
    print(f'航点{i}: ({x:+.2f}, {y:+.2f}) 距离={dist:.2f}m {status}')

print(f'\n安全半径: {safe_radius}m (场地限制: 2.0m)')
"
```

**预期输出：**
```
航点0: (+0.00, +0.00) 距离=0.00m ✓
航点1: (+0.50, +0.00) 距离=0.50m ✓
航点2: (+0.00, +0.50) 距离=0.50m ✓
航点3: (-0.50, +0.00) 距离=0.50m ✓

安全半径: 1.5m (场地限制: 2.0m)
```

**如果出现 ✗ 危险！标记：**
1. **立即停止实验准备**
2. 编辑 `control/config.py`，调整 `WAYPOINTS` 使所有点在1.5m以内
3. 重新运行验证脚本直至全部通过

---

## 3. 系统启动流程

### 3.1 无人机准备（手动操作）

**步骤1：开机与连接**

```bash
# 操作时间：约2分钟
# 操作人员：飞手

1. 无人机放置在场地中心（0, 0）位置
2. 朝向正北（X轴正方向）
3. 开启遥控器（等待连接音）
4. 开启无人机（等待自检完成）
5. 等待GPS信号（如室内可跳过）
6. 切换至姿态模式（避免GPS漂移）
```

**预期状态：**
- 遥控器显示：电池满、信号强、姿态模式
- 无人机LED：绿灯常亮（或室内闪烁）
- DJI Pilot App（如使用）：无错误提示

**异常处理：**
- 红灯闪烁：检查IMU校准、指南针干扰
- 遥控器失联：检查电池、重新对频
- 姿态模式不可用：检查飞控固件版本

**步骤2：起飞到悬停**

```bash
# 操作时间：约30秒
# 高度：1.0米（重要！MPC依赖恒定高度）

1. 遥控器切换到手动模式
2. 缓慢推油门，起飞
3. 悬停在1.0米高度（±5cm）
4. 微调位置，使无人机位于场地中心
5. 保持悬停10秒，检查稳定性
```

**预期状态：**
- 动捕系统显示：(0.0±0.05, 0.0±0.05, 1.0±0.05)
- 无人机姿态：水平，无漂移
- 遥控器杆位：中位（throttle除外）

**异常处理：**
- 高度不稳：检查气压计，切换到光流模式（如可用）
- 位置漂移：检查风扇/空调，关闭干扰源
- 姿态倾斜：降落，重新IMU校准

### 3.2 地面站启动（终端操作）

**启动MPC控制程序：**

```bash
# 打开终端，进入项目目录
cd /path/to/Volition-DJI/pythonSDK

# 运行MPC主程序
python control_mpc/mpc_main.py
```

**预期输出（启动阶段）：**

```
═══════════════════════════════════════════════════
  MPC平面控制器 - 解决200ms延迟的预测控制

  核心优势:
  • 预测式控制 (vs PID反应式)
  • 自动模型学习 (vs 手动调参)
  • 延迟感知补偿 (vs 盲目响应)

  目标航点: (0.50, 0.00)m
  控制频率: 50Hz
═══════════════════════════════════════════════════

━━━ 步骤 1/3: 连接VRPN动捕系统 ━━━
✓ VRPN客户端已连接: Drone001@192.168.31.100

━━━ 步骤 2/3: 连接MQTT ━━━
✓ MQTT已连接: 192.168.31.73:1883

━━━ 步骤 3/3: 启动心跳 ━━━
✓ 心跳已启动 (5.0Hz)
✓ 数据记录已启用: data/mpc/20250103_143022/

等待无人机位置稳定...
✓ 位置已稳定，准备开始控制
```

**每个步骤的详细说明：**

#### 步骤1: VRPN连接
- **作用**：连接动捕系统，获取无人机位置反馈
- **耗时**：1-2秒
- **成功标志**：显示 "✓ VRPN客户端已连接"
- **失败处理**：
  ```
  ✗ VRPN连接失败: Connection refused

  解决方案：
  1. 检查VRPN服务器是否运行: ps aux | grep vrpn
  2. 检查网络连接: ping 192.168.31.100
  3. 检查防火墙: sudo ufw status
  4. 重启VRPN服务: sudo systemctl restart vrpn
  5. 如仍失败，检查 control/config.py 中的 VRPN_DEVICE 配置
  ```

#### 步骤2: MQTT连接
- **作用**：连接无人机通信通道，发送控制指令
- **耗时**：1-2秒
- **成功标志**：显示 "✓ MQTT已连接"
- **失败处理**：
  ```
  ✗ MQTT连接失败: [Errno 111] Connection refused

  解决方案：
  1. 检查MQTT broker状态: mosquitto -v
  2. 检查端口占用: netstat -tuln | grep 1883
  3. 检查配置: cat control/config.py | grep MQTT_CONFIG
  4. 测试连接: mosquitto_pub -h 192.168.31.73 -t test -m "hello"
  5. 如仍失败，尝试本地broker: 修改host为'localhost'
  ```

#### 步骤3: 心跳启动
- **作用**：保持与无人机的连接活跃
- **耗时**：<1秒
- **成功标志**：显示 "✓ 心跳已启动 (5.0Hz)"
- **说明**：心跳在后台运行，无需干预

#### 位置稳定检测
- **作用**：确认无人机悬停稳定，准备开始实验
- **检测逻辑**：连续50次采样（1秒），位置变化<1cm
- **耗时**：1-5秒（取决于无人机稳定性）
- **超时处理**：如果30秒内未稳定，程序会提示手动检查

**异常情况总览：**

| 步骤 | 可能错误 | 原因 | 解决方案 |
|------|---------|------|---------|
| VRPN | Connection refused | 服务未运行 | 重启VRPN服务 |
| VRPN | Timeout | 网络问题 | 检查网线/交换机 |
| VRPN | Device not found | 设备名错误 | 核对config.py配置 |
| MQTT | Connection refused | Broker未运行 | 启动mosquitto |
| MQTT | Authentication failed | 密码错误 | 检查用户名密码 |
| MQTT | Network unreachable | 网络断开 | 检查网络设置 |
| 位置稳定 | 超时 | 无人机漂移 | 降落重新起飞 |

---

## 4. 系统辨识阶段

### 4.1 阶段概述

**目的：** 通过发送随机激励信号，让程序自动学习无人机的动态特性（A、B矩阵）

**原理：**
```
发送控制指令 u(t) → 观察位置响应 x(t) → 拟合模型 x(t+1) = A·x(t) + B·u(t-delay)
```

**时间：** 10秒（可在config中调整）

**运动范围：** 预计±0.5m（取决于激励幅值）

### 4.2 开始系统辨识

**程序提示：**

```
═══ 阶段1: 系统辨识 (持续 10.0s) ═══
⚠ 无人机将执行激励动作以学习动态特性，请确保安全空间充足

按 Enter 开始系统辨识...
```

**操作前确认清单：**
- [ ] 无人机悬停在中心位置 (0, 0, 1m)
- [ ] 遥控器手持，拇指放在模式切换开关上
- [ ] 场地内无人员进入
- [ ] 动捕系统稳定运行（检查动捕软件）
- [ ] 安全员就位

**按下Enter后，程序输出：**

```
执行系统辨识... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
系统辨识进行中... 15.3% (76次迭代)
```

### 4.3 辨识过程监控

**预期现象：**

1. **无人机行为**：
   - 前后、左右小幅度运动
   - 运动幅度约20-40cm
   - 运动呈随机方向，频率约1-2Hz
   - 高度保持不变（仅平面运动）

2. **终端输出**：
   ```
   系统辨识进行中... 0.0% (0次迭代)
   系统辨识进行中... 10.2% (51次迭代)
   系统辨识进行中... 25.5% (127次迭代)
   系统辨识进行中... 50.8% (254次迭代)
   系统辨识进行中... 75.3% (376次迭代)
   系统辨识进行中... 99.8% (499次迭代)
   ```

3. **动捕软件画面**：
   - 无人机标记点稳定识别
   - 轨迹显示不规则但连续的曲线
   - 位置坐标在 [-0.6, +0.6] 范围内波动

**异常情况处理：**

| 现象 | 可能原因 | 立即操作 | 后续处理 |
|------|---------|---------|---------|
| 无人机向一侧持续漂移 | 气流/IMU偏差 | 遥控器切回手动，归中 | 调整场地环境，重新校准IMU |
| 运动幅度过大（>1m） | 激励幅值过大 | 遥控器切回手动，归中 | 降低 `excitation_amplitude`（当前30→20） |
| 无人机几乎不动 | 激励幅值过小 | 等待完成（可能模型质量低） | 提高 `excitation_amplitude`（30→40） |
| 突然剧烈震荡 | 程序bug/通信丢包 | **紧急切换手动，降落** | 检查日志，联系开发人员 |
| 位置数据丢失 | 动捕遮挡 | 遥控器切回手动，调整姿态 | 检查标记点，调整相机角度 |

### 4.4 辨识结果分析

**10秒后，程序停止激励：**

```
停止激励信号，悬停稳定...
分析数据，识别系统模型...
```

**成功情况：**

```
✓ 系统辨识成功！模型质量: R² = 0.847

[dim]A矩阵:
[[1.000  0.000  0.019 -0.001]
 [0.000  1.000  0.001  0.020]
 [0.012 -0.003  0.921  0.008]
 [0.005  0.015 -0.012  0.918]]

B矩阵:
[[ 0.000  0.000]
 [ 0.000  0.000]
 [ 0.089 -0.012]
 [ 0.015 -0.095]]
[/dim]

✓ 模型已保存到: control_mpc/identified_model.json
```

**结果判读：**

- **R² (决定系数)**：模型拟合质量
  - `R² > 0.8`：优秀，可以放心使用
  - `0.6 < R² < 0.8`：良好，可以使用但效果可能略差
  - `R² < 0.6`：不佳，建议重新辨识

- **A矩阵**：状态转移矩阵
  - 对角线接近1：系统稳定
  - 主对角线元素<0.9：阻尼较大（安全）
  - 主对角线元素>1.0：系统不稳定（**危险，不要继续**）

- **B矩阵**：控制矩阵
  - B[2,0]：pitch对vx的影响（应为正数）
  - B[3,1]：roll对vy的影响（应为负数，坐标映射）
  - 数值在0.05-0.15范围内：正常

**失败情况：**

```
⚠ 模型质量不佳: R² = 0.432 < 0.6

原因分析：
- 数据样本不足（<100个有效点）
- 激励信号幅值过小，信噪比低
- 位置反馈质量差（动捕丢帧）
```

**失败后的操作：**

1. **方案A：重新辨识（推荐）**
   ```bash
   # 程序会提示
   系统辨识失败，无法进行MPC控制

   # 操作：Ctrl+C退出程序，重新运行
   # 调整参数（可选）：
   # - 提高激励幅值: excitation_amplitude = 40（原30）
   # - 延长辨识时间: identification_duration = 15（原10）
   ```

2. **方案B：加载已保存的模型（仅限相同无人机+相同场地）**
   ```python
   # 编辑 control_mpc/mpc_main.py，在 __init__ 中添加：
   model_path = "control_mpc/identified_model.json"
   if os.path.exists(model_path):
       self.sysid.load_model(model_path)
       A, B = self.sysid.get_current_model()
       self.mpc.set_model(A, B)
       self.delay_comp.set_system_model(A, B)
       # 跳过辨识阶段...
   ```

3. **方案C：使用手动调参的PID控制（放弃MPC）**
   ```bash
   # 运行传统PID控制器
   python control/main.py
   ```

### 4.5 辨识阶段常见问题

**Q1: 辨识过程中无人机突然向一侧飞去**

A: 这是激励信号的正常现象，但如果超过1m：
1. 立即切换手动模式，拉回中心
2. 程序会继续运行，等待完成
3. 如果结果R²<0.6，需重新辨识（并降低激励幅值）

**Q2: 辨识成功但A矩阵对角线元素>1.0**

A: **严重问题，系统不稳定，禁止继续实验！**
- 可能原因：数据质量差、模型拟合错误
- 解决方法：
  1. 检查动捕系统延迟（应<20ms）
  2. 检查网络丢包率（应<1%）
  3. 重新辨识2-3次
  4. 如持续出现，联系技术支持

**Q3: 辨识后无人机位置偏离中心**

A: 正常现象，MPC控制阶段会自动归位。如果偏离>1m：
1. 手动飞回中心位置（0, 0）
2. 等待悬停稳定
3. 继续程序（程序会检测稳定后自动开始MPC控制）

---

## 5. MPC控制阶段

### 5.1 阶段概述

**目的：** 使用学习的模型，让无人机自动飞往目标航点

**控制策略：**
- 预测时域：10步（200ms）
- 控制频率：50Hz（每20ms计算一次）
- 延迟补偿：自动估计真实状态
- 到达判定：在阈值内稳定1.5秒

### 5.2 控制开始

**程序提示：**

```
═══ 阶段2: MPC预测控制 ═══
目标航点: (0.50, 0.00)m
```

**说明：**
- 第一个目标航点从 `WAYPOINTS[0]` 读取
- 本例中为 (0.5, 0.0)，即前方50cm

### 5.3 控制过程监控

**终端输出（每0.2秒刷新一次）：**

```
#0010 | 目标(+0.50,+0.00) | 测量(+0.12,+0.03) | 估计(+0.15,+0.02) | 距 38.4cm | MPC:suc | 延迟补偿:10步 | 控制[+  45,+   8]
#0020 | 目标(+0.50,+0.00) | 测量(+0.25,+0.02) | 估计(+0.28,+0.01) | 距 22.1cm | MPC:suc | 延迟补偿:10步 | 控制[+  32,+   2]
#0030 | 目标(+0.50,+0.00) | 测量(+0.38,+0.01) | 估计(+0.41,+0.00) | 距  9.2cm | MPC:suc | 延迟补偿:10步 | 控制[+  15,+   0]
⏱ 进入阈值范围 (距离:7.85cm)...
#0040 | 目标(+0.50,+0.00) | 测量(+0.47,-0.01) | 估计(+0.49,+0.00) | 距  1.4cm | MPC:suc | 延迟补偿:10步 | 控制[+   2,+   1]
#0050 | 目标(+0.50,+0.00) | 测量(+0.49,+0.00) | 估计(+0.50,+0.00) | 距  0.5cm | MPC:suc | 延迟补偿:10步 | 控制[+   0,+   0]
✓ 已到达目标！
```

**每一列的含义：**

| 列 | 含义 | 正常范围 | 异常提示 |
|----|------|---------|---------|
| #0010 | 循环计数器（50Hz） | 递增 | 如卡住，说明程序hang |
| 目标(x,y) | 目标航点坐标 | 与WAYPOINTS一致 | - |
| 测量(x,y) | 动捕测量的位置 | 连续变化 | 如跳变，检查动捕 |
| 估计(x,y) | 延迟补偿后的估计位置 | 略超前测量值 | 如差异>20cm，异常 |
| 距XXcm | 与目标的距离 | 递减至<8cm | 如不减小，检查控制 |
| MPC:suc | MPC求解状态 | success | 如fail，检查模型 |
| 延迟补偿:10步 | 预测步数 | 10步（200ms） | - |
| 控制[+45,+8] | 杆量指令 [pitch, roll] | [-100, +100] | 如超限，检查MAX_STICK_OUTPUT |

### 5.4 到达判定

**触发条件：**
1. 距离目标 < `TOLERANCE_XY` (0.08m)
2. 持续时间 > `PLANE_ARRIVAL_STABLE_TIME` (1.5秒)

**判定过程：**
```
⏱ 进入阈值范围 (距离:7.85cm)...  ← 首次进入阈值
[等待1.5秒，期间持续检查]
✓ 已到达目标！                    ← 判定成功
```

**中途离开阈值：**
```
⏱ 进入阈值范围 (距离:7.85cm)...
✗ 偏离目标 (距离:12.3cm)         ← 重新开始计时
⏱ 进入阈值范围 (距离:6.45cm)...
✓ 已到达目标！
```

### 5.5 正常控制轨迹示例

**从(0,0)到(0.5,0)的典型轨迹：**

```
时间 | 位置(x, y) | 速度(vx, vy) | 距离 | 控制(pitch, roll)
-----|-----------|--------------|------|------------------
0.0s | (0.00, 0.00) | (0.00, 0.00) | 50cm | (+45, +0)  ← 加速
0.5s | (0.12, 0.01) | (0.25, 0.01) | 38cm | (+40, +0)
1.0s | (0.25, 0.01) | (0.26, 0.00) | 25cm | (+32, +0)
1.5s | (0.38, 0.00) | (0.24, 0.00) | 12cm | (+18, +0)  ← 减速
2.0s | (0.47, 0.00) | (0.10, 0.00) |  3cm | (+5, +0)
2.5s | (0.50, 0.00) | (0.02, 0.00) |  0cm | (+0, +0)   ← 到达
3.0s | (0.50, 0.00) | (0.00, 0.00) |  0cm | (+0, +0)   ← 稳定悬停
```

**关键观察点：**
1. **加速段（0-1s）**：pitch保持正向，速度递增
2. **减速段（1-2s）**：pitch减小，速度递减
3. **精确调整（2-2.5s）**：小幅pitch，微调位置
4. **稳定悬停（2.5-3.5s）**：控制量趋零，位置不变

### 5.6 异常控制行为处理

#### 情况1: 振荡（往复运动）

**现象：**
```
#0100 | 距  5cm | 控制[+10, +0]
#0110 | 距 12cm | 控制[-15, +0]  ← 反向
#0120 | 距  8cm | 控制[+12, +0]  ← 再反向
#0130 | 距 11cm | 控制[-14, +0]  ← 持续振荡
```

**原因分析：**
- 控制增益过大（KP_XY过高）
- 延迟估计不准确
- 模型质量不佳（R²<0.7）

**立即操作：**
1. 按 `Ctrl+C` 停止程序
2. 无人机会自动悬停（程序发送归中杆量）
3. 遥控器接管，手动降落

**后续调整：**
```python
# 编辑 control/config.py
KP_XY = 250.0  # 降低增益（原300）
MAX_STICK_OUTPUT = 80  # 进一步限幅（原100）

# 重新运行MPC程序（会加载已保存的模型，跳过辨识）
python control_mpc/mpc_main.py
```

#### 情况2: 超调（冲过目标）

**现象：**
```
#0080 | 测量(+0.48,+0.00) | 距  2cm | 控制[+5, +0]
#0090 | 测量(+0.55,+0.00) | 距  5cm | 控制[-8, +0]  ← 超调
#0100 | 测量(+0.60,+0.00) | 距 10cm | 控制[-12, +0] ← 继续超调
```

**原因分析：**
- 减速不及时（阻尼不足）
- 延迟补偿失效
- 模型B矩阵元素偏大

**立即操作：**
- 等待MPC自动纠正（通常1-2秒内会拉回）
- 如果持续超调>1m，按 `Ctrl+C` 停止

**后续调整：**
```python
# 增强阻尼
KD_XY = 15.0  # 提高微分增益（原12）

# 或者降低控制权重，让MPC更保守
# 编辑 control_mpc/mpc_controller.py 第44行
self.Q = np.diag([150.0, 150.0, 1.0, 1.0])  # 降低位置权重（原100）
self.R = np.diag([2.0, 2.0])                # 提高控制权重（原1.0）
```

#### 情况3: 无响应（控制量为0）

**现象：**
```
#0050 | 测量(+0.10,+0.05) | 距 41cm | 控制[+0, +0]  ← 异常
#0060 | 测量(+0.10,+0.05) | 距 41cm | 控制[+0, +0]
#0070 | 测量(+0.10,+0.05) | 距 41cm | 控制[+0, +0]
```

**原因分析：**
- MPC求解器失败（检查 `MPC:fail` 标志）
- 模型A矩阵奇异（不可逆）
- 程序bug

**立即操作：**
1. **紧急切换手动模式**
2. 按 `Ctrl+C` 停止程序
3. 查看终端错误信息

**排查步骤：**
```bash
# 1. 检查模型文件
cat control_mpc/identified_model.json

# 2. 检查A矩阵条件数（越接近1越好）
python -c "
import numpy as np
import json
with open('control_mpc/identified_model.json') as f:
    data = json.load(f)
A = np.array(data['A_matrix'])
cond = np.linalg.cond(A)
print(f'A矩阵条件数: {cond:.2f}')
print('良好' if cond < 100 else '不佳' if cond < 1000 else '极差')
"

# 3. 如果条件数>1000，重新辨识
```

#### 情况4: 发散（越飞越远）

**现象：**
```
#0050 | 测量(+0.20,+0.10) | 距 32cm | 控制[+50, +0]
#0060 | 测量(+0.35,+0.15) | 距 40cm | 控制[+60, +0]  ← 距离增大
#0070 | 测量(+0.55,+0.20) | 距 60cm | 控制[+80, +0]  ← 持续增大
#0080 | 测量(+0.80,+0.30) | 距 86cm | 控制[+100,+0]  ← 危险！
```

**危险等级：⚠️⚠️⚠️ 最高**

**立即操作：**
1. **立即切换手动模式**
2. **拉回中心位置**
3. **降落**
4. **不要重新运行程序**

**原因分析：**
- A矩阵不稳定（特征值>1）
- 控制反向（B矩阵符号错误）
- 严重的程序bug

**必须执行的检查：**
```python
# 检查A矩阵稳定性
python -c "
import numpy as np
import json
with open('control_mpc/identified_model.json') as f:
    data = json.load(f)
A = np.array(data['A_matrix'])
eigvals = np.linalg.eigvals(A)
print('A矩阵特征值:')
for i, ev in enumerate(eigvals):
    stable = '稳定' if abs(ev) < 1.0 else '不稳定'
    print(f'  λ{i} = {ev:.4f} ({stable})')
if all(abs(ev) < 1.0 for ev in eigvals):
    print('✓ 系统稳定')
else:
    print('✗ 系统不稳定，禁止使用此模型！')
"
```

**如果显示"系统不稳定"：**
1. 删除模型文件：`rm control_mpc/identified_model.json`
2. 重新进行系统辨识（延长时间至15秒）
3. 如仍不稳定，放弃MPC，使用PID控制

### 5.7 数据记录

**自动记录的数据：**

所有控制数据会实时保存到：
```
data/mpc/YYYYMMDD_HHMMSS/mpc_control_data.csv
```

**CSV文件内容：**
```csv
timestamp,target_x,target_y,measured_x,measured_y,estimated_x,estimated_y,estimated_vx,estimated_vy,distance,mpc_pitch,mpc_roll,mpc_cost,delay_compensation,prediction_steps
1735898422.123,0.50,0.00,0.12,0.03,0.15,0.02,0.15,0.01,0.384,45.2,8.1,123.4,success,10
1735898422.143,0.50,0.00,0.14,0.03,0.17,0.02,0.16,0.01,0.364,43.8,7.5,118.2,success,10
...
```

**实时查看日志：**
```bash
# 另开一个终端
tail -f data/mpc/latest/mpc_control_data.csv
```

### 5.8 手动终止控制

**安全终止（推荐）：**

按 `Ctrl+C`，程序会执行清理流程：

```
^C
⚠ 收到中断信号

━━━ 清理资源 ━━━
发送悬停指令...
✓ 心跳已停止
✓ MQTT已断开
✓ VRPN已断开

✓ 已安全退出
```

**注意事项：**
- 程序会自动发送5次悬停指令（500ms）
- 无人机会保持当前位置悬停
- **遥控器需接管后才能降落**

---

## 6. 异常处理预案

### 6.1 紧急情况处理流程

#### 级别1: 一般异常（黄色警告）
**现象：** 小幅振荡、位置偏差、MPC偶尔失败

**处理：**
1. 继续观察30秒
2. 如未恶化，等待自动恢复
3. 如持续不改善，按 `Ctrl+C` 停止

#### 级别2: 严重异常（红色告警）
**现象：** 大幅超调、持续振荡、发散趋势

**处理：**
1. **立即** 按 `Ctrl+C` 停止程序
2. **遥控器切换手动模式**
3. 归中杆量，稳定悬停
4. 分析日志，排查问题
5. 调整参数后重试

#### 级别3: 紧急情况（最高优先级）
**现象：**
- 无人机急速飞向边界
- 突然下坠/上升
- 完全失控
- 动捕系统失联

**处理：**
1. **遥控器立即切换手动模式**（第一优先级）
2. **稳定姿态** 或 **紧急降落**
3. 电脑按 `Ctrl+C`（如来得及）
4. 事后分析日志，上报异常

### 6.2 特定异常场景

#### 场景1: 动捕系统失联

**检测方式：**
```
#0100 | 测量(+0.50,+0.00) | 距  5cm | ...
#0101 | 测量(+0.50,+0.00) | 距  5cm | ...  ← 位置冻结
#0102 | 测量(+0.50,+0.00) | 距  5cm | ...
```

或程序报错：
```
✗ VRPN数据超时 (>1s无更新)
```

**应对：**
1. 遥控器切换手动，稳定悬停
2. 检查动捕软件（是否崩溃/卡死）
3. 检查网络连接（网线是否松动）
4. 重启VRPN服务后重新运行程序

**预防措施：**
- 实验前ping测试动捕服务器
- 使用有线网络（不用WiFi）
- 动捕电脑关闭省电模式

#### 场景2: MQTT通信丢失

**检测方式：**
```
✗ 心跳发送失败: Connection lost
```

或无人机无响应（但动捕正常）

**应对：**
1. 遥控器已自动恢复控制权（DRC模式超时）
2. 按 `Ctrl+C` 停止程序
3. 手动飞回中心，降落
4. 检查MQTT broker状态
5. 检查网络连接

**预防措施：**
- 使用有线网络连接MQTT broker
- 确保broker运行稳定（不在树莓派等低性能设备上）
- 监控broker日志

#### 场景3: 无人机电池低电量

**检测方式：**
- 遥控器告警音
- DJI Pilot App提示

**应对：**
1. **立即** 按 `Ctrl+C` 停止程序
2. 遥控器接管
3. **立即降落**（无论实验是否完成）
4. 更换电池后重新开始

**预防措施：**
- 实验前确保电池≥80%
- 设置电池告警阈值为30%（在DJI Pilot中）
- 准备备用电池

#### 场景4: 程序崩溃/Hang住

**检测方式：**
```
#0200 | ... | 距 15cm | ...
#0201 | ... | 距 15cm | ...
[卡住，无新输出]
```

或Python报错：
```
Segmentation fault (core dumped)
```

**应对：**
1. **遥控器立即切换手动模式**
2. 稳定悬停或降落
3. 电脑端按 `Ctrl+C` 或 `Ctrl+Z` 强制结束
4. 如无响应，`kill -9 <pid>`

**预防措施：**
- 使用最新版本代码
- Python环境稳定（不混用conda/venv）
- 充足的内存（至少2GB可用）

### 6.3 场地边界保护

**软件保护（待实现）：**
```python
# 在 mpc_main.py 中添加边界检查
def check_safety_boundary(position, radius=1.8):
    """检查是否即将越界"""
    dist = np.linalg.norm(position[:2])
    if dist > radius:
        console.print(f"[red]⚠️ 边界告警！距离中心{dist:.2f}m[/red]")
        return False
    return True
```

**硬件保护（推荐）：**
1. 在场地边界（1.8m半径）设置物理栅栏
2. 使用DJI SDK的地理围栏功能（如支持）
3. 遥控器设置最大飞行距离限制

**人工监控：**
- 至少1名安全员专职监控无人机位置
- 准备标准化的喊话流程："边界告警，准备接管"

---

## 7. 实验后处理

### 7.1 安全降落

**标准流程：**

1. **程序终止后（Ctrl+C）**
   ```
   ✓ 已安全退出
   ```

2. **遥控器接管**
   - 确认模式切换到手动
   - 检查杆量响应正常

3. **降落前检查**
   - 确认场地中心无人员
   - 确认无障碍物
   - 告知周围人员："准备降落"

4. **缓慢降落**
   - 缓推油门杆向下
   - 保持水平姿态
   - 距地面10cm时悬停1秒
   - 轻触地面后立即关闭电机

### 7.2 数据保存与分析

**数据位置：**
```
data/mpc/YYYYMMDD_HHMMSS/
├── mpc_control_data.csv    # 控制数据
└── (可能的其他日志文件)
```

**快速分析：**

```bash
# 1. 查看控制统计信息
python -c "
import pandas as pd
df = pd.read_csv('data/mpc/latest/mpc_control_data.csv')

print('控制统计信息：')
print(f'  总采样数: {len(df)}')
print(f'  平均距离: {df[\"distance\"].mean():.4f}m')
print(f'  最大距离: {df[\"distance\"].max():.4f}m')
print(f'  平均pitch: {df[\"mpc_pitch\"].mean():.2f}')
print(f'  平均roll: {df[\"mpc_roll\"].mean():.2f}')
print(f'  MPC成功率: {(df[\"delay_compensation\"]==\"success\").mean()*100:.1f}%')
"

# 2. 生成可视化图表（如已安装matplotlib）
python -c "
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('data/mpc/latest/mpc_control_data.csv')
df['time'] = df['timestamp'] - df['timestamp'].iloc[0]

fig, axes = plt.subplots(3, 1, figsize=(12, 8))

# 位置轨迹
axes[0].plot(df['time'], df['measured_x'], label='Measured X')
axes[0].plot(df['time'], df['measured_y'], label='Measured Y')
axes[0].plot(df['time'], df['target_x'], '--', label='Target X')
axes[0].plot(df['time'], df['target_y'], '--', label='Target Y')
axes[0].set_ylabel('Position (m)')
axes[0].legend()
axes[0].grid(True)

# 距离误差
axes[1].plot(df['time'], df['distance'])
axes[1].axhline(y=0.08, color='r', linestyle='--', label='Threshold')
axes[1].set_ylabel('Distance (m)')
axes[1].legend()
axes[1].grid(True)

# 控制量
axes[2].plot(df['time'], df['mpc_pitch'], label='Pitch')
axes[2].plot(df['time'], df['mpc_roll'], label='Roll')
axes[2].set_ylabel('Control (stick units)')
axes[2].set_xlabel('Time (s)')
axes[2].legend()
axes[2].grid(True)

plt.tight_layout()
plt.savefig('data/mpc/latest/analysis.png', dpi=150)
print('图表已保存: data/mpc/latest/analysis.png')
"
```

**评估指标：**

| 指标 | 优秀 | 良好 | 需改进 |
|------|------|------|--------|
| 到达时间 | <5s | 5-10s | >10s |
| 最大距离误差 | <15cm | 15-30cm | >30cm |
| 稳态误差 | <2cm | 2-5cm | >5cm |
| 控制平滑度（pitch标准差） | <20 | 20-40 | >40 |
| MPC成功率 | >99% | 95-99% | <95% |

### 7.3 实验报告模板

**创建实验记录：**

```bash
cat > data/mpc/latest/experiment_report.md << EOF
# MPC控制实验报告

## 实验信息
- 日期: $(date +%Y-%m-%d)
- 无人机: $(grep GATEWAY_SN control/config.py | cut -d"'" -f2)
- 场地: 2m半径动捕场地
- 操作员: [姓名]

## 配置参数
- 系统辨识时间: 10秒
- 激励幅值: 30
- 预测时域: 10步
- 控制频率: 50Hz

## 系统辨识结果
- R² = [从日志复制]
- A矩阵稳定性: [稳定/不稳定]
- 辨识用时: [X秒]

## 控制性能
- 目标航点: (0.5, 0.0)
- 到达时间: [X秒]
- 最大误差: [Xcm]
- 稳态误差: [Xcm]

## 异常情况
- [如有异常，描述现象和处理]
- [无异常写"无"]

## 改进建议
- [基于本次实验的改进建议]

## 附件
- 控制数据: mpc_control_data.csv
- 轨迹图表: analysis.png
EOF

echo "实验报告模板已创建: data/mpc/latest/experiment_report.md"
```

### 7.4 系统关闭

**软件关闭：**
```bash
# 1. 确认程序已退出（Ctrl+C后）
ps aux | grep mpc_main  # 应无输出

# 2. 停止VRPN客户端（如独立运行）
# （通常随程序自动关闭）

# 3. 停止MQTT broker（如在本地）
# sudo systemctl stop mosquitto  # 仅限本地broker

# 4. 备份日志
cp -r data/mpc/latest data/mpc/backup_$(date +%Y%m%d_%H%M%S)
```

**硬件关闭：**
```bash
# 无人机
1. 遥控器：长按电源键关机
2. 无人机：长按电源键关机
3. 等待电机完全停转后移除电池

# 动捕系统
1. 关闭动捕软件
2. 关闭VRPN服务器（如独立运行）
   sudo systemctl stop vrpn
```

---

## 8. 故障排查手册

### 8.1 症状索引

| 症状 | 可能原因 | 快速定位 | 详细章节 |
|------|---------|---------|---------|
| 程序启动失败 | 依赖缺失/配置错误 | 检查错误信息 | [8.2](#82-启动问题) |
| VRPN连接失败 | 网络/服务器问题 | ping测试 | [8.3](#83-通信问题) |
| MQTT连接失败 | Broker未运行 | telnet测试 | [8.3](#83-通信问题) |
| 系统辨识失败 | 数据质量差 | 检查R² | [8.4](#84-辨识问题) |
| 控制振荡 | 增益过高 | 降低KP | [8.5](#85-控制问题) |
| 控制超调 | 阻尼不足 | 提高KD | [8.5](#85-控制问题) |
| MPC求解失败 | 模型奇异 | 检查条件数 | [8.5](#85-控制问题) |
| 无人机漂移 | 环境干扰 | 检查气流 | [8.6](#86-环境问题) |

### 8.2 启动问题

#### 错误: ImportError: No module named 'numpy'

**原因：** 依赖包未安装

**解决：**
```bash
pip install numpy scipy rich zmq paho-mqtt
# 或使用requirements.txt
pip install -r requirements.txt
```

#### 错误: FileNotFoundError: control/config.py

**原因：** 路径错误

**解决：**
```bash
# 确认当前路径
pwd  # 应该在 pythonSDK/ 目录

# 如果不是，切换目录
cd /path/to/Volition-DJI/pythonSDK
```

#### 错误: KeyError: 'GATEWAY_SN'

**原因：** 配置文件格式错误

**解决：**
```bash
# 检查配置文件语法
python -m py_compile control/config.py

# 如果报错，逐行检查语法
vim control/config.py
```

### 8.3 通信问题

#### VRPN连接超时

**诊断步骤：**
```bash
# 1. 测试网络连通性
ping 192.168.31.100
# 预期：< 10ms延迟

# 2. 测试端口
telnet 192.168.31.100 3883
# 预期：Connected to 192.168.31.100

# 3. 检查VRPN服务状态
ssh user@192.168.31.100
ps aux | grep vrpn
# 预期：看到vrpn_server进程

# 4. 检查防火墙
sudo ufw status
# 预期：3883端口允许
```

**解决方案：**
- 网络不通：检查网线、交换机
- 端口不通：重启VRPN服务
- 服务未运行：启动VRPN服务

#### MQTT连接拒绝

**诊断步骤：**
```bash
# 1. 检查broker运行状态
ps aux | grep mosquitto
# 或
sudo systemctl status mosquitto

# 2. 测试匿名连接
mosquitto_pub -h 192.168.31.73 -t test -m "hello"
# 如果失败，检查broker配置

# 3. 测试认证连接
mosquitto_pub -h 192.168.31.73 -t test -m "hello" -u dji -P lab605605
# 如果失败，检查用户名密码

# 4. 检查broker日志
sudo tail -f /var/log/mosquitto/mosquitto.log
```

**解决方案：**
- Broker未运行：`sudo systemctl start mosquitto`
- 认证失败：检查 `control/config.py` 中的用户名密码
- 端口占用：`sudo netstat -tuln | grep 1883`

### 8.4 辨识问题

#### R² < 0.6 (模型质量不佳)

**可能原因：**
1. 激励幅值过小
2. 辨识时间过短
3. 数据噪声大

**诊断：**
```bash
# 查看原始数据质量
python -c "
import sys
sys.path.insert(0, '.')
# 手动运行system_id.py的测试代码
"
```

**解决方案：**
```python
# 编辑 control_mpc/system_id.py
self.excitation_amplitude = 40.0  # 提高至40（原30）

# 编辑 control_mpc/mpc_main.py
self.identification_duration = 15.0  # 延长至15秒（原10）
```

#### A矩阵不稳定（特征值>1）

**这是严重问题，禁止使用该模型！**

**排查步骤：**
```bash
# 1. 检查数据采样率
python -c "
import pandas as pd
df = pd.read_csv('data/mpc/latest/mpc_control_data.csv')
dt = df['timestamp'].diff().mean()
print(f'实际采样周期: {dt:.4f}s (预期: 0.02s)')
if abs(dt - 0.02) > 0.005:
    print('警告：采样周期不稳定！')
"

# 2. 检查延迟估计
python -c "
import json
with open('control_mpc/identified_model.json') as f:
    data = json.load(f)
print(f'使用的延迟步数: {data.get(\"delay_steps\", \"未知\")}')
# 应该是10步（200ms @ 50Hz）
"
```

**解决方案：**
- 如果采样周期不稳定：检查CPU负载，关闭后台任务
- 如果延迟估计错误：手动测量真实延迟，调整 `delay_steps`
- 如果持续失败：联系技术支持

### 8.5 控制问题

#### 振荡（往复运动）

**快速修复（临时）：**
```python
# 编辑 control/config.py
KP_XY = 250.0  # 降低20%
MAX_STICK_OUTPUT = 80  # 降低20%
```

**根本修复（需要重新辨识）：**
```python
# 编辑 control_mpc/mpc_controller.py
# 调整权重矩阵
self.Q = np.diag([80.0, 80.0, 1.0, 1.0])   # 降低位置权重
self.R = np.diag([2.0, 2.0])                # 提高控制代价
```

#### 超调（冲过目标）

**快速修复：**
```python
# 编辑 control/config.py
KD_XY = 18.0  # 提高50%
```

**分析工具：**
```bash
# 查看速度曲线，诊断减速是否及时
python -c "
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('data/mpc/latest/mpc_control_data.csv')
df['time'] = df['timestamp'] - df['timestamp'].iloc[0]
df['speed'] = (df['estimated_vx']**2 + df['estimated_vy']**2)**0.5

plt.figure(figsize=(10, 6))
plt.subplot(2,1,1)
plt.plot(df['time'], df['distance'], label='Distance')
plt.axhline(y=0.08, color='r', linestyle='--')
plt.ylabel('Distance (m)')
plt.legend()
plt.grid(True)

plt.subplot(2,1,2)
plt.plot(df['time'], df['speed'], label='Speed')
plt.ylabel('Speed (m/s)')
plt.xlabel('Time (s)')
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig('debug_overshoot.png')
print('图表已保存: debug_overshoot.png')
"
```

### 8.6 环境问题

#### 无人机持续漂移

**检查清单：**
- [ ] 空调/风扇是否对准无人机
- [ ] 场地是否有气流（门窗）
- [ ] IMU是否需要重新校准
- [ ] 光流传感器是否被遮挡（如使用）

**临时解决：**
- 关闭空调/风扇
- 关闭门窗
- 手动补偿漂移（遥控器微调）

#### 动捕数据跳变

**检查清单：**
- [ ] 标记点是否松动
- [ ] 是否有反光物体干扰
- [ ] 相机是否被遮挡
- [ ] 光线是否均匀

**诊断工具（在动捕软件中）：**
1. 查看3D重建质量
2. 检查标记点识别数量
3. 查看残差（应<0.5mm）

**解决方案：**
- 重新贴附标记点
- 移除反光物体
- 调整相机角度
- 增加补光灯

---

## 附录A：配置文件模板（2m场地优化版）

```python
# control/config.py - 针对2m半径场地的安全配置

"""
配置参数模块 - 2m场地优化版
适用场景：受限空间，安全第一
"""

# ========== 无人机配置 ==========
GATEWAY_SN = '9N9CN2J0012CXY'  # 修改为你的无人机序列号
VRPN_DEVICE = 'Drone001@192.168.31.100'  # 修改为你的VRPN设备名

# ========== MQTT配置 ==========
MQTT_CONFIG = {
    'host': '192.168.31.73',  # MQTT broker地址
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# ========== 数据记录配置 ==========
ENABLE_DATA_LOGGING = True   # 强烈建议启用，用于分析

# ========== 航点配置（2m场地安全版）==========
WAYPOINTS = [
    (0.0, 0.0),    # 中心点（起飞位置）
    (0.4, 0.0),    # 前方40cm（保守）
    (0.0, 0.4),    # 左侧40cm
    (-0.4, 0.0),   # 后方40cm
    (0.0, -0.4),   # 右侧40cm
    (0.3, 0.3),    # 对角线（42cm距离）
]

# ⚠️ 安全限制
PLANE_USE_RANDOM_WAYPOINTS = False  # 禁用随机航点
PLANE_AUTO_NEXT_WAYPOINT = False    # 手动确认每个航点

# ========== PID增益（保守调参）==========
KP_XY = 300.0   # 比例增益（降低以减少超调）
KI_XY = 15.0    # 积分增益（降低以防积分饱和）
KD_XY = 15.0    # 微分增益（提高以增强阻尼）

KP_YAW = 12.0
KI_YAW = 5.0
KD_YAW = 1.0

# ========== 控制参数 ==========
CONTROL_FREQUENCY = 50        # 控制频率（Hz）
TOLERANCE_XY = 0.08           # 到达阈值（米）- 收紧
TOLERANCE_YAW = 2.0           # Yaw角阈值（度）
MAX_STICK_OUTPUT = 100        # 杆量限幅 - 降低至100
MAX_YAW_STICK_OUTPUT = 660
NEUTRAL = 1024

# ========== 到达判定 ==========
PLANE_ARRIVAL_STABLE_TIME = 1.5  # 延长稳定时间以确保真正到达

# ========== 高级控制特性（可选）==========
PLANE_GAIN_SCHEDULING_CONFIG = {
    'enabled': True,
    'distance_far': 0.8,    # 远距离阈值（降低）
    'distance_near': 0.15,  # 近距离阈值
    'profile': {
        'far': {'kp_scale': 1.0, 'kd_scale': 0.3},
        'near': {'kp_scale': 0.8, 'kd_scale': 1.5},
    }
}

PLANE_PID_RESET_ON_APPROACH = {
    'enabled': True,
    'reset_mask': '010',
    'trigger_distance': 0.12,
    'mute_duration': 0.8
}
```

---

## 附录B：快速检查清单（实验前必读）

**打印此清单，实验前逐项确认：**

```
□ 硬件检查
  □ 无人机电池 ≥ 80%
  □ 螺旋桨紧固，无损伤
  □ IMU校准（7天内）
  □ 遥控器电量充足

□ 软件检查
  □ Python依赖包已安装
  □ VRPN连接测试通过
  □ MQTT连接测试通过
  □ 配置文件已调整（航点在1.5m内）

□ 场地检查
  □ 2m半径内无障碍物
  □ 地面平整，无反光
  □ 光线充足均匀
  □ 无气流干扰

□ 安全检查
  □ 安全员就位
  □ 急停流程已培训
  □ 遥控器随时可接管
  □ 安全警戒线已设置

□ 数据准备
  □ 磁盘空间 > 1GB
  □ 日志目录可写
  □ 备份已创建

□ 人员准备
  □ 飞手经验充足
  □ 安全员熟悉场地
  □ 沟通手势已约定

□ 应急准备
  □ 急救包已备
  □ 应急联系人已知悉
  □ 保险已购买（如需要）
```

---

## 附录C：常用命令速查

```bash
# === 实验前 ===
# 测试VRPN
python vrpn_test.py

# 验证航点安全
python -c "from control.config import WAYPOINTS; [print(f'{i}: {wp} dist={(wp[0]**2+wp[1]**2)**0.5:.2f}m') for i, wp in enumerate(WAYPOINTS)]"

# === 实验中 ===
# 启动MPC控制
python control_mpc/mpc_main.py

# 查看实时日志（另开终端）
tail -f data/mpc/latest/mpc_control_data.csv

# 监控系统资源
htop  # 查看CPU/内存

# === 实验后 ===
# 快速数据分析
python -c "import pandas as pd; df=pd.read_csv('data/mpc/latest/mpc_control_data.csv'); print(f'平均距离:{df[\"distance\"].mean():.3f}m')"

# 备份数据
cp -r data/mpc/latest data/mpc/backup_$(date +%Y%m%d_%H%M%S)

# === 故障排查 ===
# 检查A矩阵稳定性
python -c "import numpy as np, json; A=np.array(json.load(open('control_mpc/identified_model.json'))['A_matrix']); print('稳定' if all(abs(ev)<1 for ev in np.linalg.eigvals(A)) else '不稳定')"

# 查看进程
ps aux | grep python

# 强制终止
pkill -9 -f mpc_main
```

---

## 附录D：联系支持

如遇到本手册无法解决的问题，请按以下优先级联系支持：

1. **查看GitHub Issues**: https://github.com/your-repo/issues
2. **发送问题报告**:
   ```bash
   # 自动收集诊断信息
   python utils/collect_diagnostics.py > diagnostics.txt
   # 附带日志文件发送至: support@example.com
   ```
3. **紧急问题**: 致电 XXX-XXXX-XXXX（工作时间：9:00-18:00）

**报告问题时请提供：**
- 完整的错误信息
- `control/config.py` 配置文件
- 最近的日志文件 `data/mpc/latest/`
- 系统辨识结果（如有）
- 视频录像（如可能）

---

**文档版本：** v1.0
**最后更新：** 2025-01-03
**适用版本：** pythonSDK v0.1.7
**作者：** Claude (Anthropic)

**注意：** 本文档仍在持续改进中，如有建议或发现错误，请提交Issue或Pull Request。
