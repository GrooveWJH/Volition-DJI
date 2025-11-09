#!/usr/bin/env python3
"""
UWB Data Receiver with Real-time Smoothing - 实时接收并平滑 UWB 定位数据

同时显示原始数据和平滑后的数据（仅 X/Y，忽略 Z 轴）

滤波策略:
    1. 异常值剔除 (3σ 原则)
    2. 移动平均滤波
    3. 卡尔曼滤波 (可选)
"""

import struct
import serial
import time
from typing import List, Optional, Deque
from collections import deque
import numpy as np

# ================== Protocol Constants ===================
MULTIPLY_VOLTAGE = 1000.0
MULTIPLY_POS = 1000.0

FRAME_HEADER = 0x55
FUNCTION_MARK = 0x00
TAIL_CHECK = 0xEE
FIXED_PART_SIZE = 896

NODE_SIZE = struct.calcsize("<BB" + "3s"*3 + "H"*8)  # 27 bytes
MAX_NODES = 30

# ================== Configuration ===================
PRINT_FREQUENCY_HZ = 30  # 打印频率 (Hz)
SERIAL_PORT = "/dev/ttyACM0"
BAUDRATE = 1500000

# ================== Filter Parameters (从分析报告计算) ===================
# 基于统计分析报告的实测数据
FILTER_WINDOW_X = 5      # X 轴移动平均窗口 (σ=28.6mm, 使用5点平滑)
FILTER_WINDOW_Y = 3      # Y 轴移动平均窗口 (σ=12.9mm, 使用3点平滑)
OUTLIER_THRESHOLD_X = 0.085  # X 轴异常值阈值 (3σ = 3*28.6mm = 85.8mm)
OUTLIER_THRESHOLD_Y = 0.039  # Y 轴异常值阈值 (3σ = 3*12.9mm = 38.7mm)


# ================== Data Structures ===================
class NodeRole:
    """节点角色枚举"""
    ANCHOR = 1
    TAG = 2
    CONSOLE = 3

    _NAMES = {1: "ANCHOR", 2: "TAG", 3: "CONSOLE"}

    @classmethod
    def get_name(cls, role: int) -> str:
        return cls._NAMES.get(role, "UNKNOWN")


class AnchorNode:
    """UWB 节点数据"""

    def __init__(self, node_id: int, role: int, pos_3d: List[float], dis_arr: List[float]):
        self.id = node_id
        self.role = role
        self.pos_3d = pos_3d  # [x, y, z] in meters
        self.dis_arr = dis_arr  # 8 distances in meters

    def __repr__(self) -> str:
        role_name = NodeRole.get_name(self.role)
        x, y = self.pos_3d[0], self.pos_3d[1]  # 只显示 X/Y
        return f"<Node id={self.id:2d} role={role_name:7s} pos=({x:6.3f}, {y:6.3f})m>"


class UWBFrame:
    """UWB 数据帧"""

    def __init__(self):
        self.id = 0
        self.role = 0
        self.local_time = 0
        self.system_time = 0
        self.voltage = 0.0
        self.nodes: List[AnchorNode] = []


# ================== Smoothing Filter ===================
class MovingAverageFilter:
    """移动平均滤波器（带异常值剔除）"""

    def __init__(self, window_size: int, outlier_threshold: float):
        self.window_size = window_size
        self.outlier_threshold = outlier_threshold
        self.buffer: Deque[float] = deque(maxlen=window_size)
        self.last_valid_value: Optional[float] = None

    def update(self, new_value: float) -> float:
        """更新滤波器并返回平滑后的值"""
        # 异常值检测（基于历史均值）
        if len(self.buffer) >= 3:
            mean = np.mean(self.buffer)
            if abs(new_value - mean) > self.outlier_threshold:
                # 检测到异常值，使用上一个有效值代替
                new_value = self.last_valid_value if self.last_valid_value is not None else new_value

        # 添加到缓冲区
        self.buffer.append(new_value)
        self.last_valid_value = new_value

        # 返回移动平均值
        return float(np.mean(self.buffer))

    def get_current(self) -> Optional[float]:
        """获取当前平滑值"""
        return float(np.mean(self.buffer)) if len(self.buffer) > 0 else None


