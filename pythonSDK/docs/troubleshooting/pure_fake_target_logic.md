# Pure.py spuriou目标上报逻辑详解

## 📋 概述

`pure.py` 是纯净版 IVAS + 多 DRC 程序，专注于 IVAS 任务接收、分发和多无人机控制。本文档详细说明其 spuriou目标上报（Fake Target Reporting）的逻辑，特别是三架无人机并行工作的场景。

## 🏗️ 系统架构

### 整体架构图

```plantuml
@startuml
!define RECTANGLE class

package "Pure.py 主程序" {
    [Main Thread] as main
    [IVAS Task Poller] as task
}

package "UAV 1 (Pilot 1)" {
    [DJI MQTT Client 1] as mqtt1
    [IVAS Client 1\nZSDX001] as ivas1
    [Position Reporter 1] as pos1
    [Fake Target Reporter 1] as fake1
    [Heartbeat 1] as heart1
}

package "UAV 2 (Pilot 2)" {
    [DJI MQTT Client 2] as mqtt2
    [IVAS Client 2\nZSDX002] as ivas2
    [Position Reporter 2] as pos2
    [Fake Target Reporter 2] as fake2
    [Heartbeat 2] as heart2
}

package "UAV 3 (Pilot 3)" {
    [DJI MQTT Client 3] as mqtt3
    [IVAS Client 3\nZSDX003] as ivas3
    [Position Reporter 3] as pos3
    [Fake Target Reporter 3] as fake3
    [Heartbeat 3] as heart3
}

cloud "DJI Cloud\nMQTT Broker" as dji
cloud "IVAS Server\n192.168.31.38:8888" as ivas_server

mqtt1 --> dji : 订阅 OSD/HSI
mqtt2 --> dji : 订阅 OSD/HSI
mqtt3 --> dji : 订阅 OSD/HSI

pos1 --> ivas1 : 上报位置
pos2 --> ivas2 : 上报位置
pos3 --> ivas3 : 上报位置

fake1 --> ivas1 : 上报 spuriou目标
fake2 --> ivas2 : 上报 spuriou目标
fake3 --> ivas3 : 上报 spuriou目标

ivas1 --> ivas_server : HTTP API
ivas2 --> ivas_server : HTTP API
ivas3 --> ivas_server : HTTP API

task --> ivas1 : 轮询任务

note right of fake1
  ID Pool: 10-19
  每2秒上报1个目标
  航点后20秒窗口
end note

note right of fake2
  ID Pool: 20-29
  每2秒上报1个目标
  航点后20秒窗口
end note

note right of fake3
  ID Pool: 30-39
  每2秒上报1个目标
  航点后20秒窗口
end note

@enduml
```

### 关键设计原则

1. **完全并行**: 三架无人机独立运行，互不干扰
2. **独立账户**: 每架 UAV 使用独立的 IVAS 账户登录
3. **ID 隔离**: 每架 UAV 使用不重叠的目标 ID 池
4. **时间窗口**: 仅在到达航点后 20 秒内上报 spuriou目标

## 🎯 spuriou目标上报逻辑

### 核心配置

```python
# config.py - IVAS_FAKE_TARGET 配置
IVAS_FAKE_TARGET = {
    'enabled': True,                   # 总开关
    'report_hz': 0.5,                  # 上报频率（0.5Hz = 每2秒）
    'lat_offset': 0.0001,              # 纬度偏移 ≈ 11m
    'lon_offset': 0.0001,              # 经度偏移 ≈ 8-10m
    'target_count': 1,                 # 每次上报1个目标
    'altitude': 0.0,                   # 固定高度（地面目标）
    'require_gps': True,               # 要求 GPS 有效
    'target_classes': [0, 1],          # 0:人, 1:车
    'target_class_weights': [0.1, 0.9], # 10% 人，90% 车
    'max_targets_per_uav': 10,         # 每个 UAV 10 个循环 ID
    'report_after_waypoint': True,     # 仅在航点后上报
    'report_duration': 20.0,           # 航点后上报持续 20 秒
    'enable_debug_log': False,         # 调试日志
}
```

### ID 分配策略

