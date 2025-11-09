#!/usr/bin/env python3
"""
UWB Real-time Data Visualizer with Noise Filtering

实时读取 /dev/ttyACM0 的 UWB 数据并可视化，支持可调滤波参数

使用方法:
    python visualize_live.py [--port /dev/ttyACM0] [--alpha 0.3] [--window 5]

参数:
    --port      串口设备路径 (默认: /dev/ttyACM0)
    --alpha     EMA滤波系数 (0-1, 越小越平滑, 默认: 0.3)
    --window    移动平均窗口大小 (默认: 5)
    --baudrate  波特率 (默认: 1500000)
"""

import struct
import serial
import time
import argparse
from collections import deque, defaultdict
from typing import Dict, List, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import threading
import numpy as np

# ================== 协议常量 ===================
MULTIPLY_VOLTAGE = 1000.0
MULTIPLY_POS = 1000.0

FRAME_HEADER = 0x55
FUNCTION_MARK = 0x00
TAIL_CHECK = 0xEE
FIXED_PART_SIZE = 896


# ================== 数据结构 ===================
class AnchorNode:
    ROLE_MAP = {1: "ANCHOR", 2: "TAG", 3: "CONSOLE"}

    def __init__(self, node_id, role, pos_3d, dis_arr):
        self.id = node_id
        self.role = role
        self.pos_3d = pos_3d
        self.dis_arr = dis_arr


class AnchorFrame0Result:
    ROLE_MAP = {1: "ANCHOR", 2: "TAG", 3: "CONSOLE"}

    def __init__(self):
        self.role = 0
        self.id = 0
        self.local_time = 0
        self.system_time = 0
        self.voltage = 0
        self.nodes = []


# ================== 滤波器类 ===================
class NoiseFilter:
    """可调参数的噪声滤波器，支持 EMA + 移动平均"""

    def __init__(self, alpha: float = 0.3, window_size: int = 5):
        """
        Args:
            alpha: EMA 滤波系数 (0-1)，越小越平滑但延迟越大
            window_size: 移动平均窗口大小
        """
        self.alpha = alpha
        self.window_size = window_size

        # 存储每个节点的历史数据
        self.ema_values: Dict[int, List[float]] = {}  # node_id -> [x, y, z]
        self.history: Dict[int, deque] = {}  # node_id -> deque of [x, y, z]

    def update_alpha(self, alpha: float):
        """动态调整 EMA 系数"""
        self.alpha = max(0.0, min(1.0, alpha))
        print(f"\033[93m[Filter] Alpha updated to {self.alpha:.2f}\033[0m")

    def update_window(self, window_size: int):
        """动态调整移动平均窗口"""
        self.window_size = max(1, window_size)
        print(f"\033[93m[Filter] Window size updated to {self.window_size}\033[0m")

    def filter_position(self, node_id: int, pos_3d: List[float]) -> List[float]:
        """
        对位置数据应用滤波

        策略: EMA (快速响应) + 移动平均 (平滑噪声)
        """
        # 初始化
        if node_id not in self.ema_values:
            self.ema_values[node_id] = pos_3d.copy()
            self.history[node_id] = deque(maxlen=self.window_size)
            self.history[node_id].append(pos_3d)
            return pos_3d

        # Step 1: EMA 滤波 (快速响应突变)
        ema = self.ema_values[node_id]
        for i in range(3):
            ema[i] = self.alpha * pos_3d[i] + (1 - self.alpha) * ema[i]

        # Step 2: 移动平均 (平滑高频噪声)
        self.history[node_id].append(ema.copy())
        history_array = np.array(self.history[node_id])
        smoothed = np.mean(history_array, axis=0).tolist()

        return smoothed

    def reset(self):
        """重置滤波器状态"""
        self.ema_values.clear()
        self.history.clear()