class PositionSmoother:
    """2D 位置平滑器（仅 X/Y）"""

    def __init__(self):
        self.filter_x = MovingAverageFilter(FILTER_WINDOW_X, OUTLIER_THRESHOLD_X)
        self.filter_y = MovingAverageFilter(FILTER_WINDOW_Y, OUTLIER_THRESHOLD_Y)

    def update(self, x: float, y: float) -> tuple:
        """更新位置并返回平滑后的 (x, y)"""
        smoothed_x = self.filter_x.update(x)
        smoothed_y = self.filter_y.update(y)
        return smoothed_x, smoothed_y

    def get_current(self) -> Optional[tuple]:
        """获取当前平滑位置"""
        x = self.filter_x.get_current()
        y = self.filter_y.get_current()
        return (x, y) if x is not None and y is not None else None


# ================== Frame Parser ===================
def parse_24bit_signed(data: bytes) -> int:
    """解析 24-bit 有符号整数（小端序）"""
    val = int.from_bytes(data, byteorder='little', signed=True)
    return val


def parse_node(node_bytes: bytes) -> Optional[AnchorNode]:
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

    return AnchorNode(node_id, role, pos_3d, dis_arr)


def parse_uwb_frame(data: bytes) -> Optional[UWBFrame]:
    """解析 UWB 数据帧"""
    # 验证帧长度和头尾
    if len(data) < FIXED_PART_SIZE:
        return None
    if data[0] != FRAME_HEADER or data[1] != FUNCTION_MARK:
        return None
    if data[FIXED_PART_SIZE - 1] != TAIL_CHECK:
        return None

    frame = UWBFrame()

    # 解析节点数据（2 ~ 811 字节）
    offset = 2
    for _ in range(MAX_NODES):
        node_bytes = data[offset:offset + NODE_SIZE]
        node = parse_node(node_bytes)
        if node:
            frame.nodes.append(node)
        offset += NODE_SIZE

    # 解析元数据
    meta_base = 2 + NODE_SIZE * MAX_NODES + 67

    frame.local_time = struct.unpack_from("<I", data, meta_base)[0]
    frame.voltage = struct.unpack_from("<H", data, meta_base + 8)[0] / MULTIPLY_VOLTAGE
    frame.system_time = struct.unpack_from("<I", data, meta_base + 10)[0]
    frame.id = data[meta_base + 14]
    frame.role = data[meta_base + 15]

    return frame


