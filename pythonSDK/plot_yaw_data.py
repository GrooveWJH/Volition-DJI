#!/usr/bin/env python3
"""
Yaw角PID数据可视化工具

功能：
- 读取control_yaw.py生成的CSV数据
- 使用Plotly生成交互式图表
- 显示Yaw角跟踪和杆量输出

使用方法：
    python plot_yaw_data.py data/yaw/20240315_143022
"""

import sys
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_data(log_dir):
    """从日志目录加载CSV数据"""
    csv_path = os.path.join(log_dir, 'yaw_control_data.csv')
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"找不到数据文件: {csv_path}")

    df = pd.read_csv(csv_path)

    # 转换时间戳为相对时间（从0开始，单位：秒）
    df['time'] = df['timestamp'] - df['timestamp'].iloc[0]

    return df


def create_plot(df, title="Yaw角PID控制分析"):
    """创建Yaw角可视化图表"""

    # 创建2行1列的子图
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            'Yaw角跟踪',
            'Yaw杆量输出'
        ),
        vertical_spacing=0.12,
        row_heights=[0.5, 0.5]
    )

    # 子图1: Yaw角跟踪
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['target_yaw'],
            mode='lines',
            name='目标Yaw角',
            line=dict(color='red', dash='dash', width=2)
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['current_yaw'],
            mode='lines',
            name='当前Yaw角',
            line=dict(color='cyan', width=2)
        ),
        row=1, col=1
    )

    # 子图2: Yaw杆量输出
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['yaw_absolute'],
            mode='lines',
            name='Yaw杆量',
            line=dict(color='purple', width=2)
        ),
        row=2, col=1
    )

    # 添加中位线（1024）
    fig.add_hline(
        y=1024,
        line_dash="dash",
        line_color="gray",
        opacity=0.5,
        annotation_text="中位 (1024)",
        row=2, col=1
    )

    # 更新X轴标签
    fig.update_xaxes(title_text="时间 (秒)", row=1, col=1)
    fig.update_xaxes(title_text="时间 (秒)", row=2, col=1)

    # 更新Y轴标签
    fig.update_yaxes(title_text="角度 (度)", row=1, col=1)
    fig.update_yaxes(title_text="杆量值", row=2, col=1)

    # 更新布局
    fig.update_layout(
        title=title,
        showlegend=True,
        height=800,
        hovermode='x unified',
        template='plotly_white'
    )

    return fig


def print_statistics(df):
    """打印数据统计信息"""
    print("\n" + "="*60)
    print("Yaw角PID控制统计信息")
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
        print("用法: python plot_yaw_data.py <日志目录>")
        print("示例: python plot_yaw_data.py data/yaw/20240315_143022")
        sys.exit(1)

    log_dir = sys.argv[1]

    print(f"正在加载数据: {log_dir}")
    df = load_data(log_dir)
    print(f"数据加载完成！共 {len(df)} 条记录\n")

    # 打印统计信息
    print_statistics(df)

    # 创建图表
    print("\n正在生成图表...")
    fig = create_plot(df, title=f"Yaw角PID控制分析 - {os.path.basename(log_dir)}")

    # 保存HTML文件
    html_path = os.path.join(log_dir, 'yaw_analysis.html')
    fig.write_html(html_path)
    print(f"图表已保存: {html_path}")

    # 在浏览器中打开
    fig.show()


if __name__ == '__main__':
    main()
