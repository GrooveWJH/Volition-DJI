#!/usr/bin/env python3
"""
UWB Data Receiver with Real-time Smoothing & Web Visualization
实时接收并平滑 UWB 定位数据，通过 Web 界面可视化

功能:
    1. 实时数据接收和平滑
    2. Plotly Dash Web 可视化
    3. 原始数据 vs 平滑数据对比
    4. 仅显示 X/Y 平面 (忽略 Z 轴)

运行:
    python uwb/getdata_smoothed_web.py
    然后打开浏览器访问 http://localhost:8050
"""

import struct
import serial
import time
from typing import List, Optional, Deque
from collections import deque
import numpy as np
import threading
from datetime import datetime

# Dash and Plotly
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
from plotly.subplots import make_subplots

# ================== Protocol Constants ===================
MULTIPLY_VOLTAGE = 1000.0
MULTIPLY_POS = 1000.0

FRAME_HEADER = 0x55
FUNCTION_MARK = 0x00
TAIL_CHECK = 0xEE
FIXED_PART_SIZE = 896

NODE_SIZE = struct.calcsize("<BB" + "3s"*3 + "H"*8)
MAX_NODES = 30

# ================== Configuration ===================
SERIAL_PORT = "/dev/ttyACM0"
BAUDRATE = 1500000

# ================== Default Filter Parameters ===================
DEFAULT_FILTER_WINDOW_X = 5
DEFAULT_FILTER_WINDOW_Y = 3
DEFAULT_OUTLIER_THRESHOLD_X = 0.085
DEFAULT_OUTLIER_THRESHOLD_Y = 0.039

# ================== Visualization Config ===================
MAX_POINTS = 500  # 最多显示的历史点数
UPDATE_INTERVAL_MS = 100  # Web 刷新间隔 (ms)


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
        self.pos_3d = pos_3d
        self.dis_arr = dis_arr


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
        if len(self.buffer) >= 3:
            mean = np.mean(self.buffer)
            if abs(new_value - mean) > self.outlier_threshold:
                new_value = self.last_valid_value if self.last_valid_value is not None else new_value

        self.buffer.append(new_value)
        self.last_valid_value = new_value
        return float(np.mean(self.buffer))


class PositionSmoother:
    """2D 位置平滑器（仅 X/Y）"""
    def __init__(self, window_x=DEFAULT_FILTER_WINDOW_X, window_y=DEFAULT_FILTER_WINDOW_Y,
                 threshold_x=DEFAULT_OUTLIER_THRESHOLD_X, threshold_y=DEFAULT_OUTLIER_THRESHOLD_Y):
        self.filter_x = MovingAverageFilter(window_x, threshold_x)
        self.filter_y = MovingAverageFilter(window_y, threshold_y)

    def update(self, x: float, y: float) -> tuple:
        smoothed_x = self.filter_x.update(x)
        smoothed_y = self.filter_y.update(y)
        return smoothed_x, smoothed_y


# ================== Global Data Storage ===================
class DataStore:
    """全局数据存储（线程安全）"""
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}  # {node_id: {'timestamps': [], 'raw_x': [], 'raw_y': [], 'smooth_x': [], 'smooth_y': []}}
        self.smoothers = {}
        self.frame_count = 0
        self.voltage = 0.0
        self.running = True
        # 平滑器参数（可动态调整）
        self.filter_window_x = DEFAULT_FILTER_WINDOW_X
        self.filter_window_y = DEFAULT_FILTER_WINDOW_Y
        self.outlier_threshold_x = DEFAULT_OUTLIER_THRESHOLD_X
        self.outlier_threshold_y = DEFAULT_OUTLIER_THRESHOLD_Y

    def update_filter_params(self, window_x, window_y, threshold_x, threshold_y):
        """更新平滑器参数并重新创建所有 smoother"""
        with self.lock:
            self.filter_window_x = window_x
            self.filter_window_y = window_y
            self.outlier_threshold_x = threshold_x
            self.outlier_threshold_y = threshold_y
            # 重新创建所有 smoother
            self.smoothers.clear()

    def get_filter_params(self):
        """获取当前平滑器参数"""
        with self.lock:
            return {
                'window_x': self.filter_window_x,
                'window_y': self.filter_window_y,
                'threshold_x': self.outlier_threshold_x,
                'threshold_y': self.outlier_threshold_y
            }

    def add_data(self, node_id: int, raw_x: float, raw_y: float, smooth_x: float, smooth_y: float):
        with self.lock:
            if node_id not in self.data:
                self.data[node_id] = {
                    'timestamps': deque(maxlen=MAX_POINTS),
                    'raw_x': deque(maxlen=MAX_POINTS),
                    'raw_y': deque(maxlen=MAX_POINTS),
                    'smooth_x': deque(maxlen=MAX_POINTS),
                    'smooth_y': deque(maxlen=MAX_POINTS),
                }

            now = time.time()
            self.data[node_id]['timestamps'].append(now)
            self.data[node_id]['raw_x'].append(raw_x)
            self.data[node_id]['raw_y'].append(raw_y)
            self.data[node_id]['smooth_x'].append(smooth_x)
            self.data[node_id]['smooth_y'].append(smooth_y)

    def get_data(self, node_id: int):
        with self.lock:
            if node_id in self.data:
                return {
                    'timestamps': list(self.data[node_id]['timestamps']),
                    'raw_x': list(self.data[node_id]['raw_x']),
                    'raw_y': list(self.data[node_id]['raw_y']),
                    'smooth_x': list(self.data[node_id]['smooth_x']),
                    'smooth_y': list(self.data[node_id]['smooth_y']),
                }
            return None

    def get_all_nodes(self):
        with self.lock:
            return list(self.data.keys())