```plantuml
@startuml
!define RECTANGLE class

rectangle "UAV 1 (device_code=1)" as uav1 {
    rectangle "ID Pool: 10-19" as pool1 {
        rectangle "10" as id10
        rectangle "11" as id11
        rectangle "..." as dots1
        rectangle "19" as id19
    }
    note bottom: base_id = 1 × 10 = 10
}

rectangle "UAV 2 (device_code=2)" as uav2 {
    rectangle "ID Pool: 20-29" as pool2 {
        rectangle "20" as id20
        rectangle "21" as id21
        rectangle "..." as dots2
        rectangle "29" as id29
    }
    note bottom: base_id = 2 × 10 = 20
}

rectangle "UAV 3 (device_code=3)" as uav3 {
    rectangle "ID Pool: 30-39" as pool3 {
        rectangle "30" as id30
        rectangle "31" as id31
        rectangle "..." as dots3
        rectangle "39" as id39
    }
    note bottom: base_id = 3 × 10 = 30
}

note right of uav1
  循环索引: 0 → 1 → ... → 9 → 0
  当前 ID = base_id + index
  示例: 10 → 11 → 12 → ... → 19 → 10
end note

@enduml
```

### 单个无人机上报状态机

```plantuml
@startuml
[*] --> 等待航点

等待航点 : 监听 flyto_progress
等待航点 : status != 'wayline_ok'

等待航点 --> 航点到达 : 检测到 wayline_ok

航点到达 : 记录到达时间
航点到达 : 开启 20 秒上报窗口

航点到达 --> 上报窗口内 : 开始计时

上报窗口内 : 每 2 秒生成 1 个 spuriou目标
上报窗口内 : 循环使用 ID 池
上报窗口内 : 加权随机选择类别

上报窗口内 --> 上报窗口内 : elapsed < 20s\n继续上报

上报窗口内 --> 等待航点 : elapsed > 20s\n停止上报

note right of 上报窗口内
  生成 spuriou目标流程:
  1. 获取无人机 GPS (lat, lon)
  2. 随机偏移 ±10m
  3. 选择类别 (90% 车, 10% 人)
  4. 使用当前 ID (循环索引)
  5. 调用 IVAS API 上报
  6. 索引 +1 (模 10)
end note

@enduml
```

## 🔄 三架无人机并行时序图

### 场景：三架 UAV 到达不同航点

```plantuml
@startuml
participant "UAV 1\n(Pilot 1)" as uav1
participant "IVAS Client 1\n(ZSDX001)" as ivas1
participant "UAV 2\n(Pilot 2)" as uav2
participant "IVAS Client 2\n(ZSDX002)" as ivas2
participant "UAV 3\n(Pilot 3)" as uav3
participant "IVAS Client 3\n(ZSDX003)" as ivas3
participant "IVAS Server" as server

== T=0s: UAV 1 到达航点 1 ==
uav1 -> uav1 : 检测到 wayline_ok
uav1 -> uav1 : 开启 20s 上报窗口\n(T=0 ~ T=20)
activate uav1 #lightblue

== T=2s: UAV 1 首次上报 ==
uav1 -> ivas1 : 上报目标 ID=10 (车)\nGPS: (lat+0.00005, lon-0.00003)
ivas1 -> server : POST /targets\n{"id": 10, "cls": 1, ...}
server --> ivas1 : 200 OK

== T=5s: UAV 2 到达航点 1 ==
uav2 -> uav2 : 检测到 wayline_ok
uav2 -> uav2 : 开启 20s 上报窗口\n(T=5 ~ T=25)
activate uav2 #lightgreen

== T=4s: UAV 1 第二次上报 ==
uav1 -> ivas1 : 上报目标 ID=11 (车)\nGPS: (lat-0.00007, lon+0.00008)
ivas1 -> server : POST /targets\n{"id": 11, "cls": 1, ...}
server --> ivas1 : 200 OK

== T=7s: UAV 2 首次上报 ==
uav2 -> ivas2 : 上报目标 ID=20 (人)\nGPS: (lat+0.00009, lon-0.00002)
ivas2 -> server : POST /targets\n{"id": 20, "cls": 0, ...}
server --> ivas2 : 200 OK

== T=10s: UAV 3 到达航点 1 ==
uav3 -> uav3 : 检测到 wayline_ok
uav3 -> uav3 : 开启 20s 上报窗口\n(T=10 ~ T=30)
activate uav3 #lightyellow

== T=6s: UAV 1 第三次上报 ==
uav1 -> ivas1 : 上报目标 ID=12 (车)
ivas1 -> server : POST /targets
server --> ivas1 : 200 OK

== T=9s: UAV 2 第二次上报 ==
uav2 -> ivas2 : 上报目标 ID=21 (车)
ivas2 -> server : POST /targets
server --> ivas2 : 200 OK

== T=12s: UAV 3 首次上报 ==
uav3 -> ivas3 : 上报目标 ID=30 (车)
ivas3 -> server : POST /targets
server --> ivas3 : 200 OK

note over uav1, server
  三架无人机完全并行工作
  不同的 ID 池保证目标不冲突
  不同的 IVAS 账户保证数据隔离
end note

== T=20s: UAV 1 窗口关闭 ==
uav1 -> uav1 : 窗口超时，停止上报
deactivate uav1

== T=25s: UAV 2 窗口关闭 ==
uav2 -> uav2 : 窗口超时，停止上报
deactivate uav2

== T=30s: UAV 3 窗口关闭 ==
uav3 -> uav3 : 窗口超时，停止上报
deactivate uav3

@enduml
```

