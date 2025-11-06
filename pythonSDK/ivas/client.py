#!/usr/bin/env python3
"""
IVAS 无人机客户端核心模块

提供与 IVAS 服务器交互的核心功能：
1. 位置数据上报
2. 目标检测数据上报
3. 任务轮询
4. 自动 token 管理
"""

import requests
import time
import random
from typing import Dict, Any, Optional


class IVASClient:
    """IVAS 无人机客户端

    一个线程处理所有频率的任务：
    - 高频: 位置上报 + 目标上报 (可配置)
    - 低频: 任务轮询 (可配置)

    特性：
    - 自动登录和 token 管理
    - 自动处理 token 过期重新登录
    - 随机数据生成
    - 可配置的上报频率
    """

    TARGET_TYPES = ["person", "vehicle", "aircraft"]  # 0:人, 1:车, 2:飞机

    def __init__(
        self,
        device_code: int,
        account: str,
        password: str,
        base_lat: float,
        base_lon: float,
        base_alt: float,
        coord_range: Dict[str, float],
        base_url: str,
        display_queue=None,
        report_hz: float = 1.0,
        task_hz: float = 0.2
    ):
        """
        初始化 IVAS 客户端

        Args:
            device_code: 设备编号 (1, 2, 3)
            account: 登录账号 (例如: ZSDX001)
            password: 登录密码
            base_lat: 基准纬度
            base_lon: 基准经度
            base_alt: 基准海拔高度
            coord_range: 坐标随机范围，字典包含 lat_offset, lon_offset, alt_offset
            base_url: IVAS 服务器地址 (例如: http://localhost:5001)
            display_queue: 可视化队列 (可选)
            report_hz: 位置和目标上报频率 (Hz)
            task_hz: 任务轮询频率 (Hz)
        """
        self.device_code = device_code
        self.account = account
        self.password = password
        self.base_lat = base_lat
        self.base_lon = base_lon
        self.base_alt = base_alt
        self.coord_range = coord_range

        self.base_url = base_url
        self.token = None  # 登录后的 token
        self.queue = display_queue

        self.report_interval = 1.0 / report_hz
        self.task_interval = 1.0 / task_hz

        self.running = True
        self.last_task_time = 0

    def run(self):
        """主运行循环 - 一个线程处理所有频率的任务"""
        # 启动前先登录获取 token
        if not self.login():
            self._log('error', "初始登录失败，无法启动")
            return

        while self.running:
            loop_start = time.time()

            try:
                # 每次循环都发送位置和目标数据
                self._report_position()
                self._report_targets()

                # 检查是否需要轮询任务
                now = time.time()
                if now - self.last_task_time >= self.task_interval:
                    self._poll_task()
                    self.last_task_time = now

            except Exception as e:
                self._log('error', f"循环异常: {e}")

            # 精确睡眠，保持频率
            elapsed = time.time() - loop_start
            sleep_time = max(0, self.report_interval - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        """停止运行"""
        self.running = False

    def login(self) -> bool:
        """
        登录 IVAS 服务器获取 token

        Returns:
            bool: 登录成功返回 True，失败返回 False
        """
        url = f"{self.base_url}/jk-ivas/third/controller/zsLogin"
        payload = {
            'account': self.account,
            'password': self.password
        }

        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('resCode') == 1:
                    self.token = result['resData']['token']
                    self._log('info', f"[{self.account}] 登录成功")
                    return True
                else:
                    self._log('error', f"[{self.account}] 登录失败: {result.get('resMsg')}")
                    return False
            else:
                self._log('error', f"[{self.account}] 登录失败: HTTP {resp.status_code}")
                return False

        except requests.RequestException as e:
            self._log('error', f"[{self.account}] 登录异常: {e}")
            return False

    # ==================== 数据生成方法 ====================

    def _generate_position_data(self) -> Dict[str, Any]:
        """生成随机位置数据"""
        lat_offset = self.coord_range['lat_offset']
        lon_offset = self.coord_range['lon_offset']
        alt_offset = self.coord_range['alt_offset']

        return {
            'deviceCode': self.device_code,
            'userX': self.base_lat + random.uniform(-lat_offset, lat_offset),
            'userY': self.base_lon + random.uniform(-lon_offset, lon_offset),
            'userZ': self.base_alt + random.uniform(-alt_offset, alt_offset),
            'azimuth': random.randint(0, 359),
            'localTime': int(time.time() * 1000),  # 毫秒时间戳
            'motion': random.randint(0, 1),
            'validCount': random.randint(5, 12),
            'roomId': 22,
            'refPositionType': 0
        }

    def _generate_target_data(self) -> Dict[str, Any]:
        """生成随机目标检测数据"""
        obj_cnt = random.randint(0, 3)
        objs = []

        lat_offset = self.coord_range['lat_offset']
        lon_offset = self.coord_range['lon_offset']

        for _ in range(obj_cnt):
            target_lat = self.base_lat + random.uniform(-lat_offset, lat_offset)
            target_lon = self.base_lon + random.uniform(-lon_offset, lon_offset)
            target_alt = self.base_alt + random.uniform(-10, 10)

            objs.append({
                'id': random.randint(1000, 9999),
                'cls': random.randint(0, 2),  # 0:人, 1:车, 2:飞机
                'gis': [target_lon, target_lat, target_alt],
                'bbox': [
                    random.uniform(0, 1920),
                    random.uniform(0, 1080),
                    random.uniform(50, 200),
                    random.uniform(50, 200)
                ],
                'obj_img': f"http://example.com/img/{random.randint(1, 100)}.jpg"
            })

        return {
            'timestamp': int(time.time()),
            'obj_cnt': obj_cnt,
            'objs': objs
        }

    # ==================== HTTP 请求方法 ====================

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """
        统一的 HTTP 请求入口，自动处理 token 过期

        Args:
            method: 'GET' 或 'POST'
            url: 请求 URL
            **kwargs: 传递给 requests 的参数

        Returns:
            Response 对象，失败返回 None
        """
        headers = kwargs.get('headers', {})
        headers['token'] = self.token
        kwargs['headers'] = headers
        kwargs['timeout'] = kwargs.get('timeout', 3)

        try:
            if method == 'POST':
                resp = requests.post(url, **kwargs)
            else:
                resp = requests.get(url, **kwargs)

            # 处理 401 token 过期
            if resp.status_code == 401:
                self._log('warning', f"[{self.account}] Token 过期，重新登录")
                if self.login():
                    # 重试一次
                    headers['token'] = self.token
                    if method == 'POST':
                        resp = requests.post(url, **kwargs)
                    else:
                        resp = requests.get(url, **kwargs)

            return resp

        except requests.RequestException as e:
            self._log('error', f"请求异常: {e}")
            return None

    def _report_position(self):
        """上报位置数据到 IVAS 服务器 (POST with URL params)"""
        url = f"{self.base_url}/jk-ivas/third/controller/reportUserData"
        data = self._generate_position_data()

        # 使用 params 传递 URL 参数
        resp = self._request('POST', url, params=data)

        if resp and resp.status_code == 200:
            # 添加 token 和 account 信息用于显示
            data['_token'] = self.token
            data['_account'] = self.account
            self._log('position', data)
        elif resp:
            self._log('error', f"位置上报失败: HTTP {resp.status_code}")

    def _report_targets(self):
        """上报目标数据到 IVAS 服务器 (POST with JSON body)"""
        url = f"{self.base_url}/jk-ivas/non/controller/postTarPos"
        data = self._generate_target_data()

        # 使用 json 传递 body
        resp = self._request('POST', url, json=data)

        if resp and resp.status_code == 200:
            self._log('targets', data)
        elif resp:
            self._log('error', f"目标上报失败: HTTP {resp.status_code}")

    def _poll_task(self):
        """从 IVAS 服务器轮询任务 (GET)"""
        url = f"{self.base_url}/jk-ivas/third/controller/outdoorTask"

        resp = self._request('GET', url)

        if resp and resp.status_code == 200:
            try:
                result = resp.json()
                self._log('task', result)
            except Exception as e:
                self._log('error', f"任务解析失败: {e}")
        elif resp:
            self._log('error', f"任务轮询失败: HTTP {resp.status_code}")

    # ==================== 日志辅助方法 ====================

    def _log(self, log_type: str, data: Any):
        """统一的日志输出方法"""
        if self.queue:
            self.queue.put((log_type, self.device_code, data))
        else:
            # 如果没有队列，直接打印
            print(f"[{log_type.upper()}] Device {self.device_code}: {data}")
