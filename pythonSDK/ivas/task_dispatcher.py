"""
IVAS 任务分发模块 - 任务控制功能

包含任务轮询、分发、执行的所有逻辑：
- task_poller: 户外系统的任务轮询和分发
- task_mqtt_forwarder: 室内系统的任务轮询和MQTT转发
- _distribute_broadcast: 广播任务分发
- _execute_task: 单个任务执行
- _clear_mission_state: 任务状态清除（新增）

所有函数都是纯函数，无状态依赖。
"""

import time
import threading
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

from .reporters import fake_target_reporter

# ========== 任务状态管理 ==========

# Mission state file path (与 djisdk/tasks/trajectory.py 保持一致)
MISSION_STATE_FILE = Path('/tmp/djisdk_mission_state.json')


def _clear_mission_state(callsign: str):
    """
    清除指定无人机的任务状态（不影响其他无人机）

    Args:
        callsign: 无人机呼号（如 'Pilot 1', 'Pilot 2'）

    Note:
        - 使用原子写入（temp file + rename）防止部分读取
        - 静默失败（写入失败不影响任务执行）
        - 只删除指定callsign，保留其他UAV数据
        - 与 djisdk/tasks/trajectory.py 使用相同的原子写入机制
    """
    try:
        if not MISSION_STATE_FILE.exists():
            return

        # 1. 读取整个文件（保留其他无人机数据）
        with open(MISSION_STATE_FILE, 'r') as f:
            mission_state = json.load(f)

        # 2. 只删除指定 callsign
        if callsign in mission_state:
            del mission_state[callsign]

        # 3. 原子写入（与 trajectory.py 相同机制）
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir='/tmp', prefix='djisdk_mission_') as tmp_file:
            json.dump(mission_state, tmp_file, indent=2)
            tmp_path = tmp_file.name

        shutil.move(tmp_path, MISSION_STATE_FILE)

    except Exception:
        pass  # 静默失败，不影响飞行任务


# ========== 任务分发控制 ==========


def task_poller(
    ivas_client,
    uav_clients_map: Dict[int, Any],
    interval: float,
    stop_event: threading.Event,
    enable_task_execution: bool = True
):
    """
    任务轮询和分发线程（纯函数）

    单点轮询 IVAS 服务器的任务队列，根据任务 ID 路由分发。

    核心功能（保留 TaskDistributor 的逻辑）：
    - 单点轮询（避免任务被重复消费）
    - 智能路由（id=99 广播，id=1/2/3 单播）
    - 任务去重（避免重复执行）

    Args:
        ivas_client: IVAS HTTP 客户端
        uav_clients_map: 设备映射 {device_code: uav_client_dict}
        interval: 轮询间隔（秒）
        stop_event: 停止事件
        enable_task_execution: 是否执行任务分发（False时仅监视，不执行）
    """
    next_tick = time.perf_counter()
    executed_tasks = set()  # 任务去重集合

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 轮询任务
            result = ivas_client.poll_task()

            if result:
                # 打印任务分隔符
                print("\n" + "="*60)
                print(f"[任务] 🎯 接收到新任务 (时间: {time.strftime('%H:%M:%S')})")
                print("="*60)

                task_data = result['data']
                target_id = task_data.get('id', 0)
                mission = task_data.get('mission', 0)

                # 检查是否启用任务执行
                if not enable_task_execution:
                    print(
                        f"[任务] 👁️ 监视模式：任务已接收但不执行 (ID:{target_id}, mission={mission})")
                    print("="*60 + "\n")
                    next_tick += interval
                    continue

                # 路由分发
                if target_id == 99:
                    # 广播模式：分发给所有设备
                    _distribute_broadcast(
                        task_data, uav_clients_map, executed_tasks)
                elif target_id in uav_clients_map:
                    # 单播模式：分发给指定设备
                    print(f"[任务] 路由到设备 {target_id} (mission={mission})")
                    uav = uav_clients_map[target_id]
                    _execute_task(uav, task_data)
                else:
                    print(f"[任务] ⚠️ 未知任务 ID: {target_id} (mission={mission})")

                # 任务处理完成后打印分隔符
                print("="*60 + "\n")

            next_tick += interval

        # 精确睡眠
        time.sleep(0.001)


