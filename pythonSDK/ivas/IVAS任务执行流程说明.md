# IVAS 任务执行流程说明

本文档详细说明 IVAS 任务系统的执行流程、并行机制和每个任务类型的具体实现。

---

## 目录

- [核心执行流程](#核心执行流程)
- [并行执行机制](#并行执行机制)
- [任务类型详解](#任务类型详解)
  - [Mission 1: 起飞到10米](#mission-1-起飞到10米)
  - [Mission 2: 降落](#mission-2-降落)
  - [Mission 3: 一键返航](#mission-3-一键返航)
  - [Mission 4: 飞向指定点](#mission-4-飞向指定点)
  - [Mission 5/6/7: 轨迹任务](#mission-567-轨迹任务)
- [指令发送底层机制](#指令发送底层机制)
- [实际测试示例](#实际测试示例)
- [总结](#总结)
- [常见问题](#常见问题)
- [版本历史](#版本历史)

---

## 核心执行流程

### 1. 任务触发点

**位置**：`dashboard/ivas_adapter.py:188-252`

```python
def _execute_task_in_background(self, task_data: Dict[str, Any]):
    """
    在后台线程执行 IVAS 任务（新任务会中断旧任务）

    策略：
    - 如果有旧任务正在执行，立即停止它
    - 然后在后台线程执行新任务
    """
    # 检查是否具备执行条件
    if self.caller is None:
        self._add_log('warning', "任务执行器未初始化（缺少 ServiceCaller），跳过任务执行")
        return

    # ⚠️ 新机制：停止旧任务（如果存在）
    if self.current_runner and self.current_runner.running:
        self._add_log('info', "停止旧任务，准备执行新任务")
        self.current_runner.stop()  # 设置 running=False 并等待线程结束

    # 等待旧线程结束（最多等待2秒）
    if self.task_executor_thread and self.task_executor_thread.is_alive():
        self.task_executor_thread.join(timeout=2.0)
        if self.task_executor_thread.is_alive():
            self._add_log('warning', "旧任务线程未能及时停止，强制启动新任务")

    # 在后台线程执行新任务
    from djisdk.tasks.ivas_executor import execute_ivas_task
    from djisdk.tasks.runner import MissionRunner

    self._add_log('info', f"开始执行任务 {task_data.get('mission')}")

    # 🔥 创建新的 MissionRunner（用于可中断任务）
    self.current_runner = MissionRunner(
        self.mqtt,
        self.caller,
        self.heartbeat_thread,
        self.uav_config
    )

    def task_wrapper():
        """任务包装器：执行完成后清理 runner 引用"""
        try:
            execute_ivas_task(
                task_data,
                self.mqtt,
                self.caller,
                self.uav_config,
                self.heartbeat_thread,
                runner=self.current_runner  # 传递 runner 以支持任务中断
            )
        finally:
            self.current_runner = None  # 任务完成，清理引用

    self.task_executor_thread = threading.Thread(
        target=task_wrapper,
        daemon=True
    )
    self.task_executor_thread.start()
```

**触发时机**：当 `IVASAdapter._handle_ivas_log()` 接收到 `log_type='task'` 且有任务数据时自动调用。

**任务中断机制**：
- ✅ 新任务会立即中断旧任务（不再跳过）
- ✅ 使用 `MissionRunner.stop()` 安全停止任务
- ✅ 最多等待 2 秒让旧任务退出

### 2. 任务分发

**位置**：`djisdk/tasks/ivas_executor.py:27-76`

```python
def execute_ivas_task(
    task_data: Dict[str, Any],
    mqtt_client,
    caller,
    uav_config: Dict[str, str],
    heartbeat_thread: Optional[threading.Thread] = None
) -> None:
    """执行 IVAS 任务（同步执行，应在后台线程调用）"""

    mission = task_data.get('mission')
    target_id = task_data.get('id')
    callsign = uav_config.get('callsign', '未知')

    console.print(f"[bold cyan][{callsign}] 执行 IVAS 任务 {mission}[/bold cyan]")

    try:
        # 任务分发
        if mission == 1:
            _task_takeoff_10m(mqtt_client, caller, heartbeat_thread, callsign)
        elif mission == 2:
            _task_land(mqtt_client, callsign)
        elif mission == 3:
            _task_return_home(caller, callsign)
        elif mission == 4:
            lat = task_data.get('lat')
            lon = task_data.get('lon')
            alt = task_data.get('alt')
            _task_fly_to_point(caller, lat, lon, alt, callsign)
        elif mission in [5, 6, 7]:
            _task_trajectory(mqtt_client, caller, mission, uav_config, callsign)
        else:
            console.print(f"[red][{callsign}] 未知任务类型: {mission}[/red]")

        console.print(f"[bold green][{callsign}] 任务 {mission} 执行完成[/bold green]")

    except Exception as e:
        console.print(f"[bold red][{callsign}] 任务执行失败: {e}[/bold red]")
        raise
```

---

## 并行执行机制

### 关键设计

**核心原则**：每架无人机有**独立的 IVASAdapter 实例**，每个实例有**自己的后台线程**！

### 数据结构

**位置**：`dashboard/monitor.py`

```python
# 每架无人机独立的客户端
uav_clients = [
    {
        'id': '1',
        'mqtt': MQTTClient(sn='9N9CN2J0012CXY'),      # 1号机的MQTT
        'caller': ServiceCaller(...),                  # 1号机的Caller
        'ivas': IVASAdapter(device_code=1, ...)       # 1号机的Adapter（独立线程）
    },
    {
        'id': '2',
        'mqtt': MQTTClient(sn='9N9CN8400164WH'),      # 2号机的MQTT
        'caller': ServiceCaller(...),                  # 2号机的Caller
        'ivas': IVASAdapter(device_code=2, ...)       # 2号机的Adapter（独立线程）
    }
]
```

### 并行执行时间线

```
T0: keyboard发送 device_id=1, mission=5  →  Mock Server queue[1]
T1: keyboard发送 device_id=2, mission=6  →  Mock Server queue[2]

T2: IVASClient(device_code=1) 轮询  →  获取mission=5
    → IVASAdapter[0]._execute_task_in_background()
    → threading.Thread(target=execute_ivas_task, args=(...))  ✅ 1号机线程启动

T3: IVASClient(device_code=2) 轮询  →  获取mission=6
    → IVASAdapter[1]._execute_task_in_background()
    → threading.Thread(target=execute_ivas_task, args=(...))  ✅ 2号机线程启动

T4: ✅ 1号机在执行mission=5（飞轨迹1）
    ✅ 2号机在执行mission=6（飞轨迹2）
    两者并行运行！
```

### 为什么可以并行？

1. 每个 `IVASAdapter` 是独立对象
2. 每个对象有自己的 `task_executor_thread` 属性
3. `thread.is_alive()` 检查只影响**该无人机的线程**，不影响其他无人机
4. Python的 `threading` 模块由操作系统调度，自动实现并行

---

## 任务类型详解

### Mission 1: 起飞到10米

**函数**：`_task_takeoff_10m` (`djisdk/tasks/ivas_executor.py:79-94`)

**发送指令**：
```python
send_stick_control(mqtt, throttle=1024+300)  # 上拉油门
```

**执行流程**：

1. 创建起飞任务
   ```python
   takeoff_mission = create_takeoff_mission(
       target_height=10.0,      # 目标高度10米
       height_tolerance=0.5,    # 容错0.5米
       throttle_offset=300      # 油门偏移量
   )
   ```

2. 使用 `MissionRunner` 执行任务
   ```python
   runner = MissionRunner(mqtt, caller, heartbeat, {'callsign': callsign, 'sn': mqtt.gateway_sn})
   takeoff_mission(runner)
   ```

3. 内部循环控制：
   - 读取当前高度：`mqtt.get_relative_height()`
   - 如果 `高度 < 目标 - 0.5m`：发送上拉油门（`throttle=1024+300`）
   - 如果 `高度 >= 目标 - 0.5m`：发送悬停（`throttle=1024`）
   - 每 0.1 秒循环一次

4. 达到目标后返回

**实际发生**：无人机原地起飞到相对高度 10 米并悬停。

**典型日志输出**：
```
[cyan][Pilot 1] 开始起飞到10米...
[dim][Pilot 1] 当前高度: 2.34m, 目标: 10.00m
[dim][Pilot 1] 当前高度: 5.67m, 目标: 10.00m
[dim][Pilot 1] 当前高度: 9.82m, 目标: 10.00m
[green][Pilot 1] 起飞完成，当前高度: 10.12m
```

---

### Mission 2: 降落

**函数**：`_task_land` (`djisdk/tasks/ivas_executor.py:97-122`)

**发送指令**：
```python
send_stick_control(mqtt, throttle=694)  # 下拉油门（半杆）
```

**计算说明**：
- 中位值：`1024` (悬停)
- 半杆下拉：`1024 - 330 = 694`

**执行流程**：

1. 循环 500 次（最多 50 秒）
2. 每次循环：
   - 读取高度：`mqtt.get_relative_height()`
   - 如果 `高度 < 0.5m`：停止降落
   - 否则：发送 `throttle=694`（半杆下拉）
   - 等待 0.1 秒
   - 每秒打印一次当前高度

3. 降落完成后发送 10 次悬停指令（防止飘动）
   ```python
   for _ in range(10):
       send_stick_control(mqtt)  # 悬停 (throttle=1024)
       time.sleep(0.1)
   ```

**实际发生**：无人机缓慢降落到地面（半杆速度），高度 < 0.5 米时停止。

**典型日志输出**：
```
[cyan][Pilot 1] 开始降落...
[dim][Pilot 1] 当前高度: 9.87m
[dim][Pilot 1] 当前高度: 7.23m
[dim][Pilot 1] 当前高度: 4.56m
[dim][Pilot 1] 当前高度: 1.89m
[dim][Pilot 1] 当前高度: 0.34m
[green][Pilot 1] 已降落到地面
```

---

### Mission 3: 一键返航

**函数**：`_task_return_home` (`djisdk/tasks/ivas_executor.py:124-128`)

**发送指令**：
```python
return_home(caller)  # 调用 DJI 云端服务
```

**底层实现** (`djisdk/services/commands.py`):
```python
def return_home(caller: ServiceCaller) -> Dict[str, Any]:
    """一键返航"""
    return _call_service(
        caller,
        "flight_mode_switch_return_home",
        success_msg="返航指令已发送"
    )
```

**执行流程**：

1. 通过 MQTT 向 DJI 云端发送 `/services` 消息
2. 消息内容：
   ```json
   {
       "method": "flight_mode_switch_return_home",
       "data": {},
       "tid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   }
   ```
3. DJI 飞控自动执行返航算法：
   - 爬升到安全高度
   - 直线飞回 Home 点（起飞点）
   - 自动降落

**实际发生**：无人机自动返航到起飞点并降落（DJI 原生功能）。

**典型日志输出**：
```
[cyan][Pilot 1] 执行一键返航...
[green][Pilot 1] 返航指令已发送
```

---

### Mission 4: 飞向指定点

**函数**：`_task_fly_to_point` (`djisdk/tasks/ivas_executor.py:131-144`)

**发送指令**：
```python
fly_to_point(caller, latitude=lat, longitude=lon, height=alt, max_speed=12)
```

**底层实现** (`djisdk/services/commands.py`):
```python
def fly_to_point(caller, latitude, longitude, height, max_speed=12):
    """飞向指定GPS坐标"""
    return _call_service(
        caller,
        "flight_task_fly_to_point",
        {
            "target_latitude": latitude,
            "target_longitude": longitude,
            "target_height": height,
            "max_speed": max_speed
        }
    )
```

**执行流程**：

1. 通过 MQTT 向 DJI 云端发送飞行任务
2. DJI 飞控自动：
   - 规划路径（考虑避障）
   - 控制飞行速度（最大 12 m/s）
   - 到达目标点后悬停

**参数说明**：
- `latitude`: 目标纬度（度，WGS84）
- `longitude`: 目标经度（度，WGS84）
- `height`: 目标海拔高度（米，相对于起飞点）
- `max_speed`: 最大飞行速度（米/秒）

**实际发生**：无人机自动飞到指定 GPS 坐标（纬度/经度/海拔高度），最大速度 12 m/s。

**使用示例**（键盘输入）：
```
选择任务: 4
纬度 (latitude): 23.123456
经度 (longitude): 113.654321
高度 (altitude, 米): 50.0
```

**典型日志输出**：
```
[cyan][Pilot 1] 飞向目标点 (lat:23.123456, lon:113.654321, alt:50.0m)...
[green][Pilot 1] Fly-to 指令已发送 (ID: 12345)
```

---

### Mission 5/6/7: 轨迹任务

**函数**：`_task_trajectory` (`djisdk/tasks/ivas_executor.py:147-174`)

**任务映射**：
- Mission 5 → `Trajectory/uav1.json`
- Mission 6 → `Trajectory/uav2.json`
- Mission 7 → `Trajectory/uav3.json`

**发送指令**（循环）：
```python
fly_to_point(caller, lat=wp['lat'], lon=wp['lon'], height=flight_height, max_speed=speed)
```

**执行流程**：

1. **加载轨迹文件**
   ```python
   trajectory_file = f"Trajectory/uav{mission-4}.json"
   waypoints = load_trajectory(trajectory_file)
   ```

2. **解析航点列表**
   轨迹文件格式（示例）：
   ```json
   [
       {"x": 1.5, "y": 2.0},
       {"x": 3.0, "y": 4.5},
       {"x": -1.0, "y": 3.0}
   ]
   ```

3. **转换为 GPS 坐标**
   - `x`, `y` 是相对动捕原点的坐标（米）
   - 转换为绝对 GPS 坐标（纬度/经度）

4. **顺序执行每个航点**：
   ```python
   for waypoint in waypoints:
       fly_to_point(caller, lat=waypoint['lat'], lon=waypoint['lon'], height=flight_height)
       wait_until_arrived()  # 等待抵达（检查 GPS 距离 < 1 米）
   ```

**实际发生**：无人机按预设轨迹文件顺序飞行多个航点，完成复杂航线。

**典型日志输出**：
```
[cyan][Pilot 1] 执行轨迹任务: Trajectory/uav1.json...
[dim][Pilot 1] 已加载 8 个航点
[dim][Pilot 1] 飞向航点 1/8 (lat:23.123, lon:113.456, alt:20.0m)
[dim][Pilot 1] 已抵达航点 1/8
[dim][Pilot 1] 飞向航点 2/8 (lat:23.125, lon:113.458, alt:20.0m)
...
[green][Pilot 1] 轨迹任务执行完成
```

---

## 指令发送底层机制

所有指令最终通过两种方式发送：

### 1. 摇杆控制（实时控制）

**使用场景**：Mission 1（起飞）、Mission 2（降落）

**函数**：`send_stick_control` (`djisdk/services/commands.py`)

```python
def send_stick_control(mqtt_client, pitch=1024, roll=1024, yaw=1024, throttle=1024):
    """发送虚拟摇杆指令（实时控制）"""
    mqtt_client.client.publish(
        f"thing/product/{mqtt_client.gateway_sn}/drc/down",  # DRC话题
        json.dumps({
            "data": {
                "pitch": pitch,      # 俯仰（前后）：1024中位，>1024前进，<1024后退
                "roll": roll,        # 横滚（左右）：1024中位，>1024右移，<1024左移
                "yaw": yaw,          # 航向（旋转）：1024中位，>1024右转，<1024左转
                "throttle": throttle # 油门（上下）：1024中位，>1024上升，<1024下降
            },
            "method": "control_source"
        }),
        qos=0
    )
```

**摇杆值说明**：
- 中位值：`1024` (悬停/静止)
- 范围：`364 ~ 1684` (对应遥控器摇杆行程)
- 半杆偏移：`±330` (半行程)

**特点**：
- ✅ 实时控制，响应快速
- ⚠️ 需要持续发送（类似遥控器，松手停止）
- ⚠️ 需要手动实现闭环控制逻辑

---

### 2. 服务调用（任务指令）

**使用场景**：Mission 3（返航）、Mission 4（飞点）、Mission 5-7（轨迹）

**函数**：`ServiceCaller.call` (`djisdk/core/service_caller.py`)

```python
def call(self, method, data, timeout=10):
    """调用 DJI 云端服务（任务指令）"""
    tid = str(uuid4())

    # 发送请求
    self.mqtt.client.publish(
        f"thing/product/{self.mqtt.gateway_sn}/services",  # 服务话题
        json.dumps({
            "tid": tid,
            "bid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "method": method,  # 如 "flight_task_fly_to_point"
            "data": data,      # 如 {"target_latitude": 23.123, ...}
            "timestamp": int(time.time() * 1000)
        })
    )

    # 等待响应（通过 Future 对象）
    future = self.pending_requests[tid]
    return future.result(timeout=timeout)
```

**常用服务方法**：
- `flight_mode_switch_return_home` - 返航
- `flight_task_fly_to_point` - 飞向指定点
- `drc_mode_enter` - 进入DRC模式
- `cloud_control_auth_request` - 请求控制权

**特点**：
- ✅ 任务型指令，发送一次即可
- ✅ DJI 飞控自动执行（自带避障、路径规划）
- ✅ 有响应确认（同步等待结果）
- ⚠️ 延迟较高（需要云端处理）

---

## 实际测试示例

### 场景：多机并行任务

**目标**：1号机执行 Mission 5（轨迹1），2号机执行 Mission 6（轨迹2）

### 操作步骤

```bash
# Terminal 1: 启动 Mock Server
python ivas/task_mock_server.py

# Terminal 2: 启动 Dashboard（连接 Mock Server）
IVAS_BASE_URL=http://localhost:5001 python main.py

# Terminal 3: 发送任务指令
python ivas/keyboard_commander.py
```

### 键盘操作

```
==============================
    IVAS 任务菜单
==============================
按键  任务名称          任务类型
-------------------------------
 1    起飞10米         mission=1
 2    降落             mission=2
 3    返航             mission=3
 4    飞向指定点       mission=4 (需坐标)
 5    轨迹任务1        mission=5
 6    轨迹任务2        mission=6
 7    轨迹任务3        mission=7

 k    切换设备         当前: 设备 1
 s    查看统计         Mock Server 状态
 c    清空队列         清空所有任务
 q    退出             关闭程序
-------------------------------

当前控制设备: 1

选择任务 (输入按键): k
输入新的设备 ID (1-3): 2
✓ 已切换到设备 2

选择任务 (输入按键): 5
✓ 任务已推送到 Mock Server
设备 2 的 IVAS Client 将在下次轮询时接收此任务
```

### 执行时间线

```
[12:00:00] [Pilot 1] 收到任务: 轨迹任务1 (ID:1)
[12:00:00] [Pilot 1] 开始执行任务 5
[12:00:01] [Pilot 1] 执行轨迹任务: Trajectory/uav1.json...
[12:00:01] [Pilot 1] 已加载 8 个航点
[12:00:02] [Pilot 1] 飞向航点 1/8 (lat:23.123456, lon:113.654321, alt:20.0m)

[12:00:05] [Pilot 2] 收到任务: 轨迹任务2 (ID:2)  ← 同时进行！
[12:00:05] [Pilot 2] 开始执行任务 6
[12:00:06] [Pilot 2] 执行轨迹任务: Trajectory/uav2.json...
[12:00:06] [Pilot 2] 已加载 6 个航点
[12:00:07] [Pilot 2] 飞向航点 1/6 (lat:23.789012, lon:113.999888, alt:20.0m)

[12:00:15] [Pilot 1] 已抵达航点 1/8
[12:00:15] [Pilot 1] 飞向航点 2/8 (lat:23.125000, lon:113.656000, alt:20.0m)

[12:00:18] [Pilot 2] 已抵达航点 1/6
[12:00:18] [Pilot 2] 飞向航点 2/6 (lat:23.790000, lon:114.001000, alt:20.0m)

...

[12:05:30] [Pilot 1] 已抵达航点 8/8
[12:05:30] [Pilot 1] 轨迹任务执行完成

[12:04:50] [Pilot 2] 已抵达航点 6/6
[12:04:50] [Pilot 2] 轨迹任务执行完成
```

### 并行执行验证

**关键证明**：
1. ✅ 两架无人机的日志**交替出现**（时间戳混合）
2. ✅ 1号机任务未完成时，2号机已开始执行
3. ✅ 两个任务的完成时间**不同**（各自独立）

---

## 总结

### 核心要点

1. **触发点**：`dashboard/ivas_adapter.py:188-252` - `threading.Thread(target=task_wrapper).start()`

2. **并行机制**：
   - 每个无人机 → 独立的 `IVASAdapter` 实例
   - 每个实例 → 独立的 `task_executor_thread` 线程
   - 多个线程 → 操作系统自动调度并行执行

3. **任务中断**（v1.1 新增）：
   - 新任务会立即停止旧任务
   - 使用 `MissionRunner.stop()` 安全退出
   - 最多等待 2 秒让旧任务完成清理

4. **任务映射**：
   - **Mission 1**: 摇杆控制起飞（循环发送上拉油门）
   - **Mission 2**: 摇杆控制降落（循环发送下拉油门）
   - **Mission 3**: 服务调用返航（DJI自动返航）
   - **Mission 4**: 服务调用飞点（DJI自动飞到GPS坐标）
   - **Mission 5-7**: 服务调用序列（依次飞多个航点）

5. **指令类型**：
   - **摇杆控制**：实时、低延迟、需持续发送（Mission 1, 2）
   - **服务调用**：任务型、高级功能、一次发送（Mission 3, 4, 5-7）

6. **设备识别**（v1.1 简化）：
   - 统一使用 `deviceCode` query 参数
   - Mock Server 和真实 IVAS 使用相同机制
   - 配置文件中的 `device_code` 是唯一数据源

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Keyboard Commander                      │
│                   (Terminal 3 - 用户输入)                    │
└────────────┬────────────────────────────────┬────────────────┘
             │                                │
             │ HTTP POST                      │ HTTP POST
             │ device_id=1, mission=5         │ device_id=2, mission=6
             │                                │
             ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│                       Mock Server                            │
│                  (Terminal 1 - 任务队列)                     │
│         queue[1]: [mission=5]   queue[2]: [mission=6]       │
└────────────┬────────────────────────────────┬────────────────┘
             │                                │
             │ HTTP GET (polling)             │ HTTP GET (polling)
             │ device_id=1                    │ device_id=2
             │                                │
             ▼                                ▼
┌──────────────────────┐          ┌──────────────────────┐
│  IVASClient (code=1) │          │  IVASClient (code=2) │
│  (Dashboard Thread)  │          │  (Dashboard Thread)  │
└──────────┬───────────┘          └──────────┬───────────┘
           │                                 │
           │ task={'mission':5}              │ task={'mission':6}
           │                                 │
           ▼                                 ▼
┌──────────────────────┐          ┌──────────────────────┐
│ IVASAdapter[0]       │          │ IVASAdapter[1]       │
│ (UAV #1 Instance)    │          │ (UAV #2 Instance)    │
└──────────┬───────────┘          └──────────┬───────────┘
           │                                 │
           │ spawn thread                    │ spawn thread
           │                                 │
           ▼                                 ▼
┌──────────────────────┐          ┌──────────────────────┐
│ execute_ivas_task()  │          │ execute_ivas_task()  │
│ (Background Thread)  │          │ (Background Thread)  │
│ - 加载 uav1.json      │          │ - 加载 uav2.json      │
│ - 飞8个航点          │          │ - 飞6个航点          │
└──────────┬───────────┘          └──────────┬───────────┘
           │                                 │
           │ fly_to_point()                  │ fly_to_point()
           │                                 │
           ▼                                 ▼
┌──────────────────────┐          ┌──────────────────────┐
│ MQTTClient           │          │ MQTTClient           │
│ (SN: 9N9CN2J0012CXY) │          │ (SN: 9N9CN8400164WH) │
└──────────┬───────────┘          └──────────┬───────────┘
           │                                 │
           │ MQTT Publish                    │ MQTT Publish
           │                                 │
           ▼                                 ▼
      ┌─────────┐                      ┌─────────┐
      │  无人机1 │                      │  无人机2 │
      └─────────┘                      └─────────┘
```

### 关键文件索引

| 文件 | 行数范围 | 功能 |
|------|---------|------|
| `dashboard/ivas_adapter.py` | 188-252 | 任务触发（后台线程启动 + 任务中断） |
| `djisdk/tasks/ivas_executor.py` | 27-76 | 任务分发（mission映射） |
| `djisdk/tasks/ivas_executor.py` | 79-94 | Mission 1 实现 |
| `djisdk/tasks/ivas_executor.py` | 97-122 | Mission 2 实现 |
| `djisdk/tasks/ivas_executor.py` | 124-128 | Mission 3 实现 |
| `djisdk/tasks/ivas_executor.py` | 131-144 | Mission 4 实现 |
| `djisdk/tasks/ivas_executor.py` | 147-174 | Mission 5-7 实现 |
| `djisdk/services/commands.py` | - | 底层指令实现 |
| `djisdk/tasks/runner.py` | - | MissionRunner（可中断任务执行器） |
| `ivas/client.py` | 283-290 | 任务轮询（传递 deviceCode） |
| `ivas/task_mock_server.py` | 67-86 | Mock Server 任务分发 |
| `dashboard/monitor.py` | 149-193 | IVAS Adapter 初始化 |

---

## 常见问题

### Q1: 任务执行中如何处理新任务？

**A**: 支持**新任务中断旧任务**机制（v1.1 新增）。

**行为**：
- ✅ 收到新任务时，立即停止旧任务
- ✅ 使用 `MissionRunner.stop()` 安全退出（设置 `running=False`）
- ✅ 最多等待 2 秒让旧任务完成清理
- ⚠️ 如果旧任务 2 秒内未退出，强制启动新任务

**实现位置**：`dashboard/ivas_adapter.py:188-214`

```python
# 停止旧任务（如果存在）
if self.current_runner and self.current_runner.running:
    self._add_log('info', "停止旧任务，准备执行新任务")
    self.current_runner.stop()

# 等待旧线程结束（最多等待2秒）
if self.task_executor_thread and self.task_executor_thread.is_alive():
    self.task_executor_thread.join(timeout=2.0)
```

**适用场景**：
- 紧急停止当前任务（如发现障碍物，立即返航）
- 任务优先级调整（如轨迹任务中途改为降落）

**注意事项**：
- 旧任务的 `MissionRunner` 会收到 `running=False` 信号
- 任务内部循环应定期检查 `runner.running` 并在为 `False` 时退出

### Q2: 如何区分不同无人机的任务？

**A**: 通过 `device_code` 和数组索引绑定：
- Mock Server 的 `device_id=1` → 对应 `UAV_CONFIGS[0]`（1号机）
- Mock Server 的 `device_id=2` → 对应 `UAV_CONFIGS[1]`（2号机）

### Q3: Mission 5/6/7 的轨迹文件格式是什么？

**A**: JSON格式，包含动捕坐标的航点列表：
```json
[
    {"x": 1.5, "y": 2.0},
    {"x": 3.0, "y": 4.5}
]
```
其中 `x`, `y` 是相对动捕原点的米制坐标，会被转换为 GPS 坐标。

### Q4: 如何添加新的任务类型？

**A**: 修改 `djisdk/tasks/ivas_executor.py`：
1. 添加新的 `_task_xxx()` 函数
2. 在 `execute_ivas_task()` 的 `if-elif` 中添加分支
3. 在键盘控制器中添加对应的菜单选项

### Q5: Mock Server 和真实 IVAS 如何识别设备？

**A**: 两者使用**相同的设备识别机制**（v1.1 简化）。

#### 统一的设备识别方式

**客户端**（`ivas/client.py:283-290`）：
```python
def _poll_task(self):
    """从 IVAS 服务器轮询任务 (GET)"""
    url = f"{self.base_url}/jk-ivas/third/controller/outdoorTask"

    # 传递 deviceCode 参数（来自 UAV_CONFIGS 中的 ivas.device_code）
    params = {'deviceCode': self.device_code}
    resp = self._request('GET', url, params=params)
```

**Mock Server**（`ivas/task_mock_server.py:67-86`）：
```python
@app.route('/jk-ivas/third/controller/outdoorTask', methods=['GET'])
def get_outdoor_task():
    # 直接从 query 参数获取 deviceCode
    device_id = request.args.get('deviceCode', type=int)

    if not device_id:
        return jsonify({'code': 400, 'msg': '缺少 deviceCode 参数', 'data': None}), 400

    # 返回该设备的任务队列
    if device_id in task_queues and task_queues[device_id]:
        task = task_queues[device_id].popleft()
        return jsonify({'code': 200, 'data': task})
```

**真实 IVAS 服务器**：
- 也应接受 `deviceCode` query 参数
- 根据 `deviceCode` 返回对应设备的任务
- 仍然需要 token 验证（HTTP Header）

#### 配置映射关系

**配置文件**（`dashboard/config.py`）：
```python
UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',
        'ivas': {
            'device_code': 1,        # ← 对应 Mock Server queue[1]
            'account': 'ZSDX001',
            'password': '000000'
        }
    },
    {
        'sn': '9N9CN8400164WH',
        'ivas': {
            'device_code': 2,        # ← 对应 Mock Server queue[2]
            'account': 'ZSDX002',
            'password': '000000'
        }
    }
]
```

#### Token 认证差异

**测试环境（Mock Server）**：
- ✅ 需要登录获取 token（模拟认证流程）
- ⚠️ 不验证 token 内容（简化测试）
- ✅ 直接使用 `deviceCode` 参数识别设备

**生产环境（真实 IVAS 服务器）**：
- ✅ 必须登录获取有效 token
- ✅ 每个请求验证 token 有效性
- ✅ 使用 `deviceCode` 参数识别设备
- ⚠️ Token 过期自动重新登录（`client.py:238-246`）

#### 环境切换

```bash
# 测试模式（Mock Server）
IVAS_BASE_URL=http://localhost:5001 python main.py

# 生产模式（真实 IVAS 服务器）
python main.py  # 使用配置文件中的默认地址
```

#### 关键改进（v1.1）

**简化前**（已废弃）：
- ❌ Mock Server 支持 3 种识别方式（deviceCode / device_id / token 解析）
- ❌ 客户端和服务器行为不一致
- ❌ 过度设计，复杂度高

**简化后**（当前版本）：
- ✅ 统一使用 `deviceCode` query 参数
- ✅ 客户端和 Mock Server 行为完全一致
- ✅ 真实 IVAS 服务器也应遵循相同规范
- ✅ 配置文件中的 `device_code` 是唯一数据源

---

**文档版本**: v1.1
**最后更新**: 2025-01-11
**维护者**: Volition-DJI Team

## 版本历史

### v1.1 (2025-01-11)
- ✅ 新增任务中断机制（新任务会停止旧任务）
- ✅ 简化设备识别逻辑（统一使用 `deviceCode` 参数）
- ✅ 移除 Mock Server 的多重识别方式
- ✅ 更新 Q1 和 Q5 常见问题说明

### v1.0 (2025-01-10)
- 初始版本：完整的任务执行流程说明
