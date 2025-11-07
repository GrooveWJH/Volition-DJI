# 多航点轨迹飞行 - 使用指南

## 功能概述

`djisdk.tasks.trajectory` 模块提供了多航点顺序飞行的高级封装，让你只需几行代码就能实现复杂的轨迹飞行任务。

## 核心函数

### 1. `load_trajectory(filepath)` - 加载航点文件

```python
from djisdk import load_trajectory

# 从 JSON 文件加载航点
waypoints = load_trajectory('Trajectory/uav1.json')
print(f"加载了 {len(waypoints)} 个航点")
```

**航点文件格式** (`Trajectory/uav1.json`):
```json
[
    {"id": 1, "lat": 39.0427514, "lon": 117.7238255},
    {"id": 2, "lat": 39.0428000, "lon": 117.7239000},
    {"id": 3, "lat": 39.0428500, "lon": 117.7239500}
]
```

### 2. `fly_trajectory_sequence()` - 执行轨迹飞行

```python
from djisdk import fly_trajectory_sequence

success = fly_trajectory_sequence(
    runners=runners,                  # MissionRunner 列表
    waypoints=waypoints,              # 航点列表
    height=100.0,                     # 飞行高度（米）
    max_speed=12,                     # 最大速度（m/s）
    hover_between_waypoints=5.0,      # 航点间悬停时间（秒）
    show_progress=True                # 显示进度信息
)
```

**功能特性**：
- ✅ 自动依次飞向所有航点
- ✅ 实时监控飞行进度（剩余距离、时间）
- ✅ 航点间自动悬停稳定飞控
- ✅ 多无人机并行执行相同轨迹
- ✅ 详细的进度日志输出

### 3. `create_trajectory_mission()` - 创建任务函数

```python
from djisdk import create_trajectory_mission

# 创建轨迹任务（用于 run_parallel_missions）
trajectory_mission = create_trajectory_mission(
    waypoints=waypoints,
    height=100.0,
    max_speed=12
)

# 并行执行任务
runners = run_parallel_missions(connections, trajectory_mission, uav_configs)
```

## 完整示例

### 最简示例（60 行代码）

```python
#!/usr/bin/env python3
from djisdk import (
    setup_multiple_drc_connections,
    run_parallel_missions,
    cleanup_missions,
    create_takeoff_mission,
    load_trajectory,
    fly_trajectory_sequence,
    return_home,
)

UAV_CONFIGS = [{'sn': '9N9CN2J0012CXY', 'user_id': 'pilot1', 'callsign': 'Alpha'}]
MQTT_CONFIG = {'host': 'grve.me', 'port': 1883, 'username': 'dji', 'password': 'lab605605'}

def main():
    # 1. 加载航点
    waypoints = load_trajectory('Trajectory/uav1.json')

    # 2. 连接无人机
    connections = setup_multiple_drc_connections(
        uav_configs=UAV_CONFIGS,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=100
    )

    try:
        # 3. 起飞
        runners = run_parallel_missions(
            connections,
            create_takeoff_mission(target_height=30.0),
            UAV_CONFIGS
        )

        # 4. 飞行轨迹（核心！）
        fly_trajectory_sequence(
            runners=runners,
            waypoints=waypoints,
            height=100.0,
            max_speed=12
        )

        # 5. 返航
        for runner in runners:
            return_home(runner.caller)

    finally:
        cleanup_missions(runners)

if __name__ == '__main__':
    main()
```

### 完整示例（带详细输出和监控）

参考 `mission-trajectory.py` - 约 230 行，包含：
- 详细的进度显示和表格输出
- 用户确认提示
- 返航后高度监控
- 完善的错误处理

## 使用流程

### 标准流程（5 步）

```python
# 步骤 1: 加载航点数据
waypoints = load_trajectory('Trajectory/uav1.json')

# 步骤 2: 连接无人机并进入 DRC 模式
connections = setup_multiple_drc_connections(uav_configs, mqtt_config)

# 步骤 3: 起飞到指定高度
takeoff_mission = create_takeoff_mission(target_height=30.0)
runners = run_parallel_missions(connections, takeoff_mission, uav_configs)

# 步骤 4: 执行轨迹飞行
success = fly_trajectory_sequence(
    runners=runners,
    waypoints=waypoints,
    height=100.0,
    max_speed=12,
    hover_between_waypoints=5.0
)

# 步骤 5: 返航并清理
for runner in runners:
    return_home(runner.caller)
cleanup_missions(runners)
```

## 参数说明

### `fly_trajectory_sequence()` 参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `runners` | `List[MissionRunner]` | 必填 | 任务执行器列表 |
| `waypoints` | `List[Dict]` | 必填 | 航点列表，每个包含 `lat`, `lon`, 可选 `id` |
| `height` | `float` | 必填 | 飞行高度（椭球高，米） |
| `max_speed` | `int` | `12` | 最大速度（m/s，0-15） |
| `hover_between_waypoints` | `float` | `5.0` | 航点间悬停时间（秒） |
| `show_progress` | `bool` | `True` | 是否显示进度信息 |

