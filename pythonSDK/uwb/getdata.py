#!/usr/bin/env python3
"""
UWB Data Receiver - 实时接收并解析 UWB 定位数据

从串口读取 UWB 设备发送的 896 字节数据帧，解析节点位置、距离和电压信息

帧结构:
    - Header (2B): 0x55 0x00
    - Nodes (810B): 30 × 27 bytes (id, role, pos_3d, dis_arr)
    - Padding (67B): 保留字段
    - Metadata (16B): local_time, system_time, voltage, id, role
    - Tail (1B): 0xEE
"""

import struct
import serial
import time
from typing import List, Optional

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
        x, y, z = self.pos_3d
        return f"<Node id={self.id:2d} role={role_name:7s} pos=({x:6.3f}, {y:6.3f}, {z:6.3f})m>"

    def print_detailed(self):
        """打印详细信息（彩色输出）"""
        role_name = NodeRole.get_name(self.role)
        role_color = "\033[92m" if self.role == NodeRole.ANCHOR else "\033[96m"  # Green for ANCHOR, Cyan for TAG

        print(f"  {role_color}[{role_name:7s}]\033[0m ID={self.id:2d} | "
              f"XYZ = ({self.pos_3d[0]:6.3f}, {self.pos_3d[1]:6.3f}, {self.pos_3d[2]:6.3f})m", end="")

        # 只打印有效距离（非 0xFFFF）
        valid_distances = [d for d in self.dis_arr if d < 655.0]  # 0xFFFF/100 = 655.35
        if valid_distances:
            print(f" | Dist = {valid_distances[0]:.2f}m", end="")
        print()


class UWBFrame:
    """UWB 数据帧"""

    def __init__(self):
        self.id = 0
        self.role = 0
        self.local_time = 0
        self.system_time = 0
        self.voltage = 0.0
        self.nodes: List[AnchorNode] = []

    def __repr__(self) -> str:
        role_name = NodeRole.get_name(self.role)
        return f"<Frame id={self.id} role={role_name} voltage={self.voltage:.2f}V nodes={len(self.nodes)}>"

    def print_summary(self):
        """打印帧摘要（彩色输出）"""
        timestamp = time.strftime("%H:%M:%S")
        role_name = NodeRole.get_name(self.role)

        # 统计节点类型
        anchors = sum(1 for n in self.nodes if n.role == NodeRole.ANCHOR)
        tags = sum(1 for n in self.nodes if n.role == NodeRole.TAG)

        voltage_color = "\033[92m" if self.voltage > 3.5 else "\033[93m"  # Green if >3.5V, Yellow otherwise

        print(f"\n\033[96m[{timestamp}]\033[0m "
              f"Frame #{self.id:2d} ({role_name}) | "
              f"Anchors: {anchors} | Tags: {tags} | "
              f"{voltage_color}Voltage: {self.voltage:.2f}V\033[0m")


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
    """
    解析 UWB 数据帧

    Args:
        data: 896 字节的原始数据

    Returns:
        UWBFrame 对象，解析失败返回 None
    """
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

    # 解析元数据（812 ~ 895 字节）
    # 结构: padding(67B) + local_time(4B) + system_time(4B) + voltage(2B) + system_time_dup(4B) + id(1B) + role(1B)
    meta_base = 2 + NODE_SIZE * MAX_NODES + 67

    frame.local_time = struct.unpack_from("<I", data, meta_base)[0]
    frame.voltage = struct.unpack_from("<H", data, meta_base + 8)[0] / MULTIPLY_VOLTAGE
    frame.system_time = struct.unpack_from("<I", data, meta_base + 10)[0]
    frame.id = data[meta_base + 14]
    frame.role = data[meta_base + 15]

    return frame


# ================== Serial Reader ===================
def read_uwb_serial():
    """持续读取串口数据并解析 UWB 帧"""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
    except Exception as e:
        print(f"\033[91m✗ Failed to open serial port {SERIAL_PORT}: {e}\033[0m")
        return

    buffer = bytearray()
    last_print_time = time.time()
    frame_count = 0
    print_interval = 1.0 / PRINT_FREQUENCY_HZ  # 计算打印间隔

    print("\033[96m" + "="*70 + "\033[0m")
    print("\033[92m              UWB Real-time Data Receiver\033[0m")
    print("\033[96m" + "="*70 + "\033[0m")
    print(f"  Port:             {SERIAL_PORT}")
    print(f"  Baudrate:         {BAUDRATE}")
    print(f"  Print Frequency:  {PRINT_FREQUENCY_HZ} Hz")
    print("\033[96m" + "="*70 + "\033[0m\n")
    print(f"\033[96mListening for UWB data... (Ctrl+C to stop)\033[0m\n")

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
                        frame.print_summary()
                        for node in sorted(frame.nodes, key=lambda n: (n.role, n.id)):
                            node.print_detailed()
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
    read_uwb_serial()

