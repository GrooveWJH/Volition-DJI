#!/usr/bin/env python3
"""
测试 TaskDistributor 的持续轮询功能

验证修复后的 IVASClient 会以固定频率持续轮询任务
"""
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dashboard.task_distributor import TaskDistributor
from rich.console import Console

console = Console()

# 全局计数器
poll_count = 0
poll_times = []
lock = threading.Lock()


class MockAdapter:
    """模拟 adapter"""
    def __init__(self, device_code, callsign):
        self.device_code = device_code
        self.uav_config = {'callsign': callsign}

    def receive_task(self, task_data, force_immediate=False):
        pass


def create_distributor_with_counter():
    """创建带有轮询计数器的 TaskDistributor"""
    distributor = TaskDistributor(ivas_config={
        'base_url': 'http://localhost:5001',  # 不存在的服务器，但不影响测试循环
        'account': 'test',
        'password': 'test',
        'task_hz': 5.0  # 5Hz = 每秒5次 = 0.2秒间隔
    })

    # 覆盖 _poll_task 来计数
    original_poll = distributor.ivas_client._poll_task

    def counting_poll():
        global poll_count, poll_times
        with lock:
            poll_count += 1
            poll_times.append(time.time())
            console.print(f"[green]✓ 第 {poll_count} 次轮询 (时间: {time.time():.2f})[/green]")
        # 不调用原始方法，避免网络请求

    distributor.ivas_client._poll_task = counting_poll

    # 覆盖 login 让它成功（跳过实际网络请求）
    distributor.ivas_client.login = lambda: True
    distributor.ivas_client.token = "mock_token"

    return distributor


def test_continuous_polling():
    """测试持续轮询"""
    console.print("\n[bold cyan]========== 测试: 持续轮询 ==========[/bold cyan]\n")

    global poll_count, poll_times
    poll_count = 0
    poll_times = []

    distributor = create_distributor_with_counter()

    # 注册一个adapter
    adapter = MockAdapter(1, "无人机1")
    distributor.register(adapter.device_code, adapter)
    distributor.finalize()

    console.print("[bold]启动轮询线程，监控 3 秒...[/bold]")
    distributor.start()

    # 等待3秒
    time.sleep(3.0)

    # 停止轮询
    distributor.stop()

    # 分析结果
    console.print(f"\n[bold cyan]========== 结果分析 ==========[/bold cyan]\n")
    console.print(f"总轮询次数: {poll_count}")
    console.print(f"期望次数: 约 15 次 (3秒 × 5Hz)")

    if poll_count >= 12:  # 允许一些误差
        console.print(f"[green]✓ 持续轮询正常：{poll_count} 次 >= 12 次[/green]")
    else:
        console.print(f"[red]✗ 持续轮询异常：{poll_count} 次 < 12 次[/red]")
        return False

    # 计算轮询间隔
    if len(poll_times) >= 2:
        intervals = [poll_times[i+1] - poll_times[i] for i in range(len(poll_times)-1)]
        avg_interval = sum(intervals) / len(intervals)
        console.print(f"\n平均轮询间隔: {avg_interval:.3f} 秒")
        console.print(f"期望间隔: 0.200 秒 (5Hz)")

        if 0.15 <= avg_interval <= 0.25:  # 允许±0.05秒误差
            console.print(f"[green]✓ 轮询频率正常[/green]")
        else:
            console.print(f"[yellow]⚠ 轮询频率偏离预期（可能由于系统负载）[/yellow]")

    return True


def test_no_infinite_sleep():
    """测试不会陷入无限睡眠"""
    console.print("\n[bold cyan]========== 测试: 避免无限睡眠 ==========[/bold cyan]\n")

    global poll_count
    poll_count = 0

    distributor = create_distributor_with_counter()
    adapter = MockAdapter(1, "无人机1")
    distributor.register(adapter.device_code, adapter)
    distributor.finalize()

    console.print("[bold]启动轮询，检查是否会在第一次后卡住...[/bold]")
    distributor.start()

    # 等待1秒（应该轮询至少4次）
    time.sleep(1.0)
    first_count = poll_count

    # 再等待1秒
    time.sleep(1.0)
    second_count = poll_count

    distributor.stop()

    console.print(f"\n前1秒轮询次数: {first_count}")
    console.print(f"后1秒轮询次数: {second_count - first_count}")

    if second_count > first_count:
        console.print(f"[green]✓ 没有陷入无限睡眠，轮询持续进行[/green]")
        return True
    else:
        console.print(f"[red]✗ 可能陷入无限睡眠，第二秒没有新的轮询[/red]")
        return False


def main():
    """运行所有测试"""
    console.print("\n[bold bright_cyan]╔════════════════════════════════════════╗[/bold bright_cyan]")
    console.print("[bold bright_cyan]║  IVASClient 轮询频率修复验证        ║[/bold bright_cyan]")
    console.print("[bold bright_cyan]╚════════════════════════════════════════╝[/bold bright_cyan]\n")

    tests = [
        ("避免无限睡眠", test_no_infinite_sleep),
        ("持续轮询", test_continuous_polling),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            console.print(f"[red]✗ {test_name} 异常: {e}[/red]")
            import traceback
            traceback.print_exc()

    # 总结
    console.print("\n[bold bright_cyan]╔════════════════════════════════════════╗[/bold bright_cyan]")
    console.print("[bold bright_cyan]║           测试总结                    ║[/bold bright_cyan]")
    console.print("[bold bright_cyan]╚════════════════════════════════════════╝[/bold bright_cyan]\n")

    total = passed + failed
    console.print(f"[bright_white]总计: {total} 个测试[/bright_white]")
    console.print(f"[bright_green]通过: {passed} 个[/bright_green]")
    if failed > 0:
        console.print(f"[bright_red]失败: {failed} 个[/bright_red]")
    else:
        console.print("[bold bright_green]✓ 所有测试通过！修复有效！[/bold bright_green]")

    console.print()
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]测试被中断[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]测试运行异常: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
