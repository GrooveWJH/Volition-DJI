#!/usr/bin/env python3
"""
IVAS HTTP 客户端 - 纯函数设计

提供与 IVAS 服务器交互的 HTTP 接口：
1. 登录和 token 管理
2. 位置数据上报
3. 目标检测数据上报
4. 任务轮询

设计原则：
- 纯函数，无状态
- 数据由调用者提供
- 职责单一（只做 HTTP 请求）
"""

import requests
import time
from typing import Dict, Any, Optional


class IVASClient:
    """
    IVAS HTTP 客户端（纯函数设计）

    职责：
    - 发送 HTTP 请求到 IVAS 服务器
    - 自动处理 token 过期重新登录
    - 无状态（除了 token）

    不包含：
    - 线程循环（由调用者控制）
    - 数据生成（由调用者提供）
    - 日志输出（由调用者处理）
    """

    def __init__(self, base_url: str, account: str, password: str):
        """
        初始化 IVAS 客户端

        Args:
            base_url: IVAS 服务器地址 (例如: http://192.168.31.38:8888)
            account: 登录账号 (例如: ZSDX001)
            password: 登录密码
        """
        self.base_url = base_url
        self.account = account
        self.password = password
        self.token = None  # 登录后的 token

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
                    return True
                else:
                    print(f"[IVAS] 登录失败: {result.get('resMsg')}")
                    return False
            else:
                print(f"[IVAS] 登录失败: HTTP {resp.status_code}")
                return False

        except requests.RequestException as e:
            print(f"[IVAS] 登录异常: {e}")
            return False

    def report_position(
        self,
        device_code: int,
        lat: float,
        lon: float,
        alt: float,
        azimuth: int,
        motion: int,
        user_name: str = None,
        valid_count: int = 10,
        room_id: int = 22
    ) -> bool:
        """
        上报位置数据到 IVAS 服务器

        Args:
            device_code: 设备编号 (1, 2, 3)
            lat: 纬度
            lon: 经度
            alt: 海拔高度（米）
            azimuth: 方位角（0-359度）
            motion: 运动状态 (0:静止, 1:移动)
            user_name: 用户名称（呼号，例如 UAV-1）
            valid_count: GPS 卫星数（默认 10）
            room_id: 任务 ID（默认 22）

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        url = f"{self.base_url}/jk-ivas/third/controller/reportUserData"

        data = {
            'ivasUserInfoId': device_code,  # 人员ID = 设备编号
            'userX': lat,
            'userY': lon,
            'userZ': alt,
            'azimuth': azimuth,
            'localTime': int(time.time() * 1000),  # 毫秒时间戳
            'motion': motion,
            'validCount': valid_count,
            'roomId': room_id,
            'refPositionType': 0
        }

        # 添加用户名称（如果提供）
        if user_name:
            data['userName'] = user_name

        resp = self._request('POST', url, params=data)
        return resp is not None and resp.status_code == 200

    def report_targets(self, timestamp: int, objs: list) -> bool:
        """
        上报目标数据到 IVAS 服务器

        Args:
            timestamp: 时间戳（秒）
            objs: 目标列表，每个目标包含 id, cls, gis, bbox, obj_img

        Returns:
            bool: 成功返回 True，失败返回 False
        """
        url = f"{self.base_url}/jk-ivas/non/controller/postTarPos"

        data = {
            'timestamp': timestamp,
            'obj_cnt': len(objs),
            'objs': objs
        }

        resp = self._request('POST', url, json=data)
        return resp is not None and resp.status_code == 200

    def poll_task(self) -> Optional[Dict[str, Any]]:
        """
        从 IVAS 服务器轮询任务

        Returns:
            Dict: 任务数据（code=200 且有 data 时），否则返回 None
        """
        url = f"{self.base_url}/jk-ivas/third/controller/outdoorTask"

        resp = self._request('GET', url, params={})

        if resp and resp.status_code == 200:
            try:
                result = resp.json()
                # 只返回有效任务
                if result.get('code') == 200 and result.get('data'):
                    return result
                return None
            except Exception as e:
                print(f"[IVAS] 任务解析失败: {e}")
                return None

        return None

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
                print(f"[IVAS] Token 过期，重新登录")
                if self.login():
                    # 重试一次
                    headers['token'] = self.token
                    if method == 'POST':
                        resp = requests.post(url, **kwargs)
                    else:
                        resp = requests.get(url, **kwargs)

            return resp

        except requests.RequestException as e:
            print(f"[IVAS] 请求异常: {e}")
            return None
