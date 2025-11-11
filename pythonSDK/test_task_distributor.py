#!/usr/bin/env python3
"""
TaskDistributor 测试脚本

验证统一任务分发器的功能：
1. 单播路由（id=1/2/3 → 对应adapter）
2. 广播分发（id=99 → 所有adapters）
3. 任务类型验证（只有1/2/3支持广播）
4. 任务去重（防止重复执行）
5. force_immediate 标志（广播任务立即执行）
"""
import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dashboard.task_distributor import TaskDistributor
from rich.console import Console

console = Console()


class MockAdapter:
    """模拟 IVASAdapter 用于测试"""

    def __init__(self, device_code, callsign):
        self.device_code = device_code
        self.uav_config = {'callsign': callsign}
        self.received_tasks = []
        self.received_immediate_tasks = []

    def receive_task(self, task_data, force_immediate=False):
        """接收任务（模拟 IVASAdapter.receive_task）"""
        self.received_tasks.append(task_data)
        if force_immediate:
            self.received_immediate_tasks.append(task_data)

        task_type = "广播" if task_data.get('id') == 99 else "单播"
        immediate_flag = " [立即执行]" if force_immediate else ""
        console.print(
            f"[green]✓ {self.uav_config['callsign']} 收到 {task_type} 任务: "
            f"mission={task_data.get('mission')}, id={task_data.get('id')}{immediate_flag}[/green]"
        )


def test_single_cast_routing():
    """测试单播路由功能"""
    console.print("\n[bold cyan]========== 测试1: 单播路由 ==========[/bold cyan]\n")

    # 创建分发器
    distributor = TaskDistributor(ivas_config={
        'base_url': 'http://localhost:5001',
        'account': 'test',
        'password': 'test',
        'task_hz': 1.0
    })

    # 注册3个adapter
    adapters = [
        MockAdapter(1, "无人机1"),
        MockAdapter(2, "无人机2"),
        MockAdapter(3, "无人机3"),
    ]

    for adapter in adapters:
        distributor.register(adapter.device_code, adapter)

    distributor.finalize()

    # 模拟任务接收（id=1 → adapter1）
    console.print("[bold]测试: 发送 id=1, mission=1 (起飞) 给 adapter1[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 1, 'mission': 1, 'timestamp': int(time.time())}
    })

    # 验证
    assert len(adapters[0].received_tasks) == 1, "adapter1 应该收到1个任务"
    assert len(adapters[1].received_tasks) == 0, "adapter2 不应该收到任务"
    assert len(adapters[2].received_tasks) == 0, "adapter3 不应该收到任务"
    console.print("[green]✓ 单播路由测试通过：只有 adapter1 收到任务[/green]")

    # 测试路由到 adapter2
    console.print("\n[bold]测试: 发送 id=2, mission=4 (前往指定点) 给 adapter2[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 2, 'mission': 4, 'timestamp': int(time.time())}
    })

    assert len(adapters[0].received_tasks) == 1, "adapter1 仍应只有1个任务"
    assert len(adapters[1].received_tasks) == 1, "adapter2 应该收到1个任务"
    assert len(adapters[2].received_tasks) == 0, "adapter3 不应该收到任务"
    console.print("[green]✓ 单播路由测试通过：只有 adapter2 收到任务[/green]")

    return True


def test_broadcast_distribution():
    """测试广播分发功能"""
    console.print("\n[bold cyan]========== 测试2: 广播分发 ==========[/bold cyan]\n")

    distributor = TaskDistributor(ivas_config={
        'base_url': 'http://localhost:5001',
        'account': 'test',
        'password': 'test',
        'task_hz': 1.0
    })

    adapters = [
        MockAdapter(1, "无人机1"),
        MockAdapter(2, "无人机2"),
        MockAdapter(3, "无人机3"),
    ]

    for adapter in adapters:
        distributor.register(adapter.device_code, adapter)

    distributor.finalize()

    # 测试广播起飞任务（id=99, mission=1）
    console.print("[bold]测试: 广播 id=99, mission=1 (起飞) 给所有adapters[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 1, 'timestamp': int(time.time())}
    })

    # 验证所有adapter都收到任务
    for i, adapter in enumerate(adapters):
        assert len(adapter.received_tasks) == 1, f"adapter{i+1} 应该收到1个任务"
        assert len(adapter.received_immediate_tasks) == 1, f"adapter{i+1} 应该收到立即执行标志"

    console.print("[green]✓ 广播分发测试通过：所有3个adapters都收到任务且标记为立即执行[/green]")

    return True


def test_task_deduplication():
    """测试任务去重功能"""
    console.print("\n[bold cyan]========== 测试3: 任务去重 ==========[/bold cyan]\n")

    distributor = TaskDistributor(ivas_config={
        'base_url': 'http://localhost:5001',
        'account': 'test',
        'password': 'test',
        'task_hz': 1.0
    })

    adapters = [MockAdapter(1, "无人机1"), MockAdapter(2, "无人机2")]

    for adapter in adapters:
        distributor.register(adapter.device_code, adapter)

    distributor.finalize()

    # 发送第一个广播任务
    timestamp = int(time.time())
    console.print("[bold]测试: 发送第一个广播任务 (id=99, mission=2, timestamp={})...[/bold]".format(timestamp))
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 2, 'timestamp': timestamp}
    })

    assert len(adapters[0].received_tasks) == 1, "第一次广播应该成功"
    assert len(adapters[1].received_tasks) == 1, "第一次广播应该成功"

    # 发送相同的广播任务（应该被去重）
    console.print("\n[bold]测试: 重复发送相同任务 (应该被去重)...[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 2, 'timestamp': timestamp}
    })

    assert len(adapters[0].received_tasks) == 1, "重复任务应该被去重，adapter1仍只有1个任务"
    assert len(adapters[1].received_tasks) == 1, "重复任务应该被去重，adapter2仍只有1个任务"

    console.print("[green]✓ 任务去重测试通过：重复任务被成功阻止[/green]")

    # 发送不同时间戳的相同任务（应该执行）
    console.print("\n[bold]测试: 发送不同时间戳的任务 (应该执行)...[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 2, 'timestamp': timestamp + 10}
    })

    assert len(adapters[0].received_tasks) == 2, "不同时间戳应该被视为新任务"
    assert len(adapters[1].received_tasks) == 2, "不同时间戳应该被视为新任务"

    console.print("[green]✓ 不同时间戳任务测试通过：新任务正常执行[/green]")

    return True