# ================== Serial Reader with Smoothing ===================
def read_uwb_serial_smoothed():
    """持续读取串口数据，显示原始和平滑后的数据"""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
    except Exception as e:
        print(f"\033[91m✗ Failed to open serial port {SERIAL_PORT}: {e}\033[0m")
        return

    buffer = bytearray()
    last_print_time = time.time()
    frame_count = 0
    print_interval = 1.0 / PRINT_FREQUENCY_HZ

    # 为每个节点创建位置平滑器
    smoothers = {}

    print("\033[96m" + "="*100 + "\033[0m")
    print("\033[92m                    UWB Real-time Data with Smoothing (2D X/Y Only)\033[0m")
    print("\033[96m" + "="*100 + "\033[0m")
    print(f"  Port:             {SERIAL_PORT}")
    print(f"  Baudrate:         {BAUDRATE}")
    print(f"  Print Frequency:  {PRINT_FREQUENCY_HZ} Hz")
    print(f"  \033[93mFilter Parameters:\033[0m")
    print(f"    X-axis: Window={FILTER_WINDOW_X}, Threshold={OUTLIER_THRESHOLD_X*1000:.1f}mm")
    print(f"    Y-axis: Window={FILTER_WINDOW_Y}, Threshold={OUTLIER_THRESHOLD_Y*1000:.1f}mm")
    print("\033[96m" + "="*100 + "\033[0m\n")
    print(f"\033[96mListening for UWB data... (Ctrl+C to stop)\033[0m")
    print(f"\033[90m{'Node':<8} {'Raw X (m)':<12} {'Raw Y (m)':<12} {'│':<3} {'Smoothed X (m)':<16} {'Smoothed Y (m)':<16} {'ΔX (mm)':<10} {'ΔY (mm)':<10}\033[0m")
    print("\033[96m" + "="*100 + "\033[0m\n")

    try:
        while True:
            # 读取串口数据
            data = ser.read(1024)
            if data:
                buffer.extend(data)

            # 搜索完整帧
            while len(buffer) >= FIXED_PART_SIZE:
                # 查找帧头
                idx = buffer.find(bytes([FRAME_HEADER, FUNCTION_MARK]))
                if idx < 0:
                    buffer.clear()
                    break

                # 检查是否有完整帧
                if len(buffer) - idx < FIXED_PART_SIZE:
                    break

                # 提取并解析帧
                frame_data = buffer[idx:idx + FIXED_PART_SIZE]
                frame = parse_uwb_frame(frame_data)

                if frame:
                    frame_count += 1
                    now = time.time()

                    # 按频率打印
                    if now - last_print_time >= print_interval:
                        timestamp = time.strftime("%H:%M:%S")

                        # 统计节点类型
                        anchors = sum(1 for n in frame.nodes if n.role == NodeRole.ANCHOR)
                        tags = sum(1 for n in frame.nodes if n.role == NodeRole.TAG)
                        voltage_color = "\033[92m" if frame.voltage > 3.5 else "\033[93m"

                        print(f"\033[96m[{timestamp}]\033[0m Frame #{frame_count:5d} | "
                              f"Anchors: {anchors} | Tags: {tags} | "
                              f"{voltage_color}Voltage: {frame.voltage:.2f}V\033[0m")

                        # 处理每个节点
                        for node in sorted(frame.nodes, key=lambda n: (n.role, n.id)):
                            # 初始化平滑器
                            if node.id not in smoothers:
                                smoothers[node.id] = PositionSmoother()

                            # 原始位置
                            raw_x, raw_y = node.pos_3d[0], node.pos_3d[1]

                            # 更新平滑器
                            smoothed_x, smoothed_y = smoothers[node.id].update(raw_x, raw_y)

                            # 计算偏差
                            delta_x = (smoothed_x - raw_x) * 1000  # mm
                            delta_y = (smoothed_y - raw_y) * 1000  # mm

                            # 颜色编码
                            role_color = "\033[92m" if node.role == NodeRole.ANCHOR else "\033[96m"
                            role_name = NodeRole.get_name(node.role)

                            # 显示原始和平滑数据
                            print(f"  {role_color}[{role_name:7s}]\033[0m "
                                  f"ID={node.id:2d} │ "
                                  f"\033[90mRaw:\033[0m  {raw_x:7.4f}  {raw_y:7.4f}  │  "
                                  f"\033[92mSmooth:\033[0m {smoothed_x:7.4f}  {smoothed_y:7.4f}  │  "
                                  f"\033[93mΔ: {delta_x:+6.1f}  {delta_y:+6.1f}\033[0m")

                        print()  # 空行分隔
                        last_print_time = now

                # 移除已处理的帧
                buffer = buffer[idx + FIXED_PART_SIZE:]

    except KeyboardInterrupt:
        print(f"\n\n\033[93m✓ Stopped after {frame_count} frames\033[0m")
    except Exception as e:
        print(f"\n\033[91m✗ Error: {e}\033[0m")
    finally:
        ser.close()
        print("\033[92m✓ Serial port closed\033[0m")


# ================== Main Entry ===================
if __name__ == "__main__":
    read_uwb_serial_smoothed()
