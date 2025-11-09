#!/usr/bin/env python3
"""
UWB Statistics Collection - 采集固定点UWB数据并计算偏差和稳定性统计

将UWB标签放置在已知固定位置，采集大量数据以计算:
- Bias (偏差): 测量值与真实值的平均误差
- Stability (稳定性): 标准差、方差、范围等统计指标

使用方法:
    python statistics.py --true-x 1.0 --true-y 2.0 --true-z 0.5 --duration 60
"""

import struct
import serial
import time
import argparse
import csv
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections import defaultdict
from datetime import datetime
import numpy as np

# ================== 导入 getdata.py 的常量和类 ===================
MULTIPLY_VOLTAGE = 1000.0
MULTIPLY_POS = 1000.0

FRAME_HEADER = 0x55
FUNCTION_MARK = 0x00
TAIL_CHECK = 0xEE
FIXED_PART_SIZE = 896

NODE_SIZE = struct.calcsize("<BB" + "3s"*3 + "H"*8)  # 27 bytes
MAX_NODES = 30

# ================== Configuration ===================
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


class UWBFrame:
    """UWB 数据帧"""

    def __init__(self):
        self.id = 0
        self.role = 0
        self.local_time = 0
        self.system_time = 0
        self.voltage = 0.0
        self.nodes: List[AnchorNode] = []


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


# ================== Statistics Collector ===================
class NodeStatistics:
    """单个节点的统计信息收集器"""

    def __init__(self, node_id: int, role: int, true_position: Optional[List[float]] = None):
        self.node_id = node_id
        self.role = role
        self.true_position = true_position  # [x, y, z] 真实位置（如果已知）

        # 原始数据收集
        self.positions: List[List[float]] = []  # 所有位置测量值
        self.timestamps: List[float] = []  # 时间戳

        # 实时统计
        self.sample_count = 0

    def add_sample(self, position: List[float], timestamp: float):
        """添加一个测量样本"""
        self.positions.append(position)
        self.timestamps.append(timestamp)
        self.sample_count += 1

    def compute_statistics(self) -> Dict[str, Any]:
        """计算统计指标"""
        if self.sample_count == 0:
            return {}

        positions = np.array(self.positions)

        # 基本统计量
        mean_pos = np.mean(positions, axis=0)
        std_pos = np.std(positions, axis=0)
        min_pos = np.min(positions, axis=0)
        max_pos = np.max(positions, axis=0)
        range_pos = max_pos - min_pos

        # 3D位置的标准差（欧几里得距离）
        mean_distance_from_mean = np.mean(np.linalg.norm(positions - mean_pos, axis=1))

        stats = {
            'node_id': self.node_id,
            'role': NodeRole.get_name(self.role),
            'sample_count': self.sample_count,
            'mean_x': mean_pos[0],
            'mean_y': mean_pos[1],
            'mean_z': mean_pos[2],
            'std_x': std_pos[0],
            'std_y': std_pos[1],
            'std_z': std_pos[2],
            'range_x': range_pos[0],
            'range_y': range_pos[1],
            'range_z': range_pos[2],
            'mean_3d_error': mean_distance_from_mean,
        }

        # 如果已知真实位置，计算偏差
        if self.true_position is not None:
            true_pos = np.array(self.true_position)
            bias = mean_pos - true_pos
            bias_magnitude = np.linalg.norm(bias)

            # 每个样本到真实位置的误差
            errors = np.linalg.norm(positions - true_pos, axis=1)
            rmse = np.sqrt(np.mean(errors ** 2))

            stats.update({
                'true_x': true_pos[0],
                'true_y': true_pos[1],
                'true_z': true_pos[2],
                'bias_x': bias[0],
                'bias_y': bias[1],
                'bias_z': bias[2],
                'bias_magnitude': bias_magnitude,
                'rmse': rmse,
            })

        return stats