**返回值**: `bool` - 是否全部成功

## 进度输出示例

```
━━━ 航点 1/5 (ID: 1) ━━━
目标: lat=39.0427514, lon=117.7238255, h=100.0m
[Alpha] 飞向航点 1...
监控飞行进度...

14:30:15 | Alpha: 航点 1 - 剩余 45.2m, 3.8s
14:30:16 | Alpha: 航点 1 - 剩余 32.1m, 2.7s
14:30:17 | Alpha: 航点 1 - 剩余 18.5m, 1.5s
✓ [Alpha] 已到达航点 1！
✓ 航点 1/5 完成
悬停等待 5.0 秒，飞控状态稳定中...
```

## 高级用法

### 多无人机并行飞行

```python
# 配置 3 架无人机
uav_configs = [
    {'sn': '9N9CN2J0012CXY', 'callsign': 'Alpha'},
    {'sn': '9N9CN8400164WH', 'callsign': 'Bravo'},
    {'sn': '9N9CN180011TJN', 'callsign': 'Charlie'},
]

# 所有无人机会并行飞向相同的航点
fly_trajectory_sequence(runners, waypoints, height=100.0)
```

### 不同无人机飞不同轨迹

```python
# 方法 1: 使用 create_trajectory_mission 创建不同任务
waypoints_alpha = load_trajectory('Trajectory/uav1.json')
waypoints_bravo = load_trajectory('Trajectory/uav2.json')

mission_alpha = create_trajectory_mission(waypoints_alpha, height=100.0)
mission_bravo = create_trajectory_mission(waypoints_bravo, height=120.0)

# 分别执行（需要手动管理）
# ...

# 方法 2: 顺序调用 fly_trajectory_sequence（推荐）
fly_trajectory_sequence([runners[0]], waypoints_alpha, height=100.0)
fly_trajectory_sequence([runners[1]], waypoints_bravo, height=120.0)
```

### 自定义进度显示

```python
# 关闭内置进度显示，自己处理
success = fly_trajectory_sequence(
    runners=runners,
    waypoints=waypoints,
    height=100.0,
    show_progress=False  # 关闭输出
)

# 或使用低级 API 手动监控
from djisdk.primitives import monitor_flyto_progress

status, progress = monitor_flyto_progress(mqtt, callsign="Alpha")
if status == 'wayline_ok':
    print("到达航点！")
```

## 文件结构

```
pythonSDK/
├── djisdk/
│   ├── tasks/
│   │   ├── trajectory.py         # 轨迹任务模块（核心）
│   │   ├── takeoff.py            # 起飞任务
│   │   └── runner.py             # 任务执行框架
│   └── primitives/
│       └── waypoint.py           # 航点原语
├── Trajectory/
│   ├── uav1.json                 # 航点数据示例
│   ├── uav2.json
│   └── uav3.json
├── mission-trajectory.py         # 完整示例（230行）
└── mission-trajectory-simple.py  # 简化示例（60行）
```

## 常见问题

### Q1: 如何调整航点间的等待时间？

```python
fly_trajectory_sequence(
    runners=runners,
    waypoints=waypoints,
    height=100.0,
    hover_between_waypoints=10.0  # 增加到 10 秒
)
```

### Q2: 如何跳过某些航点？

```python
# 在加载后过滤
waypoints = load_trajectory('Trajectory/uav1.json')
waypoints = [wp for wp in waypoints if wp['id'] not in [2, 4]]  # 跳过 ID 2 和 4
```

### Q3: 航点飞行失败怎么办？

```python
success = fly_trajectory_sequence(...)
if not success:
    print("部分航点失败，检查日志")
    # 可以选择重试或返航
    return_home(caller)
```

### Q4: 如何暂停/恢复轨迹飞行？

目前不支持暂停功能。建议使用 `Ctrl+C` 中断后手动处理。

### Q5: 飞机有最低高度限制吗？

有！飞机会自动保障最低飞行高度 20m。如果当前高度低于 20m，会先上升到 20m 再飞向目标点。

## 与原 mission-trajectory.py 的对比

| 特性 | 原版本 | 使用 SDK 模块 |
|------|--------|--------------|
| 代码行数 | 355 行 | 60-230 行 |
| 航点加载 | 手动实现 | `load_trajectory()` |
| 进度监控 | 手动循环 | `fly_trajectory_sequence()` 内置 |
| 错误处理 | 手动处理 | SDK 自动处理 |
| 复用性 | 不可复用 | 高度可复用 |
| 可维护性 | 低 | 高 |

## 下一步

- 查看 `mission-trajectory-simple.py` - 最简示例
- 查看 `mission-trajectory.py` - 完整示例
- 查看 `djisdk/tasks/trajectory.py` - 源码实现
- 查看 `Trajectory/` 目录下的航点文件示例
