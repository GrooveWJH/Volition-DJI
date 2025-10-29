#!/usr/bin/env python3
"""
通用数据可视化工具
支持多种控制数据的可视化分析

功能：
- 读取control模块生成的CSV数据
- 使用Plotly生成交互式图表
- 支持平面+Yaw和Yaw单独控制数据
- 自动检测数据类型并生成相应图表

使用方法：
    python control/visualize.py data/20240315_143022          # 平面+Yaw数据
    python control/visualize.py data/yaw/20240315_143022      # Yaw单独数据
"""

import sys
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_data(log_dir):
    """从日志目录加载CSV数据"""
    # 尝试多种可能的CSV文件名
    possible_files = [
        'control_data.csv',      # 平面+Yaw控制数据
        'yaw_control_data.csv'   # Yaw单独控制数据
    ]

    csv_path = None
    for filename in possible_files:
        test_path = os.path.join(log_dir, filename)
        if os.path.exists(test_path):
            csv_path = test_path
            break

    if csv_path is None:
        raise FileNotFoundError(f"找不到数据文件，检查目录: {log_dir}")

    df = pd.read_csv(csv_path)

    # 转换时间戳为相对时间（从0开始，单位：秒）
    df['time'] = df['timestamp'] - df['timestamp'].iloc[0]

    return df, os.path.basename(csv_path)


def detect_data_type(df):
    """检测数据类型"""
    if 'target_x' in df.columns and 'target_y' in df.columns:
        return 'plane_yaw'
    elif 'target_yaw' in df.columns and 'target_index' in df.columns:
        return 'yaw_only'
    else:
        return 'unknown'


def create_plane_yaw_plot(df, title="平面+Yaw控制分析"):
    """创建平面+Yaw控制可视化图表"""
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            'X轴跟踪', 'Y轴跟踪',
            'Yaw角跟踪', '距离误差',
            'XY杆量输出', 'Yaw杆量输出'
        ),
        vertical_spacing=0.08,
        horizontal_spacing=0.08
    )

    # X轴跟踪
    fig.add_trace(go.Scatter(x=df['time'], y=df['target_x'], mode='lines',
                            name='目标X', line=dict(color='red', dash='dash')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['current_x'], mode='lines',
                            name='当前X', line=dict(color='blue')), row=1, col=1)

    # Y轴跟踪
    fig.add_trace(go.Scatter(x=df['time'], y=df['target_y'], mode='lines',
                            name='目标Y', line=dict(color='red', dash='dash')), row=1, col=2)
    fig.add_trace(go.Scatter(x=df['time'], y=df['current_y'], mode='lines',
                            name='当前Y', line=dict(color='green')), row=1, col=2)

    # Yaw角跟踪
    fig.add_trace(go.Scatter(x=df['time'], y=df['target_yaw'], mode='lines',
                            name='目标Yaw', line=dict(color='red', dash='dash')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['current_yaw'], mode='lines',
                            name='当前Yaw', line=dict(color='cyan')), row=2, col=1)

    # 距离误差
    fig.add_trace(go.Scatter(x=df['time'], y=df['distance'], mode='lines',
                            name='距离误差', line=dict(color='orange')), row=2, col=2)

    # XY杆量输出
    fig.add_trace(go.Scatter(x=df['time'], y=df['roll_absolute'], mode='lines',
                            name='Roll杆量', line=dict(color='purple')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['pitch_absolute'], mode='lines',
                            name='Pitch杆量', line=dict(color='brown')), row=3, col=1)

    # Yaw杆量输出
    fig.add_trace(go.Scatter(x=df['time'], y=df['yaw_absolute'], mode='lines',
                            name='Yaw杆量', line=dict(color='purple')), row=3, col=2)

    # 添加中位线（1024）
    for row in [3]:
        for col in [1, 2]:
            fig.add_hline(y=1024, line_dash="dash", line_color="gray", opacity=0.5,
                         annotation_text="中位 (1024)", row=row, col=col)

    # 更新轴标签
    for row in range(1, 4):
        for col in range(1, 3):
            fig.update_xaxes(title_text="时间 (秒)", row=row, col=col)

    # Y轴标签
    fig.update_yaxes(title_text="位置 (米)", row=1, col=1)
    fig.update_yaxes(title_text="位置 (米)", row=1, col=2)
    fig.update_yaxes(title_text="角度 (度)", row=2, col=1)
    fig.update_yaxes(title_text="距离 (米)", row=2, col=2)
    fig.update_yaxes(title_text="杆量值", row=3, col=1)
    fig.update_yaxes(title_text="杆量值", row=3, col=2)

    fig.update_layout(title=title, showlegend=True, height=900, hovermode='x unified', template='plotly_white')
    return fig


