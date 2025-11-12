#!/usr/bin/env python3
"""
UWB Client - 整合 uwb/ 目录的串口读取功能

从串口读取 UWB 定位数据，提供简单的位置接口供控制系统使用。

使用方法:
    from uwb_client import UWBClient

    # 创建客户端（自动启动后台读取线程）
    client = UWBClient(target_node_id=2, use_smoothing=True)

    # 获取位置
    position = client.get_position()  # (x, y, z)

    # 停止
    client.stop()
"""

import struct
import serial
import time
import threading
from typing import Optional, Tuple, List, Deque
from collections import deque
import sys
import os

# 添加 uwb/ 目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
uwb_dir = os.path.join(script_dir, 'uwb')
if uwb_dir not in sys.path:
    sys.path.insert(0, uwb_dir)

# 尝试导入 numpy（用于平滑）
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("[UWB] Warning: numpy not available, smoothing disabled")

# ================== Protocol Constants (from uwb/getdata.py) ===================
MULTIPLY_VOLTAGE = 1000.0
MULTIPLY_POS = 1000.0

FRAME_HEADER = 0x55
FUNCTION_MARK = 0x00
TAIL_CHECK = 0xEE
FIXED_PART_SIZE = 896

NODE_SIZE = struct.calcsize("<BB" + "3s"*3 + "H"*8)  # 27 bytes
MAX_NODES = 30

# ================== Configuration ===================
DEFAULT_SERIAL_PORT = "/dev/ttyACM0"
DEFAULT_BAUDRATE = 1500000
DEFAULT_TARGET_NODE_ID = 2  # TAG 节点 ID

# 内存安全配置
MAX_BUFFER_SIZE = 10240  # 最大缓冲区大小（10KB）

# 自动重连配置
RECONNECT_INTERVAL = 5   # 重连尝试间隔（秒）

# ================== Smoothing Filter (from uwb/getdata_smoothed.py) ===================
FILTER_WINDOW_X = 40
FILTER_WINDOW_Y = 40
FILTER_WINDOW_Z = 20
OUTLIER_THRESHOLD_X = 0.40  # 400mm
OUTLIER_THRESHOLD_Y = 0.40  # 400mm
OUTLIER_THRESHOLD_Z = 0.050  # 50mm

# 自适应异常值检测配置
MAX_CONSECUTIVE_OUTLIERS = 100  # 连续 N 次异常后强制接受（说明目标真的移动了）


class MovingAverageFilter:
    """移动平均滤波器（带自适应异常值剔除）"""

    def __init__(self, window_size: int, outlier_threshold: float):
        self.window_size = window_size
        self.outlier_threshold = outlier_threshold
        self.buffer: Deque[float] = deque(maxlen=window_size)
        self.last_valid_value: Optional[float] = None
        self.consecutive_outliers = 0  # 连续异常值计数

    def update(self, new_value: float) -> float:
        """更新滤波器并返回平滑后的值"""
        if not HAS_NUMPY:
            # 没有 numpy，使用简单平均
            self.buffer.append(new_value)
            self.consecutive_outliers = 0
            return sum(self.buffer) / len(self.buffer)

        # 异常值检测（基于历史均值）
        is_outlier = False
        if len(self.buffer) >= 3:
            mean = np.mean(self.buffer)
            deviation = abs(new_value - mean)

            if deviation > self.outlier_threshold:
                is_outlier = True
                self.consecutive_outliers += 1

                # 连续异常值检测：如果连续 N 次都是异常，说明目标真的移动了
                if self.consecutive_outliers >= MAX_CONSECUTIVE_OUTLIERS:
                    # 强制接受新值，重置缓冲区以快速适应
                    self.buffer.clear()
                    self.buffer.append(new_value)
                    self.consecutive_outliers = 0
                    self.last_valid_value = new_value
                    return new_value
                else:
                    # 暂时使用上一个有效值
                    new_value = self.last_valid_value if self.last_valid_value is not None else new_value
            else:
                # 正常值，重置异常计数
                self.consecutive_outliers = 0

        # 添加到缓冲区
        self.buffer.append(new_value)
        if not is_outlier:
            self.last_valid_value = new_value

        # 返回移动平均值
        return float(np.mean(self.buffer))

    def get_current(self) -> Optional[float]:
        """获取当前平滑值"""
        if len(self.buffer) == 0:
            return None
        if HAS_NUMPY:
            return float(np.mean(self.buffer))
        else:
            return sum(self.buffer) / len(self.buffer)


