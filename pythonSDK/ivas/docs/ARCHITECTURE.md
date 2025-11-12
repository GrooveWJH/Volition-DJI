# IVAS 系统架构文档

本文档详细说明 IVAS (Intelligent Video Analysis System) 任务系统的完整架构，包括开发测试环境（Mock Server）和生产环境的关系。

## 目录

- [系统概览](#系统概览)
- [核心组件](#核心组件)
- [数据流图](#数据流图)
- [开发测试环境 vs 生产环境](#开发测试环境-vs-生产环境)
- [任务执行流程](#任务执行流程)
- [配置说明](#配置说明)

---

## 系统概览

IVAS 系统是一个分布式无人机任务调度系统，支持远程控制多架无人机执行各种任务（起飞、降落、航点飞行等）。

### 架构图

```plantuml
@startuml IVAS System Architecture

skinparam packageStyle rectangle
skinparam componentStyle rectangle

' 定义颜色
skinparam component {
    BackgroundColor<<dashboard>> LightBlue
    BackgroundColor<<ivas>> LightGreen
    BackgroundColor<<dji>> LightYellow
    BackgroundColor<<mock>> Pink
    BackgroundColor<<production>> LightCoral
}

' Dashboard 层
package "Dashboard (监控界面)" <<dashboard>> {
    component [Monitor\n主监控程序] as Monitor
    component [IVASAdapter\n适配器] as Adapter
    component [UAV State\n状态管理] as State
}

' IVAS 客户端层
package "IVAS Client" <<ivas>> {
    component [IVASClient\n任务客户端] as Client
    component [Task Executor\n任务执行器] as Executor
}

' 任务执行层
package "DJI SDK" <<dji>> {
    component [MQTT Client\n通信客户端] as MQTT
    component [Service Caller\nRPC调用器] as Caller
    component [Task Modules\n任务模块] as Tasks
}

' 测试环境
package "测试环境 (本地)" <<mock>> {
    component [Mock Server\n模拟服务器] as MockServer
    component [Keyboard Commander\n键盘控制器] as Commander
    database "Task Queues\n任务队列" as Queue
}

' 生产环境
package "生产环境 (实际部署)" <<production>> {
    component [Real IVAS Server\n真实IVAS服务器] as RealServer
    component [C2 System\n指挥控制系统] as C2
    database "Mission DB\n任务数据库" as DB
}

' 无人机
cloud "DJI 无人机" as Drone {
    component [Mavic 3E\nUAV Hardware] as UAV
}

' 数据流 - Dashboard 内部
Monitor --> Adapter : 初始化\nIVAS功能
Monitor --> State : 状态更新
Adapter --> Client : 创建并管理

' 数据流 - IVAS Client
Client --> Executor : 收到任务后\n调用执行
Executor --> Tasks : 分发任务

' 数据流 - DJI SDK
Tasks --> Caller : 调用服务
Caller --> MQTT : 发送指令
MQTT --> Drone : MQTT\n协议

' 测试环境数据流
Commander ..> MockServer : HTTP POST\n推送任务
MockServer --> Queue : 存储任务
Client ..> MockServer : HTTP GET\n轮询任务\n(每0.5秒)

' 生产环境数据流
C2 ..> RealServer : HTTP POST\n下发任务
RealServer --> DB : 存储任务
Client ..> RealServer : HTTP GET\n轮询任务\n(每0.5秒)

' 配置切换
note right of Client
  通过环境变量切换:
  IVAS_BASE_URL
  - 测试: localhost:5001
  - 生产: 192.168.31.38:8888
end note

note bottom of MockServer
  本地测试工具
  - 无需真实IVAS服务器
  - 快速验证功能
  - 支持任务广播
end note

note bottom of RealServer
  实际生产系统
  - 与指挥控制系统集成
  - 任务持久化存储
  - 多用户权限管理
end note

@enduml
```

---

## 核心组件

### 1. Dashboard (监控界面)

**职责**: 实时监控无人机状态，集成 IVAS 任务接收功能

**关键模块**:
- `monitor.py`: 主监控循环，初始化 IVAS Adapter
- `ivas_adapter.py`: 对接 DJI MQTT 数据和 IVAS 服务器
- `state.py`: UAV 状态数据模型，统一管理所有数据源

**配置文件**: `dashboard/config.py`
```python
IVAS_FEATURES = {
    'position_report': False,  # 位置上报
    'target_report': False,    # 目标检测上报
    'task_receive': True,      # 任务接收（核心功能）
}

IVAS_SERVER = {
    'base_url': 'http://192.168.31.38:8888',  # 可通过环境变量覆盖
    'task_hz': 2.0,  # 轮询频率 (每0.5秒)
}
```

---

### 2. IVAS Client (任务客户端)

**职责**: 轮询 IVAS 服务器，接收任务并执行

**关键模块**:
- `ivas/client.py`:
  - 登录认证
  - 周期性轮询任务 (`/outdoorTask`)
  - 位置上报 (`/postWgsPos` - 可选)
  - 目标检测上报 (`/postTarPos` - 可选)

**执行流程**:
```python
# ivas/client.py:run()
while self.running:
    if self.features.get('task_receive', True):
        now = time.time()
        if now - self.last_task_time >= self.task_interval:
            self._poll_task()  # 轮询任务
            self.last_task_time = now
```

---

### 3. Task Executor (任务执行器)

**职责**: 将 IVAS 任务映射到 DJI SDK 操作

**任务类型映射** (`djisdk/tasks/ivas_executor.py`):
```python
TASK_MAPPING = {
    1: "起飞到预设高度",      # 从 uav_config['flight_height'] 读取
    2: "降落",                # 持续最小油门直到飞行模式=待机
    3: "返航",                # 一键返航
    4: "飞向指定点",          # 需要 lat/lon/alt
    5-7: "执行预设轨迹任务",  # Trajectory/uav1-3.json
}
```

**任务中断机制**:
- 新任务会自动停止旧任务
- 通过 `runner.running` 标志实现
- 最多等待 2 秒旧任务结束

---

### 4. Mock Server (测试服务器)

**职责**: 本地模拟真实 IVAS 服务器，用于开发测试

**关键特性**:
- 模拟所有 IVAS HTTP 接口
- 独立任务队列（每个设备一个队列）
- 支持 id=99 广播功能
- 无需数据库，内存存储

**接口实现** (`ivas/task_mock_server.py`):
```python
# 登录接口
POST /jk-ivas/third/controller/zsLogin
→ 返回 mock-token

# 任务轮询接口
GET /jk-ivas/third/controller/outdoorTask
→ 从队列弹出任务，无任务返回 None

# 测试接口 - 推送任务
POST /mock/push_task
→ 推送任务到指定设备队列

# 测试接口 - 查看统计
GET /mock/stats
→ 返回任务推送/拉取统计

# 测试接口 - 清空队列
POST /mock/clear
→ 清空所有任务队列
```

---

### 5. Keyboard Commander (键盘控制器)

**职责**: 通过键盘发送任务指令到 Mock Server

**功能**:
- 交互式菜单选择任务
- 支持单机控制 (device_id: 1-3)
- 支持广播控制 (device_id: 99)
- 查看服务器统计信息

**使用方法**:
```bash
# 1. 启动 Mock Server
python ivas/task_mock_server.py

# 2. 启动 Keyboard Commander
python ivas/keyboard_commander.py

# 3. 选择任务
- 按 1: 起飞到预设高度
- 按 2: 降落
- 按 k: 切换设备 (1-3 单机, 99 广播)
- 按 s: 查看统计
```

---

## 数据流图

### 任务下发流程

```plantuml
@startuml Task Dispatch Flow

skinparam sequenceMessageAlign center

actor User as "操作员"
participant Commander as "Keyboard\nCommander"
participant MockServer as "Mock\nServer"
database Queue as "Task\nQueue"
participant Client as "IVAS\nClient"
participant Adapter as "IVAS\nAdapter"
participant Executor as "Task\nExecutor"
participant UAV as "无人机"

User -> Commander: 1. 选择任务\n(按键 1-7)
Commander -> Commander: 2. 构建任务数据\n{'mission': 1, 'id': 99}

alt 广播模式 (id=99)
    Commander -> MockServer: POST /mock/push_task\n(id=99)
    MockServer -> Queue: 广播到设备 1,2,3
    MockServer --> Commander: 返回广播确认
else 单机模式 (id=1-3)
    Commander -> MockServer: POST /mock/push_task\n(id=1)
    MockServer -> Queue: 推送到设备队列
    MockServer --> Commander: 返回成功
end

loop 每 0.5 秒轮询
    Client -> MockServer: GET /outdoorTask\n(token认证)
    MockServer -> Queue: 从队列弹出任务
    alt 有任务
        MockServer --> Client: 返回任务数据
        Client -> Adapter: 回调 _handle_ivas_log
        Adapter -> Adapter: 存储任务\n添加日志
        Adapter -> Executor: 启动后台线程执行

        alt 检查旧任务
            Executor -> Executor: 停止旧任务\n(runner.stop())
        end

        Executor -> UAV: 执行无人机操作\n(起飞/降落/航点)
        UAV --> Executor: 操作完成
        Executor --> Adapter: 任务完成
        Adapter -> Adapter: 清理 runner 引用
    else 无任务
        MockServer --> Client: 返回 None
    end
end

@enduml
```

---

### 任务执行状态机

```plantuml
@startuml Task Execution State Machine

skinparam state {
    BackgroundColor<<active>> LightGreen
    BackgroundColor<<blocked>> Yellow
    BackgroundColor<<error>> LightCoral
}

[*] --> Idle : Dashboard 启动

Idle --> TaskReceived : IVAS Client\n轮询到任务
TaskReceived --> CheckingOldTask : Adapter\n收到任务

state CheckingOldTask <<active>> {
    [*] --> OldTaskRunning : 检查旧任务
    OldTaskRunning --> StoppingOldTask : 旧任务存在
    StoppingOldTask --> WaitingStop : runner.stop()
    WaitingStop --> ReadyToExecute : 旧任务停止\n(最多2秒)

    OldTaskRunning --> ReadyToExecute : 无旧任务

    WaitingStop --> ForceStart : 超时
    ForceStart --> ReadyToExecute : 强制启动
}

ReadyToExecute --> Executing : 创建新 runner\n启动后台线程

state Executing <<active>> {
    [*] --> Takeoff : mission=1
    [*] --> Land : mission=2
    [*] --> ReturnHome : mission=3
    [*] --> FlyToPoint : mission=4
    [*] --> Trajectory : mission=5-7

    Takeoff --> [*] : 到达高度
    Land --> [*] : 飞行模式=待机
    ReturnHome --> [*] : 指令已发送
    FlyToPoint --> [*] : 指令已发送
    Trajectory --> [*] : 所有航点完成
}

Executing --> TaskCompleted : 正常完成
Executing --> TaskFailed : 执行异常

TaskCompleted --> Idle : 清理资源
TaskFailed --> Idle : 清理资源

Executing --> Interrupted : 收到新任务
Interrupted --> CheckingOldTask : 中断当前任务

note right of CheckingOldTask
  任务中断机制:
  - runner.running = False
  - 阻塞循环立即退出
  - 最多等待 2 秒
end note

@enduml
```

---

## 开发测试环境 vs 生产环境

### 对比表

| 特性 | Mock Server (测试) | Real IVAS Server (生产) |
|------|-------------------|------------------------|
| **部署位置** | 本地 (localhost:5001) | 远程服务器 (192.168.31.38:8888) |
| **数据持久化** | 内存存储，重启丢失 | 数据库存储，永久保存 |
| **用户认证** | 假 token，不验证密码 | 真实 token，严格认证 |
| **任务来源** | Keyboard Commander | C2 指挥控制系统 |
| **任务队列** | defaultdict(deque) | 数据库表 |
| **广播功能** | 支持 (id=99) | 取决于实际实现 |
| **统计接口** | `/mock/stats` | 取决于实际实现 |
| **清空队列** | `/mock/clear` | 不支持（安全考虑） |
| **日志记录** | Rich 控制台输出 | 结构化日志系统 |
| **高可用性** | 单进程，无容错 | 负载均衡，故障转移 |

---

### 环境切换

**方法1: 环境变量**
```bash
# 测试环境
IVAS_BASE_URL=http://localhost:5001 python dashboard/monitor.py

# 生产环境（默认）
python dashboard/monitor.py
```

**方法2: 修改配置文件**
```python
# dashboard/config.py
IVAS_SERVER = {
    'base_url': os.getenv('IVAS_BASE_URL', 'http://192.168.31.38:8888'),
}
```

---

### Mock Server 使用场景

**✅ 适用场景**:
1. **本地开发**: 无需连接真实 IVAS 服务器
2. **功能测试**: 快速验证任务执行逻辑
3. **集成测试**: 测试 Dashboard ↔ IVAS ↔ DJI SDK 完整链路
4. **演示展示**: 无网络环境下演示系统功能
5. **压力测试**: 批量推送任务测试并发处理能力

**❌ 不适用场景**:
1. **生产部署**: 无数据持久化，不可靠
2. **多用户系统**: 无权限管理
3. **长时间运行**: 内存泄漏风险

---

## 任务执行流程

### 完整时序图

```plantuml
@startuml Complete Task Execution Sequence

skinparam sequenceMessageAlign center
autonumber

actor User as "操作员"
participant Commander as "Keyboard\nCommander"
participant MockServer as "Mock\nServer"
participant Client as "IVAS\nClient"
participant Adapter as "IVAS\nAdapter"
participant Executor as "Task\nExecutor"
participant Tasks as "DJI\nTask Modules"
participant MQTT as "MQTT\nClient"
participant UAV as "无人机"

== 任务下发阶段 ==

User -> Commander: 选择任务 (按 1)
Commander -> MockServer: POST /mock/push_task\n{'mission': 1, 'id': 99}
MockServer -> MockServer: 广播到设备 1,2,3
MockServer --> Commander: 返回成功

== 任务接收阶段 ==

loop 每 0.5 秒
    Client -> MockServer: GET /outdoorTask\n(token: mock-token-ZSDX001)
    MockServer --> Client: {'mission': 1, 'id': 99}
    Client -> Adapter: _handle_ivas_log('task', data)
    Adapter -> Adapter: 存储到 latest_task
    Adapter -> Adapter: 添加日志: "收到任务: 起飞到预设高度"
end

== 任务执行阶段 ==

Adapter -> Executor: _execute_task_in_background(task_data)

alt 检查旧任务
    Executor -> Executor: current_runner.stop()
    note right: runner.running = False
    Executor -> Executor: 等待旧线程结束 (最多2秒)
end

Executor -> Executor: 创建新 runner\n(包含 mqtt, caller, heartbeat)
Executor -> Tasks: execute_ivas_task(task_data, ..., runner)

Tasks -> Tasks: 分发任务: mission=1
Tasks -> Tasks: _task_takeoff(mqtt, caller, heartbeat, uav_config, runner)

Tasks -> Tasks: 读取配置:\ntarget_height = uav_config['flight_height']\n(UAV1: 90m, UAV2: 100m, UAV3: 110m)

Tasks -> Tasks: create_takeoff_mission(\ntarget_height=90.0,\nthrottle_offset=660)

Tasks -> Tasks: runner.running = True

loop 上升阶段
    Tasks -> MQTT: send_stick_control(throttle=1024+660)
    MQTT -> UAV: 发送油门指令
    UAV --> MQTT: 返回高度数据
    MQTT --> Tasks: current_height = 45.2m

    alt 到达目标高度
        Tasks -> Tasks: current_height >= target_height\n退出循环
    end

    alt 收到新任务
        Executor -> Tasks: runner.running = False\n(通过 runner.stop())
        Tasks -> Tasks: 检测到 runner.running=False\n立即退出循环
    end
end

Tasks -> MQTT: send_stick_control() × 50次\n(悬停5秒)
MQTT -> UAV: 发送悬停指令

Tasks --> Executor: 任务完成
Executor -> Executor: 清理 current_runner 引用
Executor --> Adapter: 线程结束
Adapter -> Adapter: 添加日志: "任务执行完成"

@enduml
```

---

## 配置说明

### UAV 配置 (`dashboard/config.py`)

```python
UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',          # 无人机序列号
        'user_id': 'pilot_1',            # 用户标识（显示用）
        'callsign': 'Pilot 1',           # 呼号
        'flight_height': 90.0,           # 起飞和航点飞行高度（米）
        'vrpn_device': 'Drone001@...',   # 动捕设备
        'ivas': {
            'device_code': 1,            # IVAS 设备编号
            'account': 'ZSDX001',        # IVAS 账号
            'password': '000000'         # IVAS 密码
        }
    },
    # ... UAV2, UAV3 配置类似，flight_height 分别为 100.0, 110.0
]
```

### IVAS 功能开关

```python
IVAS_FEATURES = {
    'position_report': False,  # 无人机位置上报（实时）
    'target_report': False,    # 目标检测上报（依赖视觉算法）
    'task_receive': True,      # 任务接收（核心功能，必须开启）
}
```

### 高度配置说明

**统一原则**: 每架无人机的 `flight_height` 同时控制：
1. **起飞高度**: 任务1执行时的目标高度
2. **航点飞行高度**: 任务5-7执行轨迹时的飞行高度

**当前配置**:
- UAV1 (Pilot 1): 90 米
- UAV2 (Pilot 2): 100 米
- UAV3 (Pilot 3): 110 米

**修改方法**:
```python
# dashboard/config.py:28
'flight_height': 120.0,  # 修改为所需高度
```

---

## 总结

### 系统特点

✅ **优点**:
- **模块化设计**: Dashboard、IVAS Client、Task Executor 职责清晰
- **可测试性强**: Mock Server 支持本地完整测试
- **任务中断机制**: 新任务自动停止旧任务
- **灵活配置**: 每架无人机独立高度配置
- **环境隔离**: 测试/生产环境轻松切换

⚠️ **注意事项**:
- Mock Server 仅用于开发测试，不可用于生产
- 任务轮询频率 (2Hz) 影响任务响应延迟 (~0.5秒)
- 广播功能 (id=99) 仅支持任务 1/2/3（起飞/降落/返航）
- 任务执行过程中，Dashboard 日志可能存在 0.5-1 秒显示延迟

---

## 相关文档

- [IVAS 任务执行流程说明](./IVAS任务执行流程说明.md) - 详细任务执行步骤
- [接口文档v4](./接口文档v4.md) - IVAS HTTP 接口规范
- [README](./README.md) - IVAS Client 使用指南

---

**文档版本**: v1.0
**最后更新**: 2025-01-10
**维护者**: System Architecture Team
