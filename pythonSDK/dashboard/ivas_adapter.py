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
        uav_config: Dict[str, str]
    ):
        """
        初始化 IVAS 适配器

        Args:
            device_code: IVAS 设备编号
            mqtt_client: DJI MQTT 客户端（数据源）
            ivas_config: IVAS 配置（包含 base_url, report_hz, task_hz, account, password）
            uav_config: 无人机配置（包含 sn, callsign 等，用于日志显示）
        """
        self.device_code = device_code
        self.mqtt = mqtt_client
        self.uav_config = uav_config

        # 日志队列（简单列表，滚动窗口，最多保留10条）
        self.log_queue = []
        self.max_logs = 10
        self.log_lock = threading.Lock()

        # 最新任务数据
        self.latest_task = None
        self.task_lock = threading.Lock()

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
                    1: "原地起飞5米", 2: "原地降落", 3: "返航", 4: "前往指定点",
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