# ================== 数据解析 ===================
def parse_anchorframe0(data: bytes) -> AnchorFrame0Result:
    """解析 UWB 数据帧"""
    if len(data) < FIXED_PART_SIZE:
        return None
    if data[0] != FRAME_HEADER or data[1] != FUNCTION_MARK or data[FIXED_PART_SIZE - 1] != TAIL_CHECK:
        return None

    node_size = struct.calcsize("<BB" + "3s"*3 + "H"*8)
    result = AnchorFrame0Result()

    # 解析节点
    offset = 2
    for i in range(30):
        node_bytes = data[offset:offset + node_size]
        if len(node_bytes) < node_size:
            break

        node_id = node_bytes[0]
        if node_id == 0xFF:
            offset += node_size
            continue

        role = node_bytes[1]

        # pos_3d (3 × 24-bit signed int)
        pos_3d = []
        for j in range(3):
            start = 2 + 3 * j
            raw3 = node_bytes[start:start + 3]
            val = int.from_bytes(raw3, byteorder='little', signed=True)
            pos_3d.append(val / MULTIPLY_POS)

        # dis_arr (8 × uint16)
        dis_arr = list(struct.unpack_from("<8H", node_bytes, 2 + 9))
        dis_arr = [v / 100.0 for v in dis_arr]

        result.nodes.append(AnchorNode(node_id, role, pos_3d, dis_arr))
        offset += node_size

    # 解析元数据
    result.local_time = struct.unpack_from("<I", data, 2 + node_size * 30 + 67)[0]
    result.voltage = struct.unpack_from("<H", data, 2 + node_size * 30 + 67 + 4 + 4)[0] / MULTIPLY_VOLTAGE
    result.system_time = struct.unpack_from("<I", data, 2 + node_size * 30 + 67 + 4 + 4 + 2)[0]
    result.id = data[2 + node_size * 30 + 67 + 4 + 4 + 2 + 4]
    result.role = data[2 + node_size * 30 + 67 + 4 + 4 + 2 + 4 + 1]

    return result


