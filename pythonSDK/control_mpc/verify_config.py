#!/usr/bin/env python3
"""
配置文件验证工具

用于检查所有必要的配置项是否正确设置
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
import json
import numpy as np

console = Console()

def check_basic_config():
    """检查基础配置"""
    console.print("\n[bold cyan]━━━ 基础配置检查 ━━━[/bold cyan]\n")

    try:
        from control import config

        checks = [
            ("GATEWAY_SN", config.GATEWAY_SN, lambda x: len(x) > 0, "无人机序列号"),
            ("VRPN_DEVICE", config.VRPN_DEVICE, lambda x: '@' in x, "动捕设备名称"),
            ("MQTT_HOST", config.MQTT_CONFIG['host'], lambda x: len(x) > 0, "MQTT服务器地址"),
            ("MQTT_PORT", config.MQTT_CONFIG['port'], lambda x: x in [1883, 8883], "MQTT端口"),
            ("CONTROL_FREQUENCY", config.CONTROL_FREQUENCY, lambda x: x == 50, "控制频率"),
            ("MAX_STICK_OUTPUT", config.MAX_STICK_OUTPUT, lambda x: 50 <= x <= 150, "最大杆量限幅"),
        ]

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("配置项", style="cyan")
        table.add_column("当前值", style="yellow")
        table.add_column("状态", style="white")
        table.add_column("说明", style="dim")

        all_pass = True

        for name, value, validator, desc in checks:
            is_valid = validator(value)
            status = "[green]✓[/green]" if is_valid else "[red]✗[/red]"

            if not is_valid:
                all_pass = False

            table.add_row(name, str(value), status, desc)

        console.print(table)

        return all_pass

    except Exception as e:
        console.print(f"[red]✗ 无法读取配置文件: {e}[/red]")
        return False

def check_pid_gains():
    """检查PID增益设置"""
    console.print("\n[bold cyan]━━━ PID增益检查 ━━━[/bold cyan]\n")

    try:
        from control import config

        # 推荐范围（针对2m场地）
        recommended = {
            'KP_XY': (200, 400),
            'KI_XY': (10, 30),
            'KD_XY': (8, 20),
        }

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("增益参数", style="cyan")
        table.add_column("当前值", style="yellow", justify="right")
        table.add_column("推荐范围", style="green", justify="center")
        table.add_column("评估", style="white")

        all_reasonable = True

        for param, (min_val, max_val) in recommended.items():
            current = getattr(config, param)

            if min_val <= current <= max_val:
                status = "[green]✓ 合理[/green]"
            elif current < min_val:
                status = "[yellow]⚠ 偏低[/yellow]"
                all_reasonable = False
            else:
                status = "[yellow]⚠ 偏高[/yellow]"
                all_reasonable = False

            table.add_row(
                param,
                f"{current:.1f}",
                f"{min_val:.0f} - {max_val:.0f}",
                status
            )

        console.print(table)

        if not all_reasonable:
            console.print("\n[yellow]提示：增益参数超出推荐范围，可能影响控制性能[/yellow]")
            console.print("[yellow]      如果是首次实验，建议使用推荐范围内的值[/yellow]")

        return True  # 不阻止实验，仅提醒

    except Exception as e:
        console.print(f"[red]✗ 无法读取PID增益: {e}[/red]")
        return False

def check_mpc_model():
    """检查已保存的MPC模型"""
    console.print("\n[bold cyan]━━━ MPC模型检查 ━━━[/bold cyan]\n")

    model_path = "control_mpc/identified_model.json"

    if not os.path.exists(model_path):
        console.print("[dim]未找到已保存的模型文件[/dim]")
        console.print("[dim]首次运行时将自动进行系统辨识[/dim]")
        return True

    try:
        with open(model_path, 'r') as f:
            model_data = json.load(f)

        A = np.array(model_data['A_matrix'])
        B = np.array(model_data['B_matrix'])
        R_squared = model_data['model_quality']

        console.print(f"模型文件: {model_path}")
        console.print(f"模型质量 (R²): {R_squared:.3f}")

        # 检查模型质量
        if R_squared < 0.6:
            console.print("[red]✗ 模型质量不佳 (R² < 0.6)[/red]")
            console.print("[red]  建议：删除此模型，重新进行系统辨识[/red]")
            console.print(f"[dim]  命令: rm {model_path}[/dim]")
            return False
        elif R_squared < 0.8:
            console.print("[yellow]⚠ 模型质量一般 (0.6 ≤ R² < 0.8)[/yellow]")
            console.print("[yellow]  可以使用，但效果可能不佳[/yellow]")
        else:
            console.print("[green]✓ 模型质量良好 (R² ≥ 0.8)[/green]")

        # 检查A矩阵稳定性
        eigvals = np.linalg.eigvals(A)
        max_eigval = np.max(np.abs(eigvals))

        console.print(f"\nA矩阵最大特征值: {max_eigval:.4f}")

        if max_eigval >= 1.0:
            console.print("[red]✗ 系统不稳定（特征值 ≥ 1.0）[/red]")
            console.print("[red]  危险！禁止使用此模型！[/red]")
            console.print(f"[red]  必须删除: rm {model_path}[/red]")
            return False
        else:
            console.print("[green]✓ 系统稳定（特征值 < 1.0）[/green]")

        # 检查矩阵条件数
        cond = np.linalg.cond(A)
        console.print(f"A矩阵条件数: {cond:.2f}")

        if cond > 1000:
            console.print("[red]✗ 矩阵条件数过高，数值不稳定[/red]")
            return False
        elif cond > 100:
            console.print("[yellow]⚠ 矩阵条件数较高[/yellow]")
        else:
            console.print("[green]✓ 矩阵条件数良好[/green]")

        return True

    except Exception as e:
        console.print(f"[red]✗ 模型文件读取失败: {e}[/red]")
        console.print(f"[red]  建议：删除损坏的模型文件[/red]")
        console.print(f"[dim]  命令: rm {model_path}[/dim]")
        return False

def check_dependencies():
    """检查Python依赖包"""
    console.print("\n[bold cyan]━━━ 依赖包检查 ━━━[/bold cyan]\n")

    required_packages = [
        'numpy',
        'scipy',
        'rich',
        'zmq',
        'paho.mqtt',
    ]

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("包名", style="cyan")
    table.add_column("状态", style="white")
    table.add_column("版本", style="yellow")

    all_installed = True

    for package in required_packages:
        try:
            if package == 'paho.mqtt':
                import paho.mqtt.client as mqtt
                version = mqtt.__version__ if hasattr(mqtt, '__version__') else 'unknown'
            elif package == 'zmq':
                import zmq
                version = zmq.__version__
            else:
                mod = __import__(package)
                version = mod.__version__ if hasattr(mod, '__version__') else 'unknown'

            table.add_row(package, "[green]✓ 已安装[/green]", version)

        except ImportError:
            table.add_row(package, "[red]✗ 未安装[/red]", "-")
            all_installed = False

    console.print(table)

    if not all_installed:
        console.print("\n[red]请安装缺失的依赖包：[/red]")
        console.print("[red]  pip install numpy scipy rich zmq paho-mqtt[/red]")

    return all_installed

def main():
    """主函数"""
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    MPC控制系统 - 配置验证工具[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")

    # 执行检查
    result1 = check_dependencies()
    result2 = check_basic_config()
    result3 = check_pid_gains()
    result4 = check_mpc_model()

    # 最终判定
    console.print("\n[bold cyan]━━━ 最终判定 ━━━[/bold cyan]\n")

    critical_pass = result1 and result2 and result4

    if critical_pass:
        console.print("[bold green]✓ 关键配置检查通过[/bold green]")
        if result3:
            console.print("[bold green]✓ 所有配置正常，可以开始实验[/bold green]")
        else:
            console.print("[yellow]⚠ PID参数超出推荐范围，建议调整（不影响实验）[/yellow]")
        console.print("[dim]提示：运行前请先执行 python control_mpc/check_safety.py[/dim]\n")
        return 0
    else:
        console.print("[bold red]✗ 存在配置问题，请修复后重新检查[/bold red]\n")
        return 1

if __name__ == "__main__":
    exit(main())
