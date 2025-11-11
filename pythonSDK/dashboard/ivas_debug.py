"""
IVAS DEBUG 消息管理器

用于在高速刷新的 Rich Live 界面中显示持久的 DEBUG 信息
"""
import time
import threading
from typing import List, Dict, Any
from collections import deque


class IVASDebugManager:
    """
    全局 DEBUG 消息管理器（单例模式）

    管理所有 IVAS 相关的 DEBUG 信息，供 dashboard 面板显示
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.messages = deque(maxlen=10)  # 最多保留10条消息
        self.lock = threading.Lock()

    def add_message(self, device_code: int, callsign: str, message: str, msg_type: str = 'info'):
        """
        添加 DEBUG 消息

        Args:
            device_code: 设备编号 (1, 2, 3)
            callsign: 无人机呼号
            message: 消息内容
            msg_type: 消息类型 ('info', 'error', 'success')
        """
        with self.lock:
            entry = {
                'time': time.time(),
                'device_code': device_code,
                'callsign': callsign,
                'message': message,
                'type': msg_type
            }
            self.messages.append(entry)

    def get_recent_messages(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近的 N 条消息

        Args:
            n: 返回的消息数量

        Returns:
            消息列表，按时间倒序（最新的在前）
        """
        with self.lock:
            # 转换为列表并倒序
            return list(reversed(list(self.messages)))[:n]

    def clear(self):
        """清空所有消息"""
        with self.lock:
            self.messages.clear()


# 全局单例实例
debug_manager = IVASDebugManager()