def _distribute_broadcast(
    task_data: Dict[str, Any],
    uav_clients_map: Dict[int, Any],
    executed_tasks: set
):
    """
    广播分发（纯函数）

    将任务广播到所有设备，带任务去重和类型验证。

    Args:
        task_data: IVAS 任务数据
        uav_clients_map: 设备映射
        executed_tasks: 已执行任务集合（用于去重）
    """
    mission = task_data.get('mission', 0)
    mission_names = {1: "起飞", 2: "降落", 3: "返航"}

    # 1. 类型验证：只有 1/2/3 支持广播
    if mission not in [1, 2, 3]:
        print(f"[任务] ❌ 任务 {mission} 不支持广播，仅支持起飞/降落/返航")
        return

    # 2. 任务去重（使用 mission+timestamp 作为唯一标识）
    task_signature = f"{mission}_{task_data.get('timestamp', int(time.time()))}"

    if task_signature in executed_tasks:
        print(f"[任务] ⏭️ 任务 {task_signature} 已执行过，跳过")
        return

    executed_tasks.add(task_signature)

    # 清理旧记录（保留最近 100 条）
    if len(executed_tasks) > 100:
        old_tasks = list(executed_tasks)[:50]
        for old_task in old_tasks:
            executed_tasks.discard(old_task)

    # 3. 广播分发
    mission_name = mission_names.get(mission, f"任务{mission}")
    print(f"[任务] 📢 广播: {mission_name} (ID:99) → {len(uav_clients_map)} 个设备")

    success_count = 0
    for device_code, uav in uav_clients_map.items():
        try:
            _execute_task(uav, task_data)
            success_count += 1
            print(f"[任务]   ✓ 设备 {device_code} 已接收")
        except Exception as e:
            print(f"[任务]   ✗ 设备 {device_code} 失败: {e}")

    print(f"[任务] ✅ 广播完成: {success_count}/{len(uav_clients_map)} 个设备成功")


def _execute_task(uav_client: Dict[str, Any], task_data: Dict[str, Any]):
    """
    执行任务（纯函数）

    调用 djisdk 的 ivas_executor 执行任务。

    Args:
        uav_client: UAV 客户端字典（包含 mqtt, caller, heartbeat 等）
        task_data: IVAS 任务数据
    """
    from djisdk.tasks.ivas_executor import execute_ivas_task
    from djisdk.tasks.runner import MissionRunner
    import threading

    # 停止旧任务（如果存在）
    if 'current_runner' in uav_client and uav_client['current_runner']:
        runner = uav_client['current_runner']
        if hasattr(runner, 'running') and runner.running:
            runner.stop()

            # ✅ 新增：清除任务状态（解决Dashboard显示过期航线问题）
            callsign = uav_client.get('callsign', 'Unknown')
            _clear_mission_state(callsign)

    # 假目标上报：仅对航线任务（mission 5/6/7）按需启动，其他任务停止
    mission = task_data.get('mission')
    fake_cfg = uav_client.get('fake_target_config')
    if fake_cfg:
        # 需要启动
        if mission in (5, 6, 7):
            thread = uav_client.get('fake_target_thread')
            stop_event = uav_client.get('fake_target_stop')
            if not thread or not thread.is_alive():
                stop_event = threading.Event()
                uav_client['fake_target_stop'] = stop_event
                thread = threading.Thread(
                    target=fake_target_reporter,
                    args=(
                        uav_client['mqtt'],
                        uav_client['ivas_client'],
                        uav_client['device_code'],
                        uav_client['callsign'],
                        fake_cfg,
                        stop_event
                    ),
                    daemon=True,
                    name=f"ivas-fake-target-{uav_client['device_code']}"
                )
                thread.start()
                uav_client['fake_target_thread'] = thread
        else:
            # 非航线任务，关闭已有假目标线程
            stop_event = uav_client.get('fake_target_stop')
            thread = uav_client.get('fake_target_thread')
            if stop_event:
                stop_event.set()
            if thread:
                thread.join(timeout=2.0)
            uav_client['fake_target_thread'] = None
            uav_client['fake_target_stop'] = None

    # 创建新的 runner
    runner_config = {
        'callsign': uav_client.get('callsign', 'Unknown'),
        'sn': uav_client['mqtt'].gateway_sn,
        'flight_height': uav_client.get('flight_height', 100.0)
    }

    runner = MissionRunner(
        uav_client['mqtt'],
        uav_client['caller'],
        uav_client['heartbeat'],
        runner_config
    )

    runner.running = True  # 设置为运行状态，供任务执行和中断检查

    uav_client['current_runner'] = runner  # 保存引用（用于中断）

    # 在后台线程执行任务
    def task_wrapper():
        try:
            execute_ivas_task(
                task_data,                          # 第1个参数：任务数据
                uav_client['mqtt'],                 # 第2个参数：mqtt_client
                uav_client['caller'],               # 第3个参数：caller
                uav_client.get('config', {}),       # 第4个参数：uav_config
                heartbeat_thread=uav_client.get(
                    'heartbeat'),  # 可选参数：heartbeat_thread
                runner=runner                       # 可选参数：runner
            )
        except Exception as e:
            # 任务失败时启用 MQTT DEBUG 输出（用于诊断后续错误）
            print(f"[任务] ❌ 执行异常: {e}")
            print(f"[DEBUG] 已自动启用 MQTT 服务响应调试 - 后续任务将打印详细 JSON")
            uav_client['mqtt'].enable_service_debug = True
        finally:
            uav_client['current_runner'] = None

    thread = threading.Thread(target=task_wrapper, daemon=True)
    thread.start()


