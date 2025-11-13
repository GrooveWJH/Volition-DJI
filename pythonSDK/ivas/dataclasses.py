"""
IVAS 系统数据结构定义

提供类型安全的数据结构，用于室内定位系统。
"""

from dataclasses import dataclass, field
import threading
from typing import Optional, Tuple


@dataclass
class UWBPosition:
    """
    UWB 位置数据（线程安全）

    封装 UWB 定位数据的读写操作，内置线程安全机制。

    使用方式:
        position = UWBPosition()

        # 写入数据（线程安全）
        position.update(x=1.5, y=2.3, z=0.5, timestamp=1234567890)

        # 读取数据（线程安全）
        x, y, z, ts = position.get()

        # 检查有效性
        if position.is_valid():
            # 处理数据
            pass
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    timestamp: int = 0

    # 使用 field(default_factory=...) 避免共享可变对象
    # RLock 支持同一线程的多次锁定（避免死锁）
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def update(self, x: float, y: float, z: float, timestamp: int) -> None:
        """
        原子更新所有字段

        Args:
            x: X 坐标（米）
            y: Y 坐标（米）
            z: Z 坐标（高度，米）
            timestamp: 时间戳（毫秒）
        """
        with self._lock:
            self.x = x
            self.y = y
            self.z = z
            self.timestamp = timestamp

    def get(self) -> Tuple[Optional[float], Optional[float], Optional[float], int]:
        """
        原子读取所有字段

        Returns:
            (x, y, z, timestamp): 位置数据元组
        """
        with self._lock:
            return self.x, self.y, self.z, self.timestamp

    def is_valid(self) -> bool:
        """
        检查数据有效性

        Returns:
            bool: 如果 x, y 均不为 None/0，则返回 True
        """
        with self._lock:
            return self.x is not None and self.y is not None and self.x != 0.0 and self.y != 0.0

    def get_xy(self) -> Tuple[Optional[float], Optional[float]]:
        """
        仅读取 XY 坐标（用于平面定位）

        Returns:
            (x, y): XY 坐标元组
        """
        with self._lock:
            return self.x, self.y

    def get_with_validity(self) -> Tuple[Optional[float], Optional[float], Optional[float], int, bool]:
        """
        读取数据 + 有效性标志

        Returns:
            (x, y, z, timestamp, is_valid): 位置数据 + 有效性标志
        """
        with self._lock:
            is_valid = self.x is not None and self.y is not None and self.x != 0.0 and self.y != 0.0
            return self.x, self.y, self.z, self.timestamp, is_valid