## 📊 目标生成详细流程

### 假目标生成算法

```plantuml
@startuml
start

:获取 flyto_progress;

if (status == 'wayline_ok' 且\n上次状态 != 'wayline_ok') then (yes)
  :记录航点到达时间\nwaypoint_arrival_time = now;
  :打印: 🎯 航点X到达，开始 20s 上报窗口;
else (no)
endif

if (waypoint_arrival_time == None) then (yes)
  :跳过本次循环;
  stop
else (no)
endif

:计算时间差\nelapsed = now - waypoint_arrival_time;

if (elapsed > 20.0) then (yes)
  :清空到达时间\nwaypoint_arrival_time = None;
  :打印: ⏸️  上报窗口结束;
  stop
else (no)
endif

:从 MQTT 获取 GPS;
:lat, lon, _ = mqtt.get_position();

if (GPS 有效?) then (yes)
  :计算目标位置\ntarget_lat = lat + random(-0.0001, 0.0001)\ntarget_lon = lon + random(-0.0001, 0.0001);

  :计算目标 ID\ntarget_id = base_id + current_index;

  :加权随机选择类别\ntarget_cls = choices([0,1], weights=[0.1,0.9]);

  :生成 bbox\n(随机位置和大小);

  :构建目标对象\n{id, cls, gis, bbox, obj_img};

  :调用 IVAS API\nivas_client.report_targets(timestamp, [obj]);

  if (调试日志开启?) then (yes)
    :打印: [spuriou目标] [Callsign] GPS有效 | ID:X(车/人);
  else (no)
  endif

  :更新索引\ncurrent_index = (current_index + 1) % 10;
else (no)
  if (require_gps == True) then (yes)
    :跳过本次上报;
    stop
  else (no)
    :使用 (0, 0) 作为 GPS;
  endif
endif

stop

@enduml
```

## 🎲 目标类别分配

### 加权随机算法

```plantuml
@startuml
card "目标类别池" as pool {
    rectangle "0: 人 (10%)" as person #lightblue
    rectangle "1: 车 (90%)" as car #lightgreen
}

note right of pool
  使用 random.choices() 加权随机

  示例 10 次上报:
  - 车: 9 次 (90%)
  - 人: 1 次 (10%)

  实现:
  target_cls = random.choices(
      [0, 1],
      weights=[0.1, 0.9],
      k=1
  )[0]
end note

@enduml
```

## 🔢 ID 循环示例

### UAV 1 的 ID 循环轨迹

```plantuml
@startuml
state "ID Pool (10-19)" as pool {
    state "ID 10" as id10
    state "ID 11" as id11
    state "ID 12" as id12
    state "..." as dots
    state "ID 19" as id19

    [*] --> id10 : 初始索引 = 0
    id10 --> id11 : 索引 +1 (2秒后)
    id11 --> id12 : 索引 +1 (2秒后)
    id12 --> dots : 索引 +1
    dots --> id19 : 索引 = 9
    id19 --> id10 : 索引 = (9+1) % 10 = 0\n循环回到起点
}

note right of pool
  每 2 秒生成 1 个目标
  20 秒窗口 → 最多 10 个目标
  恰好完整循环一轮 ID 池
end note

@enduml
```

## 📈 性能和资源分配

### 上报频率计算

| 参数 | 值 | 说明 |
|------|-----|------|
| `report_hz` | 0.5 Hz | 每 2 秒上报 1 次 |
| `report_duration` | 20 秒 | 航点后上报窗口 |
| **单 UAV 最大目标数** | **10 个** | 20s ÷ 2s = 10 次上报 |
| **三 UAV 最大目标数** | **30 个** | 3 × 10 = 30 个并发目标 |

### 网络负载估算