class UWBStatisticsCollector:
    """UWB统计数据收集器"""

    def __init__(self, true_position: Optional[Dict[int, List[float]]] = None,
                 target_tag_id: Optional[int] = None):
        """
        Args:
            true_position: 节点真实位置字典 {node_id: [x, y, z]}
            target_tag_id: 目标TAG ID（如果只关注特定TAG）
        """
        self.true_position = true_position or {}
        self.target_tag_id = target_tag_id
        self.node_stats: Dict[int, NodeStatistics] = {}
        self.start_time = time.time()
        self.frame_count = 0

    def process_frame(self, frame: UWBFrame):
        """处理一帧数据"""
        self.frame_count += 1
        current_time = time.time() - self.start_time

        for node in frame.nodes:
            # 如果指定了目标TAG，只处理该TAG
            if self.target_tag_id is not None and node.id != self.target_tag_id:
                continue

            # 初始化节点统计对象
            if node.id not in self.node_stats:
                true_pos = self.true_position.get(node.id)
                self.node_stats[node.id] = NodeStatistics(node.id, node.role, true_pos)

            # 添加样本
            self.node_stats[node.id].add_sample(node.pos_3d, current_time)

    def get_statistics(self) -> List[Dict[str, Any]]:
        """获取所有节点的统计结果"""
        return [stats.compute_statistics() for stats in self.node_stats.values()]

    def save_to_csv(self, filename: str):
        """保存统计结果到CSV"""
        stats_list = self.get_statistics()
        if not stats_list:
            print("\033[93m⚠ No data collected\033[0m")
            return

        # 确保目录存在
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        with open(filename, 'w', newline='') as f:
            # 使用第一个统计对象的键作为表头
            fieldnames = list(stats_list[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()
            for stats in stats_list:
                writer.writerow(stats)

        print(f"\033[92m✓ Statistics saved to {filename}\033[0m")

    def save_raw_data_to_csv(self, filename: str):
        """保存原始测量数据到CSV（用于进一步分析）"""
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['node_id', 'role', 'timestamp', 'x', 'y', 'z'])

            for node_id, stats in self.node_stats.items():
                role_name = NodeRole.get_name(stats.role)
                for pos, ts in zip(stats.positions, stats.timestamps):
                    writer.writerow([node_id, role_name, ts, pos[0], pos[1], pos[2]])

        print(f"\033[92m✓ Raw data saved to {filename}\033[0m")

    def print_live_stats(self):
        """打印实时统计信息（带颜色）"""
        stats_list = self.get_statistics()

        print(f"\n\033[96m{'='*80}\033[0m")
        print(f"\033[96m  Live Statistics - Frames: {self.frame_count} | "
              f"Duration: {time.time() - self.start_time:.1f}s\033[0m")
        print(f"\033[96m{'='*80}\033[0m")

        for stats in stats_list:
            node_id = stats['node_id']
            role = stats['role']
            role_color = "\033[92m" if stats['role'] == 'ANCHOR' else "\033[96m"

            print(f"\n{role_color}[{role:7s}] ID={node_id:2d}\033[0m | Samples: {stats['sample_count']}")
            print(f"  Mean Position: ({stats['mean_x']:7.4f}, {stats['mean_y']:7.4f}, {stats['mean_z']:7.4f})m")
            print(f"  Std Deviation: ({stats['std_x']:7.4f}, {stats['std_y']:7.4f}, {stats['std_z']:7.4f})m")
            print(f"  Range:         ({stats['range_x']:7.4f}, {stats['range_y']:7.4f}, {stats['range_z']:7.4f})m")
            print(f"  Mean 3D Error: {stats['mean_3d_error']:7.4f}m")

            # 如果有真实位置，显示偏差信息
            if 'bias_magnitude' in stats:
                bias_color = "\033[92m" if stats['bias_magnitude'] < 0.1 else "\033[93m"
                print(f"  \033[94mTrue Position: ({stats['true_x']:7.4f}, {stats['true_y']:7.4f}, {stats['true_z']:7.4f})m\033[0m")
                print(f"  {bias_color}Bias:          ({stats['bias_x']:7.4f}, {stats['bias_y']:7.4f}, {stats['bias_z']:7.4f})m\033[0m")
                print(f"  {bias_color}Bias Magnitude: {stats['bias_magnitude']:7.4f}m\033[0m")
                print(f"  {bias_color}RMSE:          {stats['rmse']:7.4f}m\033[0m")


# ================== Main Collection Function ===================
def collect_uwb_statistics(duration: float, true_position: Optional[Dict[int, List[float]]] = None,
                          target_tag_id: Optional[int] = None, update_interval: float = 5.0):
    """
    采集UWB统计数据

    Args:
        duration: 采集时长（秒）
        true_position: 节点真实位置 {node_id: [x, y, z]}
        target_tag_id: 目标TAG ID（仅采集该TAG数据）
        update_interval: 实时统计显示间隔（秒）
    """
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
    except Exception as e:
        print(f"\033[91m✗ Failed to open serial port {SERIAL_PORT}: {e}\033[0m")
        return None

    collector = UWBStatisticsCollector(true_position, target_tag_id)
    buffer = bytearray()
    last_update_time = time.time()

    print("\033[96m" + "="*80 + "\033[0m")
    print("\033[92m              UWB Statistics Collection\033[0m")
    print("\033[96m" + "="*80 + "\033[0m")
    print(f"  Port:              {SERIAL_PORT}")
    print(f"  Baudrate:          {BAUDRATE}")
    print(f"  Duration:          {duration}s")
    print(f"  Update Interval:   {update_interval}s")
    if target_tag_id is not None:
        print(f"  \033[93mTarget TAG ID:     {target_tag_id}\033[0m")
    if true_position:
        print(f"  \033[94mTrue Position Set: {len(true_position)} nodes\033[0m")
    print("\033[96m" + "="*80 + "\033[0m\n")
    print(f"\033[96mCollecting data... (Ctrl+C to stop early)\033[0m\n")

    try:
        while (time.time() - collector.start_time) < duration:
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
                    collector.process_frame(frame)

                # 移除已处理的帧
                buffer = buffer[idx + FIXED_PART_SIZE:]

            # 定期显示实时统计
            now = time.time()
            if now - last_update_time >= update_interval:
                collector.print_live_stats()
                last_update_time = now

    except KeyboardInterrupt:
        print(f"\n\n\033[93m✓ Collection stopped early\033[0m")
    finally:
        ser.close()

    # 最终统计显示
    collector.print_live_stats()

    # 保存数据
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("uwb_statistics")
    output_dir.mkdir(exist_ok=True)

    stats_file = output_dir / f"statistics_{timestamp}.csv"
    raw_data_file = output_dir / f"raw_data_{timestamp}.csv"

    collector.save_to_csv(str(stats_file))
    collector.save_raw_data_to_csv(str(raw_data_file))

    return collector


# ================== Main Entry ===================
def main():
    parser = argparse.ArgumentParser(
        description="UWB Statistics Collection - 固定点位置偏差和稳定性统计",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 采集60秒数据，无真实位置
  python statistics.py --duration 60

  # 指定TAG的真实位置
  python statistics.py --duration 60 --true-x 1.0 --true-y 2.0 --true-z 0.5 --tag-id 5

  # 只采集特定TAG
  python statistics.py --duration 120 --tag-id 5
        """
    )

    parser.add_argument('--duration', type=float, default=60.0,
                       help='采集时长（秒），默认60秒')
    parser.add_argument('--update-interval', type=float, default=5.0,
                       help='实时统计更新间隔（秒），默认5秒')

    # 真实位置参数
    parser.add_argument('--tag-id', type=int, default=None,
                       help='目标TAG ID（如果只关注特定TAG）')
    parser.add_argument('--true-x', type=float, default=None,
                       help='TAG真实位置 X 坐标（米）')
    parser.add_argument('--true-y', type=float, default=None,
                       help='TAG真实位置 Y 坐标（米）')
    parser.add_argument('--true-z', type=float, default=None,
                       help='TAG真实位置 Z 坐标（米）')

    args = parser.parse_args()

    # 构建真实位置字典
    true_position = None
    if args.true_x is not None and args.true_y is not None and args.true_z is not None:
        if args.tag_id is None:
            print("\033[93m⚠ Warning: --tag-id not specified, true position will not be used\033[0m")
        else:
            true_position = {args.tag_id: [args.true_x, args.true_y, args.true_z]}

    # 开始采集
    collect_uwb_statistics(
        duration=args.duration,
        true_position=true_position,
        target_tag_id=args.tag_id,
        update_interval=args.update_interval
    )


if __name__ == "__main__":
    main()
