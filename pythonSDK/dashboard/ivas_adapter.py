"""
IVAS 适配器 - 对接真实无人机数据到 IVAS 服务器

职责：
1. 从 MQTTClient 获取真实位置数据（不使用 IVASClient 的随机数据）
2. 管理日志队列供 UI 显示
3. 处理任务接收并存储
4. 提供简单的查询接口

设计原则：
- 简单直接，不使用复杂设计模式
- 数据就近，直接从 mqtt 获取
- 日志简化，简单列表存储
"""

import sys
import os
import time
import threading
from typing import Dict, Any, Optional, List

# 添加 ivas 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ivas'))

from ivas import IVASClient


class IVASAdapter:
    """
    IVAS Client 适配器

    对接真实无人机数据源（MQTTClient）和 IVAS 服务器。
    """

    def __init__(
        self,
        device_code: int,
        mqtt_client,
        ivas_config: Dict[str, Any],
        uav_config: Dict[str, str],
        service_caller=None,
        heartbeat_thread=None,
        features: Optional[Dict[str, bool]] = None,
        broadcaster=None
    ):
        """
        初始化 IVAS 适配器

        Args:
            device_code: IVAS 设备编号
            mqtt_client: DJI MQTT 客户端（数据源）
            ivas_config: IVAS 配置（包含 base_url, report_hz, task_hz, account, password）
            uav_config: 无人机配置（包含 sn, callsign 等，用于日志显示）
            service_caller: djisdk ServiceCaller（用于任务执行）
            heartbeat_thread: 心跳线程（用于任务执行）
            features: 功能开关字典 {'position_report': bool, 'target_report': bool, 'task_receive': bool}
            broadcaster: 任务广播管理器（用于处理 id=99 广播任务）
        """
        self.device_code = device_code
        self.mqtt = mqtt_client
        self.caller = service_caller
        self.heartbeat_thread = heartbeat_thread
        self.uav_config = uav_config
        self.features = features or {}  # 存储功能配置
        self.broadcaster = broadcaster  # 广播管理器（可选）

        # 日志队列（简单列表，滚动窗口，最多保留10条）
        self.log_queue = []
        self.max_logs = 10
        self.log_lock = threading.Lock()

        # 最新任务数据
        self.latest_task = None
        self.task_lock = threading.Lock()

        # 任务执行器（后台线程）
        self.task_executor_thread = None
        self.current_runner = None  # 当前执行任务的 runner（用于中断）

        # 基准位置（用于生成坐标范围，取第一次有效GPS位置）
        self.base_lat = None
        self.base_lon = None
        self.base_alt = None

        # 创建 IVAS Client
        # 注意：base_lat/lon/alt 会在第一次获取到有效GPS后设置
        self.ivas_client = IVASClient(
            device_code=device_code,
            account=ivas_config['account'],
            password=ivas_config['password'],
            base_lat=0.0,  # 占位，稍后更新
            base_lon=0.0,  # 占位，稍后更新
            base_alt=0.0,  # 占位，稍后更新
            coord_range={'lat_offset': 0.0, 'lon_offset': 0.0, 'alt_offset': 0.0},  # 不使用随机偏移
            base_url=ivas_config['base_url'],
            report_hz=ivas_config['report_hz'],
            task_hz=ivas_config['task_hz'],
            features=self.features  # 传递功能配置
        )

        # 覆盖 IVAS Client 的数据生成方法（使用真实数据）
        self.ivas_client._generate_position_data = self._get_real_position_data

        # 覆盖日志方法（记录到本地队列）
        self.ivas_client._log = self._handle_ivas_log

        # 初始化时记录日志
        self._add_log('info', f"[{uav_config['callsign']}] IVAS 适配器初始化")

    def _get_real_position_data(self) -> Dict[str, Any]:
        """
        从真实 MQTT 获取位置数据（覆盖 IVASClient 的随机数据生成）

        Returns:
            符合 IVAS 位置上报格式的数据字典
        """
        # 从 MQTT 获取真实数据
        lat, lon, height = self.mqtt.get_position()
        heading = self.mqtt.get_attitude_head()
        h_speed, _, _, _ = self.mqtt.get_speed()

        # 第一次获取到有效GPS时，设置基准位置
        if lat is not None and lon is not None and self.base_lat is None:
            self.base_lat = lat
            self.base_lon = lon
            self.base_alt = height or 0.0
            self._add_log('info', f"基准位置已设置: ({lat:.6f}, {lon:.6f}, {self.base_alt:.1f})")

        # 判断运动状态（水平速度 > 0.5 m/s 则认为在运动）
        motion = 1 if h_speed and h_speed > 0.5 else 0

        # 构造上报数据
        position_data = {
            'deviceCode': self.device_code,
            'userX': lat or 0.0,  # 纬度
            'userY': lon or 0.0,  # 经度
            'userZ': height or 0.0,  # 海拔高度
            'azimuth': int(heading or 0),  # 方位角 (0-359)
            'localTime': int(time.time() * 1000),  # 毫秒时间戳
            'motion': motion,  # 运动状态 (0:静止, 1:移动)
            'validCount': 10 if lat and lon else 0,  # GPS 卫星数（模拟值）
            'roomId': 22,  # 任务 ID (固定传 22)
            'refPositionType': 0  # 设备类型 (固定传 0)
        }

        # 实时打印上报的经纬高
        if lat is not None and lon is not None:
            print(f"[上报] [{self.uav_config['callsign']}] 纬度:{lat:.6f} 经度:{lon:.6f} 高度:{height:.2f}m")

        return position_data

    def _handle_ivas_log(self, log_type: str, data: Any):
        """
        处理 IVAS Client 的日志输出

        根据日志类型记录到本地队列，供 UI 显示。

        Args:
            log_type: 日志类型 ('info', 'error', 'position', 'task', 'targets')
            data: 日志数据
        """
        # 根据日志类型生成友好的消息
        if log_type == 'info':
            message = str(data)
            msg_type = 'info'
        elif log_type == 'error':
            message = f"错误: {data}"
            msg_type = 'error'
        elif log_type == 'position':
            # 位置上报成功
            message = "位置上报成功"
            msg_type = 'success'
        elif log_type == 'targets':
            # 目标上报成功
            obj_cnt = data.get('obj_cnt', 0)
            message = f"目标上报成功 ({obj_cnt}个目标)"
            msg_type = 'success'
        elif log_type == 'task':
            # 任务轮询
            if isinstance(data, dict) and data.get('code') == 200 and data.get('data'):
                task_data = data['data']
                mission_names = {
                    1: "原地起飞10米", 2: "原地降落", 3: "返航", 4: "前往指定点",
                    5: "多航点任务1", 6: "多航点任务2", 7: "多航点任务3"
                }
                mission = task_data.get('mission', 0)
                mission_name = mission_names.get(mission, f"未知任务({mission})")
                target_id = task_data.get('id', 0)

                message = f"收到任务: {mission_name} (ID:{target_id})"
                msg_type = 'info'

                # 存储最新任务
                with self.task_lock:
                    self.latest_task = task_data

                # ========== 广播任务处理（id=99）==========
                if target_id == 99:
                    # 检查是否有广播管理器
                    if self.broadcaster:
                        # 触发广播（由 broadcaster 负责分发给所有adapter）
                        # broadcast_task 内部会检查任务去重，只会执行一次
                        self.broadcaster.broadcast_task(task_data, source_adapter=self)
                    else:
                        # 没有广播管理器，按普通任务处理（降级方案）
                        self._add_log('warning', f"收到广播任务 ID:{target_id}，但未配置广播管理器，将仅在本机执行")
                        self._execute_task_in_background(task_data)
                else:
                    # 普通任务（id != 99），直接执行
                    self._execute_task_in_background(task_data)
            else:
                # 无任务或任务为空
                return  # 不记录日志
        else:
            message = f"{log_type}: {data}"
            msg_type = 'info'

        self._add_log(msg_type, message)

    def _add_log(self, msg_type: str, message: str):
        """
        添加日志到队列（滚动窗口，最多保留 max_logs 条）

        Args:
            msg_type: 日志类型 ('info', 'success', 'error')
            message: 日志消息
        """
        with self.log_lock:
            log_entry = {
                'time': time.time(),
                'type': msg_type,
                'message': message
            }
            self.log_queue.append(log_entry)

            # 滚动窗口，删除最旧的日志
            if len(self.log_queue) > self.max_logs:
                self.log_queue.pop(0)

    def get_recent_logs(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近 N 条日志

        Args:
            n: 返回的日志条数

        Returns:
            日志列表，每条包含 time, type, message
        """
        with self.log_lock:
            return self.log_queue[-n:] if self.log_queue else []

    def get_latest_task(self) -> Optional[Dict[str, Any]]:
        """
        获取最新接收到的任务

        Returns:
            任务数据字典，如果没有任务则返回 None
        """
        with self.task_lock:
            return self.latest_task.copy() if self.latest_task else None

    def start(self):
        """
        启动 IVAS Client（在后台线程中运行）

        Returns:
            后台线程对象
        """
        thread = threading.Thread(target=self.ivas_client.run, daemon=True)
        thread.start()
        self._add_log('info', "IVAS Client 已启动")
        return thread

    def stop(self):
        """
        停止 IVAS Client
        """
        self.ivas_client.stop()
        self._add_log('info', "IVAS Client 已停止")

    def _execute_task_in_background(self, task_data: Dict[str, Any]):
        """
        在后台线程执行 IVAS 任务（新任务会中断旧任务）

        策略：
        - 如果有旧任务正在执行，立即停止它
        - 然后在后台线程执行新任务

        Args:
            task_data: IVAS 任务数据
        """
        # 检查是否具备执行条件
        if self.caller is None:
            self._add_log('warning', "任务执行器未初始化（缺少 ServiceCaller），跳过任务执行")
            return

        # 停止旧任务（如果存在）
        if self.current_runner and self.current_runner.running:
            self._add_log('info', "停止旧任务，准备执行新任务")
            self.current_runner.stop()  # 设置 running=False 并等待线程结束

        # 等待旧线程结束（最多等待2秒）
        if self.task_executor_thread and self.task_executor_thread.is_alive():
            self.task_executor_thread.join(timeout=2.0)
            if self.task_executor_thread.is_alive():
                self._add_log('warning', "旧任务线程未能及时停止，强制启动新任务")

        # 在后台线程执行新任务
        try:
            from djisdk.tasks.ivas_executor import execute_ivas_task
            from djisdk.tasks.runner import MissionRunner

            self._add_log('info', f"开始执行任务 {task_data.get('mission')}")

            # 创建新的 runner（用于可中断任务）
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

        except Exception as e:
            self._add_log('error', f"任务执行失败: {e}")
            self.current_runner = None

    def receive_broadcast_task(self, task_data: Dict[str, Any]):
        """
        接收来自 TaskBroadcaster 的广播任务

        此方法由 TaskBroadcaster.broadcast_task() 调用，
        用于接收 id=99 的广播任务并执行。

        Args:
            task_data: IVAS 任务数据
        """
        mission = task_data.get('mission', 0)
        mission_names = {1: "起飞", 2: "降落", 3: "返航"}
        mission_name = mission_names.get(mission, f"任务{mission}")

        # 记录日志
        self._add_log('info', f"[广播] 接收到广播任务: {mission_name}")

        # 在后台执行任务
        self._execute_task_in_background(task_data)