# ================== 数据采集线程 ===================
class UWBDataCollector:
    """后台线程采集 UWB 数据"""

    def __init__(self, port: str, baudrate: int, noise_filter: NoiseFilter):
        self.port = port
        self.baudrate = baudrate
        self.filter = noise_filter

        # 数据缓冲 (最近 1000 个数据点)
        self.max_points = 1000
        self.timestamps = deque(maxlen=self.max_points)
        self.raw_data = defaultdict(lambda: {'x': deque(maxlen=self.max_points),
                                              'y': deque(maxlen=self.max_points),
                                              'z': deque(maxlen=self.max_points)})
        self.filtered_data = defaultdict(lambda: {'x': deque(maxlen=self.max_points),
                                                   'y': deque(maxlen=self.max_points),
                                                   'z': deque(maxlen=self.max_points)})
        self.voltage_history = deque(maxlen=self.max_points)

        self.running = False
        self.thread = None
        self.start_time = None
        self.frame_count = 0

    def start(self):
        """启动采集线程"""
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.thread.start()
        print(f"\033[92m[Collector] Started on {self.port}\033[0m")

    def stop(self):
        """停止采集"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print(f"\033[93m[Collector] Stopped\033[0m")

    def _collect_loop(self):
        """采集循环"""
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            buffer = bytearray()

            while self.running:
                data = ser.read(1024)
                if data:
                    buffer.extend(data)

                    # 搜索完整帧
                    while len(buffer) >= FIXED_PART_SIZE:
                        idx = buffer.find(bytes([FRAME_HEADER, FUNCTION_MARK]))
                        if idx < 0:
                            buffer.clear()
                            break

                        if len(buffer) - idx < FIXED_PART_SIZE:
                            break

                        frame = buffer[idx:idx + FIXED_PART_SIZE]
                        result = parse_anchorframe0(frame)

                        if result:
                            self._process_frame(result)

                        buffer = buffer[idx + FIXED_PART_SIZE:]

        except Exception as e:
            print(f"\033[91m[Collector] Error: {e}\033[0m")
        finally:
            ser.close()

    def _process_frame(self, result: AnchorFrame0Result):
        """处理单帧数据"""
        elapsed = time.time() - self.start_time
        self.timestamps.append(elapsed)
        self.voltage_history.append(result.voltage)
        self.frame_count += 1

        for node in result.nodes:
            # 原始数据
            self.raw_data[node.id]['x'].append(node.pos_3d[0])
            self.raw_data[node.id]['y'].append(node.pos_3d[1])
            self.raw_data[node.id]['z'].append(node.pos_3d[2])

            # 滤波后数据
            filtered_pos = self.filter.filter_position(node.id, node.pos_3d)
            self.filtered_data[node.id]['x'].append(filtered_pos[0])
            self.filtered_data[node.id]['y'].append(filtered_pos[1])
            self.filtered_data[node.id]['z'].append(filtered_pos[2])

        # 每 20 帧打印一次状态
        if self.frame_count % 20 == 0:
            print(f"\033[96m[{time.strftime('%H:%M:%S')}] Frame #{self.frame_count:05d} | "
                  f"Nodes: {len(result.nodes)} | Voltage: {result.voltage:.2f}V\033[0m")


# ================== 可视化 ===================
def create_live_plot(collector: UWBDataCollector):
    """创建交互式实时图表"""

    # 创建子图: 3D轨迹 + XYZ时间序列 + 电压
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=('3D Trajectory (Raw)', '3D Trajectory (Filtered)',
                        'X Position', 'Y Position',
                        'Z Position', 'Voltage'),
        specs=[[{'type': 'scatter3d'}, {'type': 'scatter3d'}],
               [{'type': 'scatter'}, {'type': 'scatter'}],
               [{'type': 'scatter'}, {'type': 'scatter'}]],
        vertical_spacing=0.08,
        horizontal_spacing=0.1
    )

    # 颜色映射
    color_map = {}
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'cyan', 'magenta', 'yellow']

    def update_plot():
        """更新图表数据"""
        fig.data = []

        # 获取当前所有节点 ID
        all_node_ids = set(list(collector.raw_data.keys()) + list(collector.filtered_data.keys()))

        for i, node_id in enumerate(sorted(all_node_ids)):
            if node_id not in color_map:
                color_map[node_id] = colors[i % len(colors)]
            color = color_map[node_id]

            # === 3D 轨迹 (原始) ===
            if node_id in collector.raw_data and len(collector.raw_data[node_id]['x']) > 0:
                fig.add_trace(
                    go.Scatter3d(
                        x=list(collector.raw_data[node_id]['x']),
                        y=list(collector.raw_data[node_id]['y']),
                        z=list(collector.raw_data[node_id]['z']),
                        mode='lines+markers',
                        name=f'Node {node_id} (Raw)',
                        line=dict(color=color, width=2),
                        marker=dict(size=3, color=color, opacity=0.5),
                        showlegend=True
                    ),
                    row=1, col=1
                )

            # === 3D 轨迹 (滤波) ===
            if node_id in collector.filtered_data and len(collector.filtered_data[node_id]['x']) > 0:
                fig.add_trace(
                    go.Scatter3d(
                        x=list(collector.filtered_data[node_id]['x']),
                        y=list(collector.filtered_data[node_id]['y']),
                        z=list(collector.filtered_data[node_id]['z']),
                        mode='lines+markers',
                        name=f'Node {node_id} (Filtered)',
                        line=dict(color=color, width=3),
                        marker=dict(size=4),
                        showlegend=True
                    ),
                    row=1, col=2
                )

        # === 时间序列 (只显示滤波后数据) ===
        timestamps = list(collector.timestamps)

        for node_id in sorted(all_node_ids):
            if node_id not in collector.filtered_data:
                continue

            color = color_map[node_id]

            # X 位置
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=list(collector.filtered_data[node_id]['x']),
                    mode='lines',
                    name=f'Node {node_id}',
                    line=dict(color=color, width=2),
                    showlegend=False
                ),
                row=2, col=1
            )

            # Y 位置
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=list(collector.filtered_data[node_id]['y']),
                    mode='lines',
                    name=f'Node {node_id}',
                    line=dict(color=color, width=2),
                    showlegend=False
                ),
                row=2, col=2
            )

            # Z 位置
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=list(collector.filtered_data[node_id]['z']),
                    mode='lines',
                    name=f'Node {node_id}',
                    line=dict(color=color, width=2),
                    showlegend=False
                ),
                row=3, col=1
            )

        # === 电压 ===
        if len(collector.voltage_history) > 0:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=list(collector.voltage_history),
                    mode='lines',
                    name='Voltage',
                    line=dict(color='red', width=2),
                    showlegend=False
                ),
                row=3, col=2
            )

        # 更新坐标轴标签
        fig.update_xaxes(title_text="Time (s)", row=2, col=1)
        fig.update_xaxes(title_text="Time (s)", row=2, col=2)
        fig.update_xaxes(title_text="Time (s)", row=3, col=1)
        fig.update_xaxes(title_text="Time (s)", row=3, col=2)

        fig.update_yaxes(title_text="X (m)", row=2, col=1)
        fig.update_yaxes(title_text="Y (m)", row=2, col=2)
        fig.update_yaxes(title_text="Z (m)", row=3, col=1)
        fig.update_yaxes(title_text="Voltage (V)", row=3, col=2)

        # 3D 图设置
        fig.update_scenes(
            xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title="Z (m)",
            aspectmode='data'
        )

        return fig

    # 初始显示
    fig = update_plot()
    fig.update_layout(
        height=1200,
        title_text=f"UWB Real-time Visualization (Alpha={collector.filter.alpha:.2f}, Window={collector.filter.window_size})",
        showlegend=True
    )

    fig.show()

    # 定期更新 (手动刷新浏览器或使用 dash 实现自动更新)
    print("\n\033[92m=== Visualization Started ===\033[0m")
    print("\033[93mTip: 手动刷新浏览器查看最新数据，或按 Ctrl+C 停止并重新生成图表\033[0m")
    print("\n\033[96m调整滤波参数示例:\033[0m")
    print("  collector.filter.update_alpha(0.5)  # 更快响应")
    print("  collector.filter.update_window(10)  # 更平滑")

    try:
        while True:
            time.sleep(5)
            fig = update_plot()
            fig.update_layout(
                title_text=f"UWB Real-time Visualization (Alpha={collector.filter.alpha:.2f}, Window={collector.filter.window_size})"
            )
            fig.write_html('/tmp/uwb_live.html')
            print(f"\033[96m[{time.strftime('%H:%M:%S')}] Plot updated -> /tmp/uwb_live.html\033[0m")

    except KeyboardInterrupt:
        print("\n\033[93mVisualization stopped\033[0m")


# ================== 主程序 ===================
def main():
    parser = argparse.ArgumentParser(description='UWB Real-time Data Visualizer with Noise Filtering')
    parser.add_argument('--port', default='/dev/ttyACM0', help='Serial port (default: /dev/ttyACM0)')
    parser.add_argument('--baudrate', type=int, default=1500000, help='Baudrate (default: 1500000)')
    parser.add_argument('--alpha', type=float, default=0.3, help='EMA filter alpha (0-1, default: 0.3)')
    parser.add_argument('--window', type=int, default=5, help='Moving average window (default: 5)')

    args = parser.parse_args()

    # 初始化滤波器
    noise_filter = NoiseFilter(alpha=args.alpha, window_size=args.window)

    # 初始化采集器
    collector = UWBDataCollector(args.port, args.baudrate, noise_filter)

    print("\033[96m" + "="*60 + "\033[0m")
    print("\033[92m       UWB Real-time Visualizer with Noise Filtering\033[0m")
    print("\033[96m" + "="*60 + "\033[0m")
    print(f"\033[93mPort:\033[0m       {args.port}")
    print(f"\033[93mBaudrate:\033[0m   {args.baudrate}")
    print(f"\033[93mEMA Alpha:\033[0m  {args.alpha:.2f} (越小越平滑)")
    print(f"\033[93mMA Window:\033[0m  {args.window} (移动平均窗口)")
    print("\033[96m" + "="*60 + "\033[0m\n")

    try:
        # 启动采集
        collector.start()

        # 等待一些数据
        print("\033[93mCollecting initial data (5 seconds)...\033[0m")
        time.sleep(5)

        # 启动可视化
        create_live_plot(collector)

    except KeyboardInterrupt:
        print("\n\033[93mStopping...\033[0m")

    finally:
        collector.stop()
        print("\033[92mDone!\033[0m")


if __name__ == "__main__":
    main()
