#!/usr/bin/env python3
"""
IVAS 广播任务测试脚本

用于验证 id=99 广播任务修复是否生效。
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dashboard.task_broadcaster import TaskBroadcaster
from rich.console import Console

console = Console()


class MockAdapter:
    """模拟 IVASAdapter 用于测试"""

    def __init__(self, device_code, callsign):
        self.device_code = device_code
        self.uav_config = {'callsign': callsign}
        self.received_tasks = []

    def receive_broadcast_task(self, task_data):
        """接收广播任务"""
        self.received_tasks.append(task_data)
        console.print(f"[green]✓ {self.uav_config['callsign']} 收到任务: {task_data}[/green]")


def test_broadcast():
    """测试广播功能"""
    console.print("\n[bold cyan]========== IVAS 广播任务测试 ==========[/bold cyan]\n")

    # 创建广播管理器
    broadcaster = TaskBroadcaster()
    console.print("[bold]步骤1: 创建广播管理器[/bold]")

    # 创建3个模拟adapter
    adapters = [
        MockAdapter(1, "无人机1"),
        MockAdapter(2, "无人机2"),
        MockAdapter(3, "无人机3"),
    ]

    console.print("\n[bold]步骤2: 注册3个adapter[/bold]")
    for adapter in adapters:
        broadcaster.register_adapter(adapter)

    broadcaster.finalize()

    # 测试1: 广播起飞任务
    console.print("\n[bold]步骤3: 测试广播起飞任务 (id=99, mission=1)[/bold]")
    task1 = {'id': 99, 'mission': 1, 'timestamp': 1234567890}
    success = broadcaster.broadcast_task(task1, source_adapter=adapters[0])

    if success:
        console.print("[green]✓ 广播成功[/green]")
    else:
        console.print("[red]✗ 广播失败[/red]")
        return False

    # 验证所有adapter都收到任务
    console.print("\n[bold]步骤4: 验证所有adapter是否收到任务[/bold]")
    for i, adapter in enumerate(adapters):
        if len(adapter.received_tasks) == 1:
            console.print(f"[green]✓ {adapter.uav_config['callsign']} 收到 {len(adapter.received_tasks)} 个任务[/green]")
        else:
            console.print(f"[red]✗ {adapter.uav_config['callsign']} 收到 {len(adapter.received_tasks)} 个任务（预期1个）[/red]")
            return False

    # 测试2: 重复发送相同任务（应该被去重）
    console.print("\n[bold]步骤5: 测试任务去重（重复发送相同任务）[/bold]")
    success = broadcaster.broadcast_task(task1, source_adapter=adapters[0])

    if not success:
        console.print("[green]✓ 任务去重成功，跳过重复任务[/green]")
    else:
        console.print("[red]✗ 任务去重失败，重复任务未被阻止[/red]")
        return False

    # 验证adapter没有收到重复任务
    for adapter in adapters:
        if len(adapter.received_tasks) == 1:
            console.print(f"[green]✓ {adapter.uav_config['callsign']} 仍然只有 1 个任务（去重成功）[/green]")
        else:
            console.print(f"[red]✗ {adapter.uav_config['callsign']} 有 {len(adapter.received_tasks)} 个任务（去重失败）[/red]")
            return False

    # 测试3: 广播降落任务
    console.print("\n[bold]步骤6: 测试广播降落任务 (id=99, mission=2)[/bold]")
    task2 = {'id': 99, 'mission': 2, 'timestamp': 1234567891}
    success = broadcaster.broadcast_task(task2, source_adapter=adapters[0])

    if success:
        console.print("[green]✓ 降落任务广播成功[/green]")
    else:
        console.print("[red]✗ 降落任务广播失败[/red]")
        return False

    # 验证每个adapter现在有2个任务
    for adapter in adapters:
        if len(adapter.received_tasks) == 2:
            console.print(f"[green]✓ {adapter.uav_config['callsign']} 共收到 2 个任务[/green]")
        else:
            console.print(f"[red]✗ {adapter.uav_config['callsign']} 有 {len(adapter.received_tasks)} 个任务（预期2个）[/red]")
            return False

    # 测试4: 发送不支持广播的任务类型
    console.print("\n[bold]步骤7: 测试不支持广播的任务类型 (id=99, mission=4)[/bold]")
    task3 = {'id': 99, 'mission': 4, 'timestamp': 1234567892}
    success = broadcaster.broadcast_task(task3, source_adapter=adapters[0])

    if not success:
        console.print("[green]✓ 正确拒绝不支持广播的任务类型[/green]")
    else:
        console.print("[red]✗ 错误接受了不支持广播的任务类型[/red]")
        return False

    # 测试5: 非广播任务 (id != 99)
    console.print("\n[bold]步骤8: 测试非广播任务 (id=1, mission=1)[/bold]")
    task4 = {'id': 1, 'mission': 1, 'timestamp': 1234567893}
    success = broadcaster.broadcast_task(task4, source_adapter=adapters[0])

    if not success:
        console.print("[green]✓ 正确识别非广播任务[/green]")
    else:
        console.print("[red]✗ 错误处理非广播任务[/red]")
        return False

    console.print("\n[bold bright_green]========== 所有测试通过 ==========[/bold bright_green]\n")
    return True


if __name__ == '__main__':
    try:
        success = test_broadcast()
        sys.exit(0 if success else 1)
    except Exception as e:
        console.print(f"\n[bold red]测试异常: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