# ========== 室内系统专用任务转发 ==========


def task_mqtt_forwarder(
    ivas_client,
    mqtt_client,
    publish_topic: str,
    mission_filter: int,
    interval: float,
    stop_event: threading.Event
):
    """
    任务轮询与 MQTT 转发线程（室内系统专用）

    轮询 IVAS 任务，并将特定 mission 类型转发到 MQTT 主题。

    Args:
        ivas_client: IVAS HTTP 客户端
        mqtt_client: Paho MQTT 客户端
        publish_topic: MQTT 发布主题
        mission_filter: 需要转发的 mission 类型（例如 1 表示起飞）
        interval: 轮询间隔（秒）
        stop_event: 停止事件
    """
    import json
    import paho.mqtt.client as mqtt

    next_tick = time.perf_counter()
    task_count = 0

    # 任务字典映射
    mission_names = {
        1: "任务开始 - 原地起飞",
        2: "原地降落",
        3: "返航",
        4: "前往指定点",
        5: "执行预设多航点任务1",
        6: "执行预设多航点任务2",
        7: "执行预设多航点任务3"
    }

    while not stop_event.is_set():
        current = time.perf_counter()

        if current >= next_tick:
            # 轮询任务
            result = ivas_client.poll_task()

            if result:
                task_count += 1
                task_data = result.get('data', {})
                mission = task_data.get('mission', 0)
                target_id = task_data.get('id', 0)
                mission_name = mission_names.get(mission, f"未知任务({mission})")

                # 打印日志信息
                print("\n" + "="*60)
                print(f"[任务] 🎯 接收到任务 #{task_count} (时间: {time.strftime('%H:%M:%S')})")
                print(f"[任务] 类型: mission={mission} ({mission_name})")
                print(f"[任务] 目标: ID={target_id}")
                print("="*60)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("="*60)

                # 判断是否需要转发到 MQTT
                should_publish = (mission == mission_filter)

                if should_publish:
                    # 转发到 MQTT
                    try:
                        task_message = {
                            'task_id': task_count,
                            'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'timestamp': int(time.time()),
                            'mission_type': mission,
                            'mission_name': mission_name,
                            'data': result
                        }

                        payload = json.dumps(task_message, ensure_ascii=False)
                        mqtt_result = mqtt_client.publish(publish_topic, payload, qos=1)

                        if mqtt_result.rc == mqtt.MQTT_ERR_SUCCESS:
                            print(f"[任务] ✓ 已转发到 MQTT (topic: {publish_topic})")
                        else:
                            print(f"[任务] ✗ MQTT 转发失败 (rc={mqtt_result.rc})")

                    except Exception as e:
                        print(f"[任务] ✗ MQTT 转发异常: {e}")
                else:
                    # 不转发
                    print(f"[任务] ⚠️  仅打印模式（mission={mission} 不转发 MQTT）")

                print("="*60 + "\n")

            next_tick += interval

        time.sleep(0.001)
