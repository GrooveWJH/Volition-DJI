#!/usr/bin/env python3
"""
PID控制数据可视化工具

用法:
    python plot_pid_data.py data/20240101_120000
    python plot_pid_data.py data/20240101_120000 --live

功能:
- 读取CSV格式的PID控制数据
- 使用Plotly生成交互式4子图可视化
  1. X位置跟踪
  2. Y位置跟踪
  3. Roll杆量输出
  4. Pitch杆量输出
"""

import argparse
import os
import sys
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from rich.console import Console
from rich.panel import Panel

console = Console()


def load_data(data_dir):
    """加载CSV数据"""
    csv_path = os.path.join(data_dir, 'control_data.csv')

    if not os.path.exists(csv_path):
        console.print(f"[red]✗ 数据文件不存在: {csv_path}[/red]")
        return None

    try:
        df = pd.read_csv(csv_path)
        console.print(f"[green]✓ 已加载数据: {len(df)} 条记录[/green]")
        return df
    except Exception as e:
        console.print(f"[red]✗ 加载数据失败: {e}[/red]")
        return None


def create_plot(df, title="PID Control Analysis"):
    """创建4子图可视化"""

    # 计算相对时间（从0开始）
    df['relative_time'] = df['timestamp'] - df['timestamp'].iloc[0]

    # 创建2x2子图布局
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'X Position Tracking',
            'Y Position Tracking',
            'Roll Stick Output',
            'Pitch Stick Output'
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.10
    )

    # 配色方案
    COLOR_TARGET = '#FF6B6B'      # 红色 - 目标
    COLOR_CURRENT = '#4ECDC4'     # 青色 - 当前
    COLOR_STICK = '#45B7D1'       # 蓝色 - 杆量
    COLOR_NEUTRAL = '#95A5A6'     # 灰色 - 中立线

    # ========== 子图1: X位置跟踪 ==========
    fig.add_trace(
        go.Scatter(
            x=df['relative_time'],
            y=df['target_x'],
            name='Target X',
            line=dict(color=COLOR_TARGET, width=2, dash='dash'),
            legendgroup='x'
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['relative_time'],
            y=df['current_x'],
            name='Current X',
            line=dict(color=COLOR_CURRENT, width=2),
            legendgroup='x'
        ),
        row=1, col=1
    )

    # ========== 子图2: Y位置跟踪 ==========
    fig.add_trace(
        go.Scatter(
            x=df['relative_time'],
            y=df['target_y'],
            name='Target Y',
            line=dict(color=COLOR_TARGET, width=2, dash='dash'),
            legendgroup='y'
        ),
        row=1, col=2
    )
    fig.add_trace(
        go.Scatter(
            x=df['relative_time'],
            y=df['current_y'],
            name='Current Y',
            line=dict(color=COLOR_CURRENT, width=2),
            legendgroup='y'
        ),
        row=1, col=2
    )

    # ========== 子图3: Roll杆量 ==========
    # 中立线
    fig.add_trace(
        go.Scatter(
            x=[df['relative_time'].iloc[0], df['relative_time'].iloc[-1]],
            y=[1024, 1024],
            name='Neutral (1024)',
            line=dict(color=COLOR_NEUTRAL, width=1, dash='dot'),
            showlegend=False
        ),
        row=2, col=1
    )
    # 实际杆量
    fig.add_trace(
        go.Scatter(
            x=df['relative_time'],
            y=df['roll_absolute'],
            name='Roll Output',
            line=dict(color=COLOR_STICK, width=2),
            fill='tonexty',
            fillcolor='rgba(69, 183, 209, 0.1)',
            legendgroup='roll'
        ),
        row=2, col=1
    )

    # ========== 子图4: Pitch杆量 ==========
    # 中立线
    fig.add_trace(
        go.Scatter(
            x=[df['relative_time'].iloc[0], df['relative_time'].iloc[-1]],
            y=[1024, 1024],
            name='Neutral (1024)',
            line=dict(color=COLOR_NEUTRAL, width=1, dash='dot'),
            showlegend=False
        ),
        row=2, col=2
    )
    # 实际杆量
    fig.add_trace(
        go.Scatter(
            x=df['relative_time'],
            y=df['pitch_absolute'],
            name='Pitch Output',
            line=dict(color=COLOR_STICK, width=2),
            fill='tonexty',
            fillcolor='rgba(69, 183, 209, 0.1)',
            legendgroup='pitch'
        ),
        row=2, col=2
    )

    # ========== 全局样式设置 ==========
    fig.update_xaxes(title_text="Time (s)", row=2, col=1)
    fig.update_xaxes(title_text="Time (s)", row=2, col=2)
    fig.update_xaxes(title_text="Time (s)", row=1, col=1)
    fig.update_xaxes(title_text="Time (s)", row=1, col=2)

    fig.update_yaxes(title_text="Position (m)", row=1, col=1)
    fig.update_yaxes(title_text="Position (m)", row=1, col=2)
    fig.update_yaxes(title_text="Stick Value", row=2, col=1)
    fig.update_yaxes(title_text="Stick Value", row=2, col=2)

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor='center',
            font=dict(size=20, color='#2C3E50')
        ),
        height=800,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5
        ),
        hovermode='x unified',
        template='plotly_white'
    )

    return fig


def plot_static(data_dir):
    """生成静态图表"""
    df = load_data(data_dir)
    if df is None:
        return 1

    fig = create_plot(df, title=f"PID Control Analysis - {os.path.basename(data_dir)}")

    # 保存HTML文件
    output_path = os.path.join(data_dir, 'pid_analysis.html')
    fig.write_html(output_path)
    console.print(f"[green]✓ 图表已保存: {output_path}[/green]")

    # 在浏览器中打开
    console.print("[cyan]正在浏览器中打开图表...[/cyan]")
    fig.show()

    return 0


def plot_live(data_dir):
    """实时更新图表（监视CSV文件变化）"""
    import time

    console.print("[yellow]⚠ 实时模式功能开发中...[/yellow]")
    console.print("[cyan]当前将以静态模式显示数据[/cyan]")

    return plot_static(data_dir)


def main():
    parser = argparse.ArgumentParser(
        description='PID控制数据可视化工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python plot_pid_data.py data/20240101_120000          # 静态图表
  python plot_pid_data.py data/20240101_120000 --live  # 实时更新（开发中）
        """
    )
    parser.add_argument(
        'data_dir',
        help='数据目录路径（包含control_data.csv）'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='实时更新模式（监视文件变化）'
    )

    args = parser.parse_args()

    # 检查目录是否存在
    if not os.path.isdir(args.data_dir):
        console.print(f"[red]✗ 目录不存在: {args.data_dir}[/red]")
        console.print("[yellow]提示: 请提供有效的数据目录路径[/yellow]")
        return 1

    console.print(Panel.fit(
        "[bold cyan]PID Control Data Visualization[/bold cyan]\n"
        f"[dim]数据目录: {args.data_dir}[/dim]",
        border_style="cyan"
    ))

    if args.live:
        return plot_live(args.data_dir)
    else:
        return plot_static(args.data_dir)


if __name__ == '__main__':
    exit(main())