def create_yaw_only_plot(df, title="Yaw角控制分析"):
    """创建Yaw单独控制可视化图表"""
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Yaw角跟踪', 'Yaw杆量输出'),
        vertical_spacing=0.12,
        row_heights=[0.5, 0.5]
    )

    # Yaw角跟踪
    fig.add_trace(go.Scatter(x=df['time'], y=df['target_yaw'], mode='lines',
                            name='目标Yaw角', line=dict(color='red', dash='dash', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['current_yaw'], mode='lines',
                            name='当前Yaw角', line=dict(color='cyan', width=2)), row=1, col=1)

    # Yaw杆量输出
    fig.add_trace(go.Scatter(x=df['time'], y=df['yaw_absolute'], mode='lines',
                            name='Yaw杆量', line=dict(color='purple', width=2)), row=2, col=1)

    # 添加中位线（1024）
    fig.add_hline(y=1024, line_dash="dash", line_color="gray", opacity=0.5,
                 annotation_text="中位 (1024)", row=2, col=1)

    # 更新轴标签
    fig.update_xaxes(title_text="时间 (秒)", row=1, col=1)
    fig.update_xaxes(title_text="时间 (秒)", row=2, col=1)
    fig.update_yaxes(title_text="角度 (度)", row=1, col=1)
    fig.update_yaxes(title_text="杆量值", row=2, col=1)

    fig.update_layout(title=title, showlegend=True, height=800, hovermode='x unified', template='plotly_white')
    return fig


def print_plane_yaw_statistics(df):
    """打印平面+Yaw控制统计信息"""
    print("\n" + "="*60)
    print("平面+Yaw控制统计信息")
    print("="*60)

    # XY位置误差统计
    error_x_abs = df['error_x'].abs()
    error_y_abs = df['error_y'].abs()
    print(f"\n【XY位置误差】")
    print(f"  X轴平均误差: {error_x_abs.mean():.4f}m")
    print(f"  Y轴平均误差: {error_y_abs.mean():.4f}m")
    print(f"  平均距离误差: {df['distance'].mean():.4f}m")
    print(f"  最大距离误差: {df['distance'].max():.4f}m")

    # Yaw角误差统计
    error_yaw_abs = df['error_yaw'].abs()
    print(f"\n【Yaw角误差】")
    print(f"  平均误差: {error_yaw_abs.mean():.3f}°")
    print(f"  最大误差: {error_yaw_abs.max():.3f}°")
    print(f"  误差标准差: {df['error_yaw'].std():.3f}°")

    # 杆量统计
    print(f"\n【杆量输出】")
    print(f"  Roll杆量: {df['roll_absolute'].min():.0f} ~ {df['roll_absolute'].max():.0f}")
    print(f"  Pitch杆量: {df['pitch_absolute'].min():.0f} ~ {df['pitch_absolute'].max():.0f}")
    print(f"  Yaw杆量: {df['yaw_absolute'].min():.0f} ~ {df['yaw_absolute'].max():.0f}")


def print_yaw_only_statistics(df):
    """打印Yaw单独控制统计信息"""
    print("\n" + "="*60)
    print("Yaw角控制统计信息")
    print("="*60)

    # 误差统计
    error_abs = df['error_yaw'].abs()
    print(f"\n【Yaw角误差】")
    print(f"  平均误差: {error_abs.mean():.3f}°")
    print(f"  最大误差: {error_abs.max():.3f}°")
    print(f"  误差标准差: {df['error_yaw'].std():.3f}°")

    # 杆量统计
    print(f"\n【Yaw杆量】")
    print(f"  平均值: {df['yaw_absolute'].mean():.1f}")
    print(f"  最大值: {df['yaw_absolute'].max():.1f}")
    print(f"  最小值: {df['yaw_absolute'].min():.1f}")
    print(f"  偏移范围: {df['yaw_offset'].min():.1f} ~ {df['yaw_offset'].max():.1f}")


def print_common_statistics(df):
    """打印通用统计信息"""
    # 控制周期
    time_diffs = df['time'].diff().dropna()
    print(f"\n【控制周期】")
    print(f"  平均周期: {time_diffs.mean()*1000:.2f} ms")
    print(f"  实际频率: {1/time_diffs.mean():.1f} Hz")

    # 总时长
    print(f"\n【总时长】")
    print(f"  {df['time'].iloc[-1]:.2f} 秒")
    print(f"  数据点数: {len(df)}")
    print("\n" + "="*60)


def main():
    if len(sys.argv) < 2:
        print("用法: python control/visualize.py <日志目录>")
        print("示例:")
        print("  python control/visualize.py data/20240315_143022          # 平面+Yaw数据")
        print("  python control/visualize.py data/yaw/20240315_143022      # Yaw单独数据")
        sys.exit(1)

    log_dir = sys.argv[1]

    print(f"正在加载数据: {log_dir}")
    df, csv_filename = load_data(log_dir)
    data_type = detect_data_type(df)
    print(f"数据加载完成！共 {len(df)} 条记录")
    print(f"数据类型: {data_type}")
    print(f"CSV文件: {csv_filename}\n")

    # 打印统计信息
    if data_type == 'plane_yaw':
        print_plane_yaw_statistics(df)
        print_common_statistics(df)
        # 创建图表
        print("\n正在生成平面+Yaw控制图表...")
        fig = create_plane_yaw_plot(df, title=f"平面+Yaw控制分析 - {os.path.basename(log_dir)}")
    elif data_type == 'yaw_only':
        print_yaw_only_statistics(df)
        print_common_statistics(df)
        # 创建图表
        print("\n正在生成Yaw角控制图表...")
        fig = create_yaw_only_plot(df, title=f"Yaw角控制分析 - {os.path.basename(log_dir)}")
    else:
        print(f"未知的数据类型: {data_type}")
        print("支持的列名:", list(df.columns))
        sys.exit(1)

    # 保存HTML文件
    html_filename = f"{data_type}_analysis.html"
    html_path = os.path.join(log_dir, html_filename)
    fig.write_html(html_path)
    print(f"图表已保存: {html_path}")

    # 在浏览器中打开
    fig.show()


if __name__ == '__main__':
    main()