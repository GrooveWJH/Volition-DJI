# IVAS 配置传递验证报告

本文档验证 IVAS 任务执行时，三个无人机的起飞高度和航迹高度配置是否正确传递。

## 配置源（dashboard/config.py）

```python
UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',
        'callsign': 'Pilot 1',
        'flight_height': 90.0,  # ← UAV 1 起飞和航迹高度
        'ivas': {'device_code': 1, 'account': 'ZSDX001', 'password': '000000'}
    },
    {
        'sn': '9N9CN8400164WH',
        'callsign': 'Pilot 2',
        'flight_height': 100.0,  # ← UAV 2 起飞和航迹高度
        'ivas': {'device_code': 2, 'account': 'ZSDX002', 'password': '000000'}
    },
    {
        'sn': '9N9CN180011TJN',
        'callsign': 'Pilot 3',
        'flight_height': 110.0,  # ← UAV 3 起飞和航迹高度
        'ivas': {'device_code': 3, 'account': 'ZSDX003', 'password': '000000'}
    }
]
```

**预期行为**：
- **UAV 1**：起飞到 90m，轨迹任务在 90m 高度飞行
- **UAV 2**：起飞到 100m，轨迹任务在 100m 高度飞行
- **UAV 3**：起飞到 110m，轨迹任务在 110m 高度飞行

---

## 配置传递链路验证

### 步骤 1: Dashboard 初始化 IVASAdapter

**文件**: `dashboard/monitor.py:168-178`

```python
adapter = IVASAdapter(
    device_code=ivas_config['device_code'],
    mqtt_client=uav['mqtt'],
    ivas_config={
        **IVAS_SERVER,
        'account': ivas_config['account'],
        'password': ivas_config['password'],
    },
    uav_config=config,  # ✅ 完整的 UAV 配置（包含 flight_height）
    service_caller=uav['caller'],
    heartbeat_thread=uav['heartbeat'],
    features=IVAS_FEATURES
)
```

**验证**：✅ 传递了完整的 `config`，包含 `flight_height`

---

### 步骤 2: IVASAdapter 保存配置

**文件**: `dashboard/ivas_adapter.py:61`

```python
def __init__(self, device_code, mqtt_client, ivas_config, uav_config, ...):
    self.uav_config = uav_config  # ✅ 保存完整配置
```

**验证**：✅ `uav_config` 被保存为实例变量

---

### 步骤 3: 任务执行时传递配置

**文件**: `dashboard/ivas_adapter.py:98-105`

```python
def _execute_task_in_background(self, task_data):
    execute_ivas_task(
        task_data,
        self.mqtt,
        self.caller,
        self.uav_config,  # ✅ 传递 uav_config
        self.heartbeat_thread,
        runner=self.current_runner
    )
```

**验证**：✅ 调用 `execute_ivas_task` 时传递了 `uav_config`

---

### 步骤 4: 任务分发器接收配置

**文件**: `djisdk/tasks/ivas_executor.py:27-34`

```python
def execute_ivas_task(
    task_data: Dict[str, Any],
    mqtt_client,
    caller,
    uav_config: Dict[str, str],  # ✅ 接收 uav_config 参数
    heartbeat_thread: Optional[threading.Thread] = None,
    runner: Optional['MissionRunner'] = None
) -> None:
```

**验证**：✅ 函数签名包含 `uav_config` 参数

---

### 步骤 5a: Mission 1（起飞）使用 flight_height

**文件**: `djisdk/tasks/ivas_executor.py:81-94`

```python
def _task_takeoff(mqtt, caller, heartbeat, uav_config: Dict[str, Any], runner=None):
    """任务1: 起飞到预设高度"""
    # ✅ 从配置读取起飞高度，默认 20.0 米
    target_height = uav_config.get('flight_height', 20.0)
    callsign = uav_config.get('callsign', '未知')

    console.print(f"[cyan][{callsign}] 开始起飞到预设高度 {target_height}m...[/cyan]")

    takeoff_mission = create_takeoff_mission(
        target_height=target_height,  # ✅ 使用配置中的高度
        height_tolerance=0.5,
        throttle_offset=660
    )
```

**验证**：✅ Mission 1 正确使用 `uav_config['flight_height']`

**实际效果**：
- UAV 1 执行 mission=1 → 起飞到 90m
- UAV 2 执行 mission=1 → 起飞到 100m
- UAV 3 执行 mission=1 → 起飞到 110m

---

### 步骤 5b: Mission 5-7（轨迹任务）使用 flight_height

**文件**: `djisdk/tasks/ivas_executor.py:174-219`

```python
def _task_trajectory(mqtt, caller, mission: int, uav_config: Dict[str, str], callsign: str, runner=None):
    """任务5-7: 执行预设轨迹任务"""
    # ...加载轨迹文件...

    # 更新 runner 配置
    runner.config['trajectory_file'] = trajectory_file
    runner.config['flight_height'] = uav_config.get('flight_height', 20.0)  # ✅ 保存到 runner

    runner.data['total_waypoints'] = len(waypoints)
    runner.data['current_waypoint'] = 0

    # ✅ 执行轨迹（使用配置中的高度）
    flight_height = uav_config.get('flight_height', 20.0)
    success = fly_trajectory_sequence(
        runners=[runner],
        waypoints=waypoints,
        height=flight_height,  # ✅ 传递高度参数
        max_speed=12,
        hover_between_waypoints=5.0,
        show_progress=False,
        debug=False
    )
```

**验证**：✅ Mission 5-7 正确使用 `uav_config['flight_height']`

**实际效果**：
- UAV 1 执行 mission=5 → 在 90m 高度飞行轨迹
- UAV 2 执行 mission=6 → 在 100m 高度飞行轨迹
- UAV 3 执行 mission=7 → 在 110m 高度飞行轨迹

