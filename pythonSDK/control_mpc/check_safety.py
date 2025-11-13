#!/usr/bin/env python3
"""
航点安全性检查工具

用于验证所有航点是否在安全范围内（针对2m半径场地）
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import WAYPOINTS, PLANE_USE_RANDOM_WAYPOINTS, PLANE_RANDOM_MAX_DISTANCE
from rich.console import Console
from rich.table import Table
import numpy as np

console = Console()

# 安全限制（2m场地）
FIELD_RADIUS = 2.0  # 场地最大半径
SAFE_RADIUS = 1.5   # 推荐安全半径（预留0.5m余量）
WARNING_RADIUS = 1.8  # 警告半径

def check_waypoints():
    """检查航点安全性"""
    console.print("\n[bold cyan]━━━ 航点安全性检查 ━━━[/bold cyan]\n")

    # 创建表格
    table = Table(title="航点安全性分析", show_header=True, header_style="bold magenta")
    table.add_column("编号", style="cyan", justify="center")
    table.add_column("坐标 (x, y)", style="yellow")
    table.add_column("距离中心", style="green", justify="right")
    table.add_column("安全状态", style="white")

    all_safe = True
    has_warning = False

    for i, (x, y) in enumerate(WAYPOINTS):
        dist = np.sqrt(x**2 + y**2)

        # 判断安全等级
        if dist <= SAFE_RADIUS:
            status = "[green]✓ 安全[/green]"
            status_emoji = "✓"
        elif dist <= WARNING_RADIUS:
            status = "[yellow]⚠ 警告（接近边界）[/yellow]"
            status_emoji = "⚠"
            has_warning = True
        else:
            status = "[red]✗ 危险（超出安全范围）[/red]"
            status_emoji = "✗"
            all_safe = False

        table.add_row(
            f"{i}",
            f"({x:+.2f}, {y:+.2f})m",
            f"{dist:.2f}m",
            status
        )

    console.print(table)

    # 打印限制信息
    console.print(f"\n[dim]场地限制:[/dim]")
    console.print(f"  • 场地最大半径: {FIELD_RADIUS:.1f}m")
    console.print(f"  • 推荐安全半径: {SAFE_RADIUS:.1f}m （预留0.5m余量）")
    console.print(f"  • 警告半径: {WARNING_RADIUS:.1f}m")

    # 总结
    console.print("\n[bold]检查结果:[/bold]")
    if all_safe and not has_warning:
        console.print("[green]✓ 所有航点均在安全范围内，可以安全实验[/green]")
        return True
    elif all_safe and has_warning:
        console.print("[yellow]⚠ 部分航点接近边界，建议谨慎操作[/yellow]")
        console.print("[yellow]  建议：降低航点距离或提高安全意识[/yellow]")
        return True
    else:
        console.print("[red]✗ 检测到危险航点！禁止实验！[/red]")
        console.print("[red]  请编辑 control/config.py 中的 WAYPOINTS，确保所有点在 1.5m 以内[/red]")
        return False

def check_random_waypoints():
    """检查随机航点配置"""
    console.print("\n[bold cyan]━━━ 随机航点配置检查 ━━━[/bold cyan]\n")

    if not PLANE_USE_RANDOM_WAYPOINTS:
        console.print("[dim]随机航点已禁用（推荐设置）[/dim]")
        return True

    console.print("[yellow]⚠ 警告：随机航点已启用[/yellow]")

    max_dist = PLANE_RANDOM_MAX_DISTANCE

    if max_dist <= SAFE_RADIUS:
        console.print(f"[green]✓ 随机航点最大距离: {max_dist:.2f}m （在安全范围内）[/green]")
        return True
    elif max_dist <= WARNING_RADIUS:
        console.print(f"[yellow]⚠ 随机航点最大距离: {max_dist:.2f}m （接近边界）[/yellow]")
        return True
    else:
        console.print(f"[red]✗ 随机航点最大距离: {max_dist:.2f}m （超出安全范围）[/red]")
        console.print(f"[red]  建议：将 PLANE_RANDOM_MAX_DISTANCE 降低至 {SAFE_RADIUS:.1f} 或更小[/red]")
        return False

def check_excitation_amplitude():
    """检查系统辨识激励幅值"""
    console.print("\n[bold cyan]━━━ 系统辨识参数检查 ━━━[/bold cyan]\n")

    # 导入system_id模块
    try:
        from control_mpc.system_id import SystemIdentification
        sysid = SystemIdentification()
        amplitude = sysid.excitation_amplitude
        duration = sysid.excitation_duration

        # 估计最大运动范围
        # 假设：幅值50对应约0.5m移动（经验值）
        estimated_range = amplitude / 100.0

        console.print(f"激励幅值: {amplitude:.0f}")
        console.print(f"辨识时间: {duration:.0f}秒")
        console.print(f"预计运动范围: ±{estimated_range:.2f}m")

        if estimated_range <= 0.5:
            console.print(f"[green]✓ 运动范围在安全范围内[/green]")
            return True
        elif estimated_range <= 0.8:
            console.print(f"[yellow]⚠ 运动范围较大，注意观察[/yellow]")
            return True
        else:
            console.print(f"[red]✗ 运动范围过大，可能越界[/red]")
            console.print(f"[red]  建议：将 excitation_amplitude 降低至 30-40[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ 无法读取系统辨识参数: {e}[/red]")
        return False

def main():
    """主函数"""
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    MPC控制系统 - 航点安全性检查工具[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")

    # 执行检查
    result1 = check_waypoints()
    result2 = check_random_waypoints()
    result3 = check_excitation_amplitude()

    # 最终判定
    console.print("\n[bold cyan]━━━ 最终判定 ━━━[/bold cyan]\n")

    if result1 and result2 and result3:
        console.print("[bold green]✓ 所有检查通过，可以开始实验[/bold green]")
        console.print("[dim]提示：实验前请确保已阅读 operation-guide.md[/dim]\n")
        return 0
    else:
        console.print("[bold red]✗ 存在安全隐患，请修复后重新检查[/bold red]")
        console.print("[red]修复方法：编辑 control/config.py 和 control_mpc/system_id.py[/red]\n")
        return 1

if __name__ == "__main__":
    exit(main())