# Global instance
data_store = DataStore()


# ================== Frame Parser ===================
def parse_24bit_signed(data: bytes) -> int:
    return int.from_bytes(data, byteorder='little', signed=True)


def parse_node(node_bytes: bytes) -> Optional[AnchorNode]:
    if len(node_bytes) < NODE_SIZE:
        return None

    node_id = node_bytes[0]
    if node_id == 0xFF:
        return None

    role = node_bytes[1]

    pos_3d = []
    for i in range(3):
        offset = 2 + 3 * i
        raw_bytes = node_bytes[offset:offset + 3]
        value = parse_24bit_signed(raw_bytes) / MULTIPLY_POS
        pos_3d.append(value)

    dis_arr = list(struct.unpack_from("<8H", node_bytes, 11))
    dis_arr = [d / 100.0 for d in dis_arr]

    return AnchorNode(node_id, role, pos_3d, dis_arr)


def parse_uwb_frame(data: bytes) -> Optional[UWBFrame]:
    if len(data) < FIXED_PART_SIZE:
        return None
    if data[0] != FRAME_HEADER or data[1] != FUNCTION_MARK:
        return None
    if data[FIXED_PART_SIZE - 1] != TAIL_CHECK:
        return None

    frame = UWBFrame()

    offset = 2
    for _ in range(MAX_NODES):
        node_bytes = data[offset:offset + NODE_SIZE]
        node = parse_node(node_bytes)
        if node:
            frame.nodes.append(node)
        offset += NODE_SIZE

    meta_base = 2 + NODE_SIZE * MAX_NODES + 67
    frame.local_time = struct.unpack_from("<I", data, meta_base)[0]
    frame.voltage = struct.unpack_from("<H", data, meta_base + 8)[0] / MULTIPLY_VOLTAGE
    frame.system_time = struct.unpack_from("<I", data, meta_base + 10)[0]
    frame.id = data[meta_base + 14]
    frame.role = data[meta_base + 15]

    return frame


# ================== Serial Reader Thread ===================
def serial_reader_thread():
    """后台线程：持续读取串口数据"""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
        print(f"\033[92m✓ Serial port {SERIAL_PORT} opened at {BAUDRATE} baud\033[0m")
    except Exception as e:
        print(f"\033[91m✗ Failed to open serial port {SERIAL_PORT}: {e}\033[0m")
        data_store.running = False
        return

    buffer = bytearray()

    try:
        while data_store.running:
            data = ser.read(1024)
            if data:
                buffer.extend(data)

            while len(buffer) >= FIXED_PART_SIZE:
                idx = buffer.find(bytes([FRAME_HEADER, FUNCTION_MARK]))
                if idx < 0:
                    buffer.clear()
                    break

                if len(buffer) - idx < FIXED_PART_SIZE:
                    break

                frame_data = buffer[idx:idx + FIXED_PART_SIZE]
                frame = parse_uwb_frame(frame_data)

                if frame:
                    data_store.frame_count += 1
                    data_store.voltage = frame.voltage

                    for node in frame.nodes:
                        if node.id not in data_store.smoothers:
                            params = data_store.get_filter_params()
                            data_store.smoothers[node.id] = PositionSmoother(
                                window_x=params['window_x'],
                                window_y=params['window_y'],
                                threshold_x=params['threshold_x'],
                                threshold_y=params['threshold_y']
                            )

                        raw_x, raw_y = node.pos_3d[0], node.pos_3d[1]
                        smoothed_x, smoothed_y = data_store.smoothers[node.id].update(raw_x, raw_y)

                        data_store.add_data(node.id, raw_x, raw_y, smoothed_x, smoothed_y)

                buffer = buffer[idx + FIXED_PART_SIZE:]

    except Exception as e:
        print(f"\033[91m✗ Serial reader error: {e}\033[0m")
    finally:
        ser.close()
        print("\033[92m✓ Serial port closed\033[0m")