class PositionSmoother:
    """3D 位置平滑器"""

    def __init__(self):
        self.filter_x = MovingAverageFilter(FILTER_WINDOW_X, OUTLIER_THRESHOLD_X)
        self.filter_y = MovingAverageFilter(FILTER_WINDOW_Y, OUTLIER_THRESHOLD_Y)
        self.filter_z = MovingAverageFilter(FILTER_WINDOW_Z, OUTLIER_THRESHOLD_Z)

    def update(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """更新位置并返回平滑后的 (x, y, z)"""
        smoothed_x = self.filter_x.update(x)
        smoothed_y = self.filter_y.update(y)
        smoothed_z = self.filter_z.update(z)
        return smoothed_x, smoothed_y, smoothed_z

    def get_current(self) -> Optional[Tuple[float, float, float]]:
        """获取当前平滑位置"""
        x = self.filter_x.get_current()
        y = self.filter_y.get_current()
        z = self.filter_z.get_current()
        return (x, y, z) if x is not None and y is not None and z is not None else None


# ================== Frame Parser (from uwb/getdata.py) ===================
def parse_24bit_signed(data: bytes) -> int:
    """解析 24-bit 有符号整数（小端序）"""
    val = int.from_bytes(data, byteorder='little', signed=True)
    return val


def parse_node(node_bytes: bytes) -> Optional[dict]:
    """解析单个节点数据（27 bytes）"""
    if len(node_bytes) < NODE_SIZE:
        return None

    node_id = node_bytes[0]
    if node_id == 0xFF:  # 无效节点
        return None

    role = node_bytes[1]

    # pos_3d: 3 × 24-bit signed int
    pos_3d = []
    for i in range(3):
        offset = 2 + 3 * i
        raw_bytes = node_bytes[offset:offset + 3]
        value = parse_24bit_signed(raw_bytes) / MULTIPLY_POS
        pos_3d.append(value)

    # dis_arr: 8 × uint16
    dis_arr = list(struct.unpack_from("<8H", node_bytes, 11))
    dis_arr = [d / 100.0 for d in dis_arr]

    return {
        'id': node_id,
        'role': role,
        'pos_3d': pos_3d,
        'dis_arr': dis_arr
    }


def parse_uwb_frame(data: bytes) -> Optional[dict]:
    """解析 UWB 数据帧"""
    # 验证帧长度和头尾
    if len(data) < FIXED_PART_SIZE:
        return None
    if data[0] != FRAME_HEADER or data[1] != FUNCTION_MARK:
        return None
    if data[FIXED_PART_SIZE - 1] != TAIL_CHECK:
        return None

    frame = {
        'nodes': [],
        'voltage': 0.0,
        'timestamp': time.time()
    }

    # 解析节点数据（2 ~ 811 字节）
    offset = 2
    for _ in range(MAX_NODES):
        node_bytes = data[offset:offset + NODE_SIZE]
        node = parse_node(node_bytes)
        if node:
            frame['nodes'].append(node)
        offset += NODE_SIZE

    # 解析元数据
    meta_base = 2 + NODE_SIZE * MAX_NODES + 67
    frame['voltage'] = struct.unpack_from("<H", data, meta_base + 8)[0] / MULTIPLY_VOLTAGE

    return frame


# ================== UWB Client ===================
class UWBClient:
    """
    UWB 客户端 - 后台读取串口数据

    Args:
        target_node_id: 目标节点 ID（默认 2，TAG 节点）
        use_smoothing: 是否启用平滑滤波（默认 True）
        serial_port: 串口路径（默认 /dev/ttyACM0）
        baudrate: 波特率（默认 1500000）
    """

    def __init__(
        self,
        target_node_id: int = DEFAULT_TARGET_NODE_ID,
        use_smoothing: bool = True,
        serial_port: str = DEFAULT_SERIAL_PORT,
        baudrate: int = DEFAULT_BAUDRATE,
        auto_reconnect: bool = True
    ):
        self.target_node_id = target_node_id
        self.use_smoothing = use_smoothing and HAS_NUMPY
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.auto_reconnect = auto_reconnect

        self.position: Optional[Tuple[float, float, float]] = None
        self.smoother: Optional[PositionSmoother] = None
        if self.use_smoothing:
            self.smoother = PositionSmoother()

        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 启动后台读取线程
        self._start()

    def _start(self):
        """启动后台读取线程"""
        self._running = True
        self._thread = threading.Thread(target=self._read_loop_with_reconnect, daemon=True)
        self._thread.start()
        print(f"[UWB] Client started: {self.serial_port} @ {self.baudrate}")
        print(f"[UWB] Target node ID: {self.target_node_id}")
        print(f"[UWB] Smoothing: {'enabled' if self.use_smoothing else 'disabled'}")
        print(f"[UWB] Auto-reconnect: {'enabled' if self.auto_reconnect else 'disabled'}")

    def _read_loop_with_reconnect(self):
        """带自动重连的后台读取循环"""
        while self._running:
            try:
                # 尝试打开串口
                print(f"[UWB] Connecting to {self.serial_port}...")
                ser = serial.Serial(self.serial_port, self.baudrate, timeout=0.1)
                print(f"[UWB] ✓ Connected to {self.serial_port}")
                self._connected = True

                # 串口读取循环
                self._read_loop(ser)

            except serial.SerialException as e:
                self._connected = False
                if self.auto_reconnect:
                    print(f"[UWB] ✗ Serial port error: {e}")
                    print(f"[UWB] Waiting {RECONNECT_INTERVAL}s before reconnect...")
                    time.sleep(RECONNECT_INTERVAL)
                else:
                    print(f"[UWB] ERROR: Failed to open serial port: {e}")
                    self._running = False
                    break
            except Exception as e:
                self._connected = False
                print(f"[UWB] ERROR: {e}")
                if self.auto_reconnect:
                    print(f"[UWB] Waiting {RECONNECT_INTERVAL}s before reconnect...")
                    time.sleep(RECONNECT_INTERVAL)
                else:
                    self._running = False
                    break

    def _read_loop(self, ser):
        """实际的串口读取循环"""
        buffer = bytearray()

        try:
            while self._running and self._connected:
                # 读取串口数据
                data = ser.read(1024)
                if data:
                    buffer.extend(data)

                # 防止缓冲区无限增长（内存安全）
                if len(buffer) > MAX_BUFFER_SIZE:
                    print(f"[UWB] WARNING: Buffer overflow ({len(buffer)} bytes), clearing...")
                    buffer.clear()
                    continue

                # 搜索完整帧
                while len(buffer) >= FIXED_PART_SIZE:
                    # 查找帧头
                    idx = buffer.find(bytes([FRAME_HEADER, FUNCTION_MARK]))
                    if idx < 0:
                        buffer.clear()
                        break

                    # 丢弃帧头之前的垃圾数据
                    if idx > 0:
                        buffer = buffer[idx:]
                        idx = 0

                    # 检查是否有完整帧
                    if len(buffer) - idx < FIXED_PART_SIZE:
                        break

                    # 提取并解析帧
                    frame_data = buffer[idx:idx + FIXED_PART_SIZE]
                    frame = parse_uwb_frame(frame_data)

                    if frame:
                        # 查找目标节点
                        for node in frame['nodes']:
                            if node['id'] == self.target_node_id:
                                x, y, z = node['pos_3d']

                                # 平滑处理
                                if self.use_smoothing and self.smoother:
                                    x, y, z = self.smoother.update(x, y, z)

                                # 更新位置（线程安全）
                                with self._lock:
                                    self.position = (x, y, z)
                                break

                    # 移除已处理的帧
                    buffer = buffer[idx + FIXED_PART_SIZE:]

        except serial.SerialException as e:
            print(f"[UWB] Serial disconnected: {e}")
            self._connected = False
            raise  # 重新抛出异常，触发重连
        except Exception as e:
            print(f"[UWB] ERROR in read loop: {e}")
            raise
        finally:
            try:
                ser.close()
                print("[UWB] Serial port closed")
            except:
                pass

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """
        获取当前位置

        Returns:
            (x, y, z) 位置坐标（米），数据不可用时返回 None
        """
        with self._lock:
            return self.position

    def is_connected(self) -> bool:
        """检查串口是否已连接"""
        return self._connected

    def stop(self):
        """停止客户端"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        print(f"[UWB] Client stopped")

    def __del__(self):
        """析构函数，确保资源释放"""
        self.stop()


# ================== 使用示例 ===================
if __name__ == '__main__':
    print("UWB Client Test\n")

    # 创建客户端
    client = UWBClient(target_node_id=2, use_smoothing=True)

    try:
        print("\nReading UWB position data (Ctrl+C to stop)...\n")
        count = 0
        while True:
            pos = client.get_position()
            if pos:
                x, y, z = pos
                print(f"[{count:04d}] Position: ({x:7.4f}, {y:7.4f}, {z:7.4f})m", end='\r')
                count += 1
            else:
                print("Waiting for UWB data...", end='\r')
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        client.stop()
        print("Test completed")