---

### 步骤 5c: Mission 4（飞向指定点）行为

**文件**: `djisdk/tasks/ivas_executor.py:158-171`

```python
def _task_fly_to_point(caller, lat: float, lon: float, alt: float, callsign: str):
    """任务4: 飞向指定点"""
    console.print(f"[cyan][{callsign}] 飞向目标点 (lat:{lat:.6f}, lon:{lon:.6f}, alt:{alt:.1f}m)...[/cyan]")

    fly_to_id = fly_to_point(
        caller,
        latitude=lat,
        longitude=lon,
        height=alt,  # ⚠️ 使用任务数据中的 alt 参数，不是配置中的 flight_height
        max_speed=12
    )
```

**说明**：Mission 4 允许指定任意高度（由任务数据提供），**不使用配置中的 flight_height**。

**行为正确性**：✅ 这是预期行为，因为 Mission 4 的目的是飞向指定 GPS 坐标（包括高度）。

---

## 完整数据流图

```
dashboard/config.py
    │
    ├─ UAV_CONFIGS[0] = {flight_height: 90.0, callsign: 'Pilot 1', ...}
    ├─ UAV_CONFIGS[1] = {flight_height: 100.0, callsign: 'Pilot 2', ...}
    └─ UAV_CONFIGS[2] = {flight_height: 110.0, callsign: 'Pilot 3', ...}
         │
         ▼
dashboard/monitor.py:176
    uav_config=config  (完整配置传递)
         │
         ▼
dashboard/ivas_adapter.py:61
    self.uav_config = uav_config  (保存配置)
         │
         ▼
dashboard/ivas_adapter.py:102
    execute_ivas_task(..., self.uav_config, ...)  (调用时传递)
         │
         ▼
djisdk/tasks/ivas_executor.py:59-70
    if mission == 1:
        _task_takeoff(..., uav_config, ...)  → 读取 uav_config['flight_height']
         │
         ├─ UAV 1 → 90m
         ├─ UAV 2 → 100m
         └─ UAV 3 → 110m
    elif mission in [5, 6, 7]:
        _task_trajectory(..., uav_config, ...)  → 读取 uav_config['flight_height']
         │
         ├─ UAV 1 → 90m 高度轨迹
         ├─ UAV 2 → 100m 高度轨迹
         └─ UAV 3 → 110m 高度轨迹
```

---

## 验证结论

### ✅ 配置传递链路完整

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 配置源定义 | ✅ | `dashboard/config.py` 定义了三个不同高度（90/100/110m） |
| Dashboard 初始化传递 | ✅ | `monitor.py:176` 传递完整 `uav_config` |
| Adapter 保存配置 | ✅ | `ivas_adapter.py:61` 保存 `self.uav_config` |
| 任务执行时传递 | ✅ | `ivas_adapter.py:102` 传递给 `execute_ivas_task` |
| Mission 1 读取配置 | ✅ | `ivas_executor.py:84` 读取 `uav_config['flight_height']` |
| Mission 5-7 读取配置 | ✅ | `ivas_executor.py:210,214` 读取并使用 `flight_height` |

### ✅ 任务行为符合预期

| 任务类型 | 高度来源 | UAV 1 | UAV 2 | UAV 3 |
|---------|---------|-------|-------|-------|
| Mission 1（起飞） | `uav_config['flight_height']` | 90m | 100m | 110m |
| Mission 5-7（轨迹） | `uav_config['flight_height']` | 90m | 100m | 110m |
| Mission 4（飞点） | `task_data['alt']` | 由任务指定 | 由任务指定 | 由任务指定 |

### 🎯 结论

**配置传递完全正确！** 三个无人机在真实 IVAS 环境下执行任务时：

1. ✅ **起飞高度**会根据各自配置不同（90m / 100m / 110m）
2. ✅ **轨迹飞行高度**会根据各自配置不同（90m / 100m / 110m）
3. ✅ 不同无人机可以同时执行任务，各自在不同高度飞行，避免碰撞

---

## 测试建议

### 测试场景 1: 起飞任务

```bash
# 终端 1: 启动 Dashboard（连接真实 IVAS）
python main.py

# 终端 2: 发送起飞任务到三个无人机
# 方法1: 使用 keyboard_commander（手动发送）
# 方法2: 使用真实 IVAS 服务器推送任务

# 预期结果:
# - UAV 1 起飞到 90m
# - UAV 2 起飞到 100m
# - UAV 3 起飞到 110m
```

**日志验证**：
```
[cyan][Pilot 1] 开始起飞到预设高度 90.0m...
[cyan][Pilot 2] 开始起飞到预设高度 100.0m...
[cyan][Pilot 3] 开始起飞到预设高度 110.0m...
```

### 测试场景 2: 轨迹任务

```bash
# 发送轨迹任务
# - UAV 1: mission=5 (Trajectory/uav1.json)
# - UAV 2: mission=6 (Trajectory/uav2.json)
# - UAV 3: mission=7 (Trajectory/uav3.json)

# 预期结果:
# - UAV 1 在 90m 高度飞行轨迹
# - UAV 2 在 100m 高度飞行轨迹
# - UAV 3 在 110m 高度飞行轨迹
```

**日志验证**：
```
[dim][Pilot 1] 飞向航点 1/8 (lat:23.123, lon:113.456, alt:90.0m)
[dim][Pilot 2] 飞向航点 1/6 (lat:23.456, lon:113.789, alt:100.0m)
[dim][Pilot 3] 飞向航点 1/5 (lat:23.789, lon:114.012, alt:110.0m)
```

---

**文档版本**: v1.0
**验证日期**: 2025-01-11
**验证人**: Claude Code