# ================== Dash Web App ===================
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("🎯 UWB Real-time Position Tracking (X/Y Plane)",
            style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': 20}),

    html.Div([
        html.Div([
            html.Label("Select Node ID:", style={'fontWeight': 'bold', 'marginRight': 10}),
            dcc.Dropdown(
                id='node-selector',
                options=[],
                value=None,
                style={'width': '200px', 'display': 'inline-block'}
            ),
        ], style={'marginBottom': 20}),

        html.Div(id='stats-display', style={
            'padding': '15px',
            'backgroundColor': '#ecf0f1',
            'borderRadius': '5px',
            'marginBottom': 20,
            'fontSize': '14px'
        }),

        # 平滑器参数控制面板
        html.Div([
            html.H3("⚙️ Filter Parameters", style={'color': '#34495e', 'marginBottom': 10}),

            html.Div([
                html.Label("X Window Size:", style={'fontWeight': 'bold', 'marginRight': 10}),
                dcc.Slider(
                    id='slider-window-x',
                    min=1, max=20, step=1,
                    value=DEFAULT_FILTER_WINDOW_X,
                    marks={i: str(i) for i in range(1, 21, 2)},
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
            ], style={'marginBottom': 15}),

            html.Div([
                html.Label("Y Window Size:", style={'fontWeight': 'bold', 'marginRight': 10}),
                dcc.Slider(
                    id='slider-window-y',
                    min=1, max=20, step=1,
                    value=DEFAULT_FILTER_WINDOW_Y,
                    marks={i: str(i) for i in range(1, 21, 2)},
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
            ], style={'marginBottom': 15}),

            html.Div([
                html.Label("X Outlier Threshold (m):", style={'fontWeight': 'bold', 'marginRight': 10}),
                dcc.Slider(
                    id='slider-threshold-x',
                    min=0.001, max=0.5, step=0.001,
                    value=DEFAULT_OUTLIER_THRESHOLD_X,
                    marks={i/100: f'{i/100:.2f}' for i in range(0, 51, 10)},
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
            ], style={'marginBottom': 15}),

            html.Div([
                html.Label("Y Outlier Threshold (m):", style={'fontWeight': 'bold', 'marginRight': 10}),
                dcc.Slider(
                    id='slider-threshold-y',
                    min=0.001, max=0.5, step=0.001,
                    value=DEFAULT_OUTLIER_THRESHOLD_Y,
                    marks={i/100: f'{i/100:.2f}' for i in range(0, 51, 10)},
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
            ], style={'marginBottom': 15}),
        ], style={
            'padding': '15px',
            'backgroundColor': '#e8f4f8',
            'borderRadius': '5px',
            'marginBottom': 20
        }),
    ], style={'padding': '20px'}),

    dcc.Graph(id='trajectory-plot', style={'height': '400px'}),
    dcc.Graph(id='timeseries-plot', style={'height': '500px'}),

    # Hidden div to store filter parameter update status
    html.Div(id='filter-params-updated', style={'display': 'none'}),

    dcc.Interval(
        id='interval-component',
        interval=UPDATE_INTERVAL_MS,
        n_intervals=0
    )
], style={'fontFamily': 'Arial, sans-serif', 'padding': '20px'})


@app.callback(
    Output('node-selector', 'options'),
    Output('node-selector', 'value'),
    Input('interval-component', 'n_intervals')
)
def update_node_list(n):
    """更新节点列表"""
    nodes = data_store.get_all_nodes()
    options = [{'label': f'Node {nid}', 'value': nid} for nid in sorted(nodes)]

    # 默认选择第一个节点
    value = sorted(nodes)[0] if nodes else None

    return options, value


# 单独的回调用于更新平滑器参数
@app.callback(
    Output('filter-params-updated', 'children'),
    Input('slider-window-x', 'value'),
    Input('slider-window-y', 'value'),
    Input('slider-threshold-x', 'value'),
    Input('slider-threshold-y', 'value'),
    prevent_initial_call=True
)
def update_filter_params(window_x, window_y, threshold_x, threshold_y):
    """更新平滑器参数"""
    if window_x is not None and window_y is not None and threshold_x is not None and threshold_y is not None:
        data_store.update_filter_params(window_x, window_y, threshold_x, threshold_y)
        return f'Updated: X-win={window_x}, Y-win={window_y}, X-th={threshold_x:.3f}, Y-th={threshold_y:.3f}'
    return 'Not updated'


@app.callback(
    Output('stats-display', 'children'),
    Input('interval-component', 'n_intervals'),
    Input('node-selector', 'value')
)
def update_stats(n, node_id):
    """更新统计信息"""
    if node_id is None:
        return "⏳ Waiting for data..."

    data = data_store.get_data(node_id)
    if not data or len(data['raw_x']) == 0:
        return "📊 No data available for this node"

    # 计算统计量
    raw_x_arr = np.array(data['raw_x'])
    raw_y_arr = np.array(data['raw_y'])
    smooth_x_arr = np.array(data['smooth_x'])
    smooth_y_arr = np.array(data['smooth_y'])

    return html.Div([
        html.Div([
            html.Span(f"📡 Frame Count: {data_store.frame_count} | ", style={'marginRight': 15}),
            html.Span(f"🔋 Voltage: {data_store.voltage:.2f}V | ", style={'marginRight': 15}),
            html.Span(f"📍 Node ID: {node_id} | ", style={'marginRight': 15}),
            html.Span(f"📊 Data Points: {len(data['raw_x'])}", style={'marginRight': 15}),
        ], style={'marginBottom': 10}),

        html.Div([
            html.B("Raw Data: "),
            f"X: {raw_x_arr[-1]:.4f}m (σ={np.std(raw_x_arr)*1000:.1f}mm), ",
            f"Y: {raw_y_arr[-1]:.4f}m (σ={np.std(raw_y_arr)*1000:.1f}mm)"
        ], style={'marginBottom': 5, 'color': '#e74c3c'}),

        html.Div([
            html.B("Smoothed: "),
            f"X: {smooth_x_arr[-1]:.4f}m (σ={np.std(smooth_x_arr)*1000:.1f}mm), ",
            f"Y: {smooth_y_arr[-1]:.4f}m (σ={np.std(smooth_y_arr)*1000:.1f}mm)"
        ], style={'color': '#27ae60'}),
    ])


@app.callback(
    Output('trajectory-plot', 'figure'),
    Input('interval-component', 'n_intervals'),
    Input('node-selector', 'value')
)
def update_trajectory(n, node_id):
    """更新 2D 轨迹图（X-Y 平面）with time-based transparency"""
    if node_id is None:
        return go.Figure()

    data = data_store.get_data(node_id)
    if not data or len(data['raw_x']) == 0:
        return go.Figure()

    fig = go.Figure()

    # 计算基于时间的透明度
    timestamps = np.array(data['timestamps'])
    if len(timestamps) > 1:
        # 归一化时间到 [0, 1]，最新的为 1，最旧的为 0
        time_normalized = (timestamps - timestamps[0]) / (timestamps[-1] - timestamps[0] + 1e-6)
        # 透明度从 0.2 到 1.0
        alpha_values = 0.2 + 0.8 * time_normalized
    else:
        alpha_values = np.ones(len(timestamps))

    # 原始轨迹（散点）with gradient transparency
    raw_colors = [f'rgba(231, 76, 60, {alpha:.2f})' for alpha in alpha_values]
    fig.add_trace(go.Scatter(
        x=data['raw_x'],
        y=data['raw_y'],
        mode='markers',
        name='Raw Data',
        marker=dict(size=4, color=raw_colors, symbol='circle'),
    ))

    # 平滑轨迹（线条 + 标记）with gradient transparency
    smooth_colors = [f'rgba(39, 174, 96, {alpha:.2f})' for alpha in alpha_values]
    fig.add_trace(go.Scatter(
        x=data['smooth_x'],
        y=data['smooth_y'],
        mode='lines+markers',
        name='Smoothed Data',
        line=dict(color='rgba(39, 174, 96, 0.7)', width=2),
        marker=dict(size=6, symbol='diamond', color=smooth_colors),
    ))

    # 当前位置标记
    if len(data['smooth_x']) > 0:
        fig.add_trace(go.Scatter(
            x=[data['smooth_x'][-1]],
            y=[data['smooth_y'][-1]],
            mode='markers',
            name='Current Position',
            marker=dict(size=15, color='#3498db', symbol='star', line=dict(width=2, color='white')),
        ))

    fig.update_layout(
        title=f"2D Trajectory - Node {node_id} (X-Y Plane)",
        xaxis_title="X Position (m)",
        yaxis_title="Y Position (m)",
        hovermode='closest',
        legend=dict(x=0.01, y=0.99),
        plot_bgcolor='#f8f9fa',
        xaxis=dict(gridcolor='#dee2e6'),
        yaxis=dict(gridcolor='#dee2e6', scaleanchor="x", scaleratio=1),
    )

    return fig


@app.callback(
    Output('timeseries-plot', 'figure'),
    Input('interval-component', 'n_intervals'),
    Input('node-selector', 'value')
)
def update_timeseries(n, node_id):
    """更新时间序列图"""
    if node_id is None:
        return go.Figure()

    data = data_store.get_data(node_id)
    if not data or len(data['raw_x']) == 0:
        return go.Figure()

    # 转换时间戳为相对时间（秒）
    if len(data['timestamps']) > 0:
        t0 = data['timestamps'][0]
        relative_time = [(t - t0) for t in data['timestamps']]
    else:
        relative_time = []

    # 创建子图（2行1列）
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('X Position vs Time', 'Y Position vs Time'),
        vertical_spacing=0.12
    )

    # X 轴时间序列
    fig.add_trace(go.Scatter(
        x=relative_time, y=data['raw_x'],
        mode='lines', name='Raw X', line=dict(color='rgba(231, 76, 60, 0.5)', width=1)
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=relative_time, y=data['smooth_x'],
        mode='lines', name='Smooth X', line=dict(color='#27ae60', width=2)
    ), row=1, col=1)

    # Y 轴时间序列
    fig.add_trace(go.Scatter(
        x=relative_time, y=data['raw_y'],
        mode='lines', name='Raw Y', line=dict(color='rgba(52, 152, 219, 0.5)', width=1),
        showlegend=False
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=relative_time, y=data['smooth_y'],
        mode='lines', name='Smooth Y', line=dict(color='#e67e22', width=2),
        showlegend=False
    ), row=2, col=1)

    fig.update_xaxes(title_text="Time (s)", row=2, col=1)
    fig.update_yaxes(title_text="X Position (m)", row=1, col=1)
    fig.update_yaxes(title_text="Y Position (m)", row=2, col=1)

    fig.update_layout(
        height=500,
        hovermode='x unified',
        plot_bgcolor='#f8f9fa',
        legend=dict(x=0.01, y=0.99),
    )

    return fig


# ================== Main Entry ===================
if __name__ == '__main__':
    print("\033[96m" + "="*80 + "\033[0m")
    print("\033[92m        UWB Real-time Data Visualization with Smoothing\033[0m")
    print("\033[96m" + "="*80 + "\033[0m")
    print(f"  🔧 Default Filter: X-Window={DEFAULT_FILTER_WINDOW_X}, Y-Window={DEFAULT_FILTER_WINDOW_Y}")
    print(f"  🎛️  Adjustable via Web UI sliders")
    print(f"  📊 Max Points: {MAX_POINTS}")
    print(f"  🌐 Web Server: http://localhost:8050")
    print(f"  ✨ Features: Real-time parameter tuning + Time-based trajectory fading")
    print("\033[96m" + "="*80 + "\033[0m\n")

    # 启动串口读取线程
    reader_thread = threading.Thread(target=serial_reader_thread, daemon=True)
    reader_thread.start()

    # 启动 Web 服务器
    try:
        app.run(debug=False, host='0.0.0.0', port=8050)
    except KeyboardInterrupt:
        print("\n\033[93m✓ Shutting down...\033[0m")
        data_store.running = False
        reader_thread.join(timeout=2)