def test_broadcast_validation():
    """测试广播任务类型验证"""
    console.print("\n[bold cyan]========== 测试4: 广播任务类型验证 ==========[/bold cyan]\n")

    distributor = TaskDistributor(ivas_config={
        'base_url': 'http://localhost:5001',
        'account': 'test',
        'password': 'test',
        'task_hz': 1.0
    })

    adapters = [MockAdapter(1, "无人机1"), MockAdapter(2, "无人机2")]

    for adapter in adapters:
        distributor.register(adapter.device_code, adapter)

    distributor.finalize()

    # 测试支持的任务类型（1/2/3）
    console.print("[bold]测试: 广播 mission=1 (起飞) - 应该成功[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 1, 'timestamp': int(time.time())}
    })
    assert len(adapters[0].received_tasks) == 1, "mission=1 应该支持广播"

    console.print("\n[bold]测试: 广播 mission=2 (降落) - 应该成功[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 2, 'timestamp': int(time.time()) + 1}
    })
    assert len(adapters[0].received_tasks) == 2, "mission=2 应该支持广播"

    console.print("\n[bold]测试: 广播 mission=3 (返航) - 应该成功[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 3, 'timestamp': int(time.time()) + 2}
    })
    assert len(adapters[0].received_tasks) == 3, "mission=3 应该支持广播"

    # 测试不支持的任务类型（4/5/6/7）
    console.print("\n[bold]测试: 广播 mission=4 (前往指定点) - 应该被拒绝[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 4, 'timestamp': int(time.time()) + 3}
    })
    assert len(adapters[0].received_tasks) == 3, "mission=4 不应该支持广播"

    console.print("\n[bold]测试: 广播 mission=5 (多航点任务) - 应该被拒绝[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 5, 'timestamp': int(time.time()) + 4}
    })
    assert len(adapters[0].received_tasks) == 3, "mission=5 不应该支持广播"

    console.print("[green]✓ 任务类型验证测试通过：只有1/2/3支持广播[/green]")

    return True


def test_unknown_task_id():
    """测试未知任务ID处理"""
    console.print("\n[bold cyan]========== 测试5: 未知任务ID处理 ==========[/bold cyan]\n")

    distributor = TaskDistributor(ivas_config={
        'base_url': 'http://localhost:5001',
        'account': 'test',
        'password': 'test',
        'task_hz': 1.0
    })

    adapters = [MockAdapter(1, "无人机1"), MockAdapter(2, "无人机2")]

    for adapter in adapters:
        distributor.register(adapter.device_code, adapter)

    distributor.finalize()

    # 发送未知ID的任务
    console.print("[bold]测试: 发送 id=999 (未注册的ID)...[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 999, 'mission': 1, 'timestamp': int(time.time())}
    })

    assert len(adapters[0].received_tasks) == 0, "未知ID不应该被分发"
    assert len(adapters[1].received_tasks) == 0, "未知ID不应该被分发"

    console.print("[green]✓ 未知ID处理测试通过：未注册ID被正确拒绝[/green]")

    return True


def main():
    """运行所有测试"""
    console.print("\n[bold bright_cyan]╔════════════════════════════════════════╗[/bold bright_cyan]")
    console.print("[bold bright_cyan]║  TaskDistributor 功能测试套件        ║[/bold bright_cyan]")
    console.print("[bold bright_cyan]╚════════════════════════════════════════╝[/bold bright_cyan]\n")

    tests = [
        ("单播路由", test_single_cast_routing),
        ("广播分发", test_broadcast_distribution),
        ("任务去重", test_task_deduplication),
        ("广播任务类型验证", test_broadcast_validation),
        ("未知任务ID处理", test_unknown_task_id),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                console.print(f"[red]✗ {test_name} 失败[/red]")
        except Exception as e:
            failed += 1
            console.print(f"[red]✗ {test_name} 异常: {e}[/red]")
            import traceback
            traceback.print_exc()

    # 测试总结
    console.print("\n[bold bright_cyan]╔════════════════════════════════════════╗[/bold bright_cyan]")
    console.print("[bold bright_cyan]║           测试总结                    ║[/bold bright_cyan]")
    console.print("[bold bright_cyan]╚════════════════════════════════════════╝[/bold bright_cyan]\n")

    total = passed + failed
    console.print(f"[bright_white]总计: {total} 个测试[/bright_white]")
    console.print(f"[bright_green]通过: {passed} 个[/bright_green]")
    if failed > 0:
        console.print(f"[bright_red]失败: {failed} 个[/bright_red]")
    else:
        console.print("[bold bright_green]✓ 所有测试通过！[/bold bright_green]")

    console.print()
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        console.print(f"\n[bold red]测试运行异常: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
