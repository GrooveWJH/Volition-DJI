# 多航点飞行功能重构总结

## 变更概述

将 `mission-trajectory.py` 中的多航点飞行逻辑重构为 `djisdk` 的一部分，现在可以像使用其他 SDK 功能一样简单地调用轨迹飞行。

## 新增模块

### 1. `djisdk/tasks/trajectory.py` - 核心模块

**新增函数**：

```python
# 加载航点文件
load_trajectory(filepath: str) -> List[Dict[str, Any]]

# 执行轨迹飞行（核心函数）
fly_trajectory_sequence(
    runners: List[MissionRunner],
    waypoints: List[Dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True
) -> bool

# 创建轨迹任务函数
create_trajectory_mission(
    waypoints: List[Dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True
)
```

### 2. 更新的导出

**`djisdk/__init__.py`** 新增导出：
- `load_trajectory`
- `fly_trajectory_sequence`
- `create_trajectory_mission`

### 3. 新增文档和示例

- **`docs/TRAJECTORY_GUIDE.md`** - 完整使用指南（400+ 行）
- **`mission-trajectory-simple.py`** - 简化示例（60 行）
- **`mission-trajectory.py`** - 完整示例（已重构，使用新 SDK 功能）

## 使用对比

### 之前（355 行，不可复用）

```python
# mission-trajectory.py（原版本）
def load_trajectory(filepath):
    # 40+ 行实现
    ...

def fly_trajectory_sequence(runners, waypoints, ...):
    # 100+ 行实现
    ...

def main():
    # 200+ 行主逻辑
    ...
```

### 之后（3 行核心代码）

```python
from djisdk import load_trajectory, fly_trajectory_sequence

waypoints = load_trajectory('Trajectory/uav1.json')
success = fly_trajectory_sequence(runners, waypoints, height=100.0)
```

## 代码简化效果

| 项目 | 原版本 | 使用 SDK |
|------|--------|----------|
| 代码行数 | 355 | 60-230 |
| 核心逻辑 | 200+ 行 | 3 行 |
| 可复用性 | ❌ | ✅ |
| 易维护性 | ❌ | ✅ |
| 导入即用 | ❌ | ✅ |

## 功能特性

✅ **自动化航点飞行** - 依次飞向所有航点
✅ **实时进度监控** - 显示剩余距离和时间
✅ **航点间悬停** - 自动稳定飞控状态
✅ **多机并行** - 支持多架无人机同时执行
✅ **错误处理** - 完善的异常处理机制
✅ **详细日志** - 带颜色的进度输出

## 完整示例

### 最简示例（60 行）

```python
#!/usr/bin/env python3
from djisdk import (
    setup_multiple_drc_connections,
    run_parallel_missions,
    create_takeoff_mission,
    load_trajectory,
    fly_trajectory_sequence,
)

UAV_CONFIGS = [{'sn': '9N9CN2J0012CXY', 'callsign': 'Alpha'}]
MQTT_CONFIG = {'host': 'grve.me', 'port': 1883, 'username': 'dji', 'password': '***'}

def main():
    # 1. 加载航点
    waypoints = load_trajectory('Trajectory/uav1.json')

    # 2. 连接无人机
    connections = setup_multiple_drc_connections(UAV_CONFIGS, MQTT_CONFIG)

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

if __name__ == '__main__':
    main()
```

## 使用方法

### 快速开始

```bash
# 1. 准备航点文件（JSON 格式）
cat > Trajectory/my_waypoints.json <<EOF
[
    {"id": 1, "lat": 39.0427514, "lon": 117.7238255},
    {"id": 2, "lat": 39.0428000, "lon": 117.7239000}
]
EOF

# 2. 运行简化示例
python3 mission-trajectory-simple.py

# 3. 或运行完整示例
python3 mission-trajectory.py
```

### Python 代码中使用

```python
from djisdk import load_trajectory, fly_trajectory_sequence

# 加载航点
waypoints = load_trajectory('Trajectory/uav1.json')

# 执行轨迹飞行
success = fly_trajectory_sequence(
    runners=runners,
    waypoints=waypoints,
    height=100.0,
    max_speed=12,
    hover_between_waypoints=5.0,
    show_progress=True
)

if success:
    print("所有航点完成！")
```

## 航点文件格式

```json
[
    {
        "id": 1,
        "lat": 39.0427514,
        "lon": 117.7238255
    },
    {
        "id": 2,
        "lat": 39.0428000,
        "lon": 117.7239000
    }
]
```

字段说明：
- `id` - 航点编号（可选）
- `lat` - 纬度（必填，-90 ~ 90）
- `lon` - 经度（必填，-180 ~ 180）

## 文件结构

```
pythonSDK/
├── djisdk/
│   ├── tasks/
│   │   ├── __init__.py           # 导出轨迹函数
│   │   ├── trajectory.py         # ✨ 新增：轨迹任务模块
│   │   ├── takeoff.py
│   │   └── runner.py
│   └── __init__.py               # 更新：导出轨迹函数
├── docs/
│   └── TRAJECTORY_GUIDE.md       # ✨ 新增：使用指南
├── Trajectory/                   # 航点数据目录
│   ├── uav1.json
│   ├── uav2.json
│   └── uav3.json
├── mission-trajectory.py         # 更新：使用新 SDK
└── mission-trajectory-simple.py  # ✨ 新增：简化示例
```

## API 文档

### `load_trajectory(filepath)`

从 JSON 文件加载航点数据。

**参数**：
- `filepath` (str) - 航点文件路径

**返回**：
- `List[Dict]` - 航点列表

**异常**：
- `FileNotFoundError` - 文件不存在
- `json.JSONDecodeError` - JSON 格式错误
- `ValueError` - 数据格式错误

### `fly_trajectory_sequence()`

依次飞向多个航点。

**参数**：
- `runners` (List[MissionRunner]) - 任务执行器列表
- `waypoints` (List[Dict]) - 航点列表
- `height` (float) - 飞行高度（椭球高，米）
- `max_speed` (int) - 最大速度（m/s，0-15），默认 12
- `hover_between_waypoints` (float) - 航点间悬停时间（秒），默认 5.0
- `show_progress` (bool) - 是否显示进度，默认 True

**返回**：
- `bool` - 是否全部成功

### `create_trajectory_mission()`

创建轨迹飞行任务函数（用于 `run_parallel_missions`）。

**参数**：同 `fly_trajectory_sequence`（除了 `runners`）

**返回**：
- `Callable` - 任务函数

## 测试验证

```bash
# 测试导入
python3 -c "from djisdk import load_trajectory, fly_trajectory_sequence; print('✓ 导入成功')"

# 测试加载航点
python3 -c "from djisdk import load_trajectory; wps = load_trajectory('Trajectory/uav1.json'); print(f'✓ 加载了 {len(wps)} 个航点')"

# 语法检查
python3 -m py_compile mission-trajectory.py
python3 -m py_compile mission-trajectory-simple.py
```

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

## 下一步

- 📖 阅读 `docs/TRAJECTORY_GUIDE.md` 获取完整使用指南
- 🚀 运行 `mission-trajectory-simple.py` 快速体验
- 📝 查看 `mission-trajectory.py` 了解完整实现
- 🔧 根据需求自定义航点文件和参数

## 相关资源

- [djisdk 主 README](../djisdk/README.md)
- [任务系统文档](../djisdk/tasks/README.md)
- [航点原语文档](../djisdk/primitives/waypoint.py)