```plantuml
@startuml
!define RECTANGLE class

rectangle "IVAS Server" as server {
    rectangle "HTTP Endpoint\n/api/targets" as endpoint
}

rectangle "UAV 1 Thread" as t1 {
    note bottom
      0.5 Hz × 1 目标/次
      = 0.5 req/s
    end note
}

rectangle "UAV 2 Thread" as t2 {
    note bottom
      0.5 Hz × 1 目标/次
      = 0.5 req/s
    end note
}

rectangle "UAV 3 Thread" as t3 {
    note bottom
      0.5 Hz × 1 目标/次
      = 0.5 req/s
    end note
}

t1 --> endpoint : POST (每 2s)
t2 --> endpoint : POST (每 2s)
t3 --> endpoint : POST (每 2s)

note right of server
  峰值负载:
  3 × 0.5 req/s = 1.5 req/s

  平均负载 (考虑窗口):
  假设 50% 时间在窗口内
  1.5 × 0.5 = 0.75 req/s
end note

@enduml
```

## 🐛 调试和监控

### 日志输出示例

```bash
# 启用调试日志（config.py）
IVAS_FAKE_TARGET['enable_debug_log'] = True

# 输出示例
[假目标] [Pilot 1] 启动 - ID 池: 10~19, 频率: 0.5Hz, 窗口模式: 开启
[假目标] [Pilot 1] 🎯 航点1到达，开始 20.0s 上报窗口
[假目标] [Pilot 1] GPS有效 | 基准GPS:(22.548123, 113.934567) | ID:10(车)
[假目标] [Pilot 1] GPS有效 | 基准GPS:(22.548234, 113.934678) | ID:11(车)
[假目标] [Pilot 1] GPS有效 | 基准GPS:(22.548345, 113.934789) | ID:12(人)
...
[假目标] [Pilot 1] ⏸️  上报窗口结束，等待下一个航点...

[假目标] [Pilot 2] 启动 - ID 池: 20~29, 频率: 0.5Hz, 窗口模式: 开启
[假目标] [Pilot 2] 🎯 航点1到达，开始 20.0s 上报窗口
[假目标] [Pilot 2] GPS有效 | 基准GPS:(22.549123, 113.935567) | ID:20(车)
...
```

### 状态检查点

```plantuml
@startuml
:启动 fake_target_reporter 线程;

partition "初始化检查点" {
  :打印: ID 池范围;
  :打印: 上报频率;
  :打印: 窗口模式状态;
}

partition "运行时检查点" {
  if (航点到达?) then (yes)
    :打印: 🎯 航点到达，开始窗口;
  endif

  if (GPS 有效?) then (yes)
    :打印: 基准 GPS 坐标;
    :打印: 目标 ID 和类别;
  else (no)
    :打印: ⚠️  GPS 无效;
  endif

  if (窗口超时?) then (yes)
    :打印: ⏸️  上报窗口结束;
  endif
}

partition "异常检查点" {
  if (上报失败?) then (yes)
    :打印: ✗ 上报失败 (不抛异常);
  endif
}

:线程结束;

@enduml
```

## 🔧 配置调优建议

### 场景 1：高频目标生成

```python
# 每秒生成 1 个目标，窗口延长到 30 秒
IVAS_FAKE_TARGET = {
    'report_hz': 1.0,          # 1 Hz
    'report_duration': 30.0,   # 30 秒窗口
    'max_targets_per_uav': 10, # 仍然 10 个 ID 循环
}

# 结果: 每架 UAV 30 秒生成 30 个目标，但只有 10 个唯一 ID
```

### 场景 2：低延迟上报

```python
# 每 0.5 秒生成 1 个目标
IVAS_FAKE_TARGET = {
    'report_hz': 2.0,          # 2 Hz
    'report_duration': 5.0,    # 5 秒快速窗口
    'max_targets_per_uav': 10,
}

# 结果: 5 秒内完成一轮 ID 循环
```

### 场景 3：人员检测为主

```python
# 调整类别权重
IVAS_FAKE_TARGET = {
    'target_class_weights': [0.7, 0.3],  # 70% 人，30% 车
}
```

## 📝 总结

### 关键特性

1. **完全并行**: 三架 UAV 独立运行，无资源竞争
2. **ID 隔离**: 每架 UAV 10 个唯一 ID，避免冲突
3. **时间窗口**: 仅在航点后上报，节省网络资源
4. **加权随机**: 90% 车辆 + 10% 人员，模拟真实场景
5. **GPS 跟随**: 目标围绕无人机当前位置生成

### 适用场景

- ✅ 多 UAV 巡航任务演示
- ✅ IVAS 系统压力测试
- ✅ 目标检测算法验证
- ✅ 航迹规划和任务调度测试

### 局限性

- ❌ 不支持真实目标检测
- ❌ 固定的 ID 池大小（10 个/UAV）
- ❌ 无持久化存储
- ❌ 需要 GPS 有效（除非 `require_gps=False`）

---

**最后更新**: 2025-11-14
**版本**: 1.0
**作者**: Claude Code
