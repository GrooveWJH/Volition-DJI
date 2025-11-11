#!/usr/bin/env python3
"""
IVAS 系统完整性检查脚本

验证：
1. 位置上报逻辑（有GPS vs 无GPS）
2. 任务轮询频率
3. 任务分发路由（单播 + 广播）
4. 睡眠间隔计算
"""
import sys
import os
import time
import threading
from unittest.mock import Mock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rich.console import Console
from rich.table import Table

console = Console()

# ============ 测试1: 位置上报逻辑 ============

def test_position_report_with_gps():
    """测试有GPS时的位置上报"""
    console.print("\n[bold cyan]========== 测试1: 有GPS时的位置上报 ==========[/bold cyan]\n")

    from dashboard.ivas_adapter import IVASAdapter

    # 创建Mock MQTT客户端（有GPS）
    mock_mqtt = Mock()
    mock_mqtt.get_position = Mock(return_value=(23.123456, 113.654321, 100.0))
    mock_mqtt.get_attitude_head = Mock(return_value=45.0)
    mock_mqtt.get_speed = Mock(return_value=(1.5, 0, 0, 0))

    # 创建Adapter
    adapter = IVASAdapter(
        device_code=1,
        mqtt_client=mock_mqtt,
        ivas_config={
            'base_url': 'http://test',
            'account': 'test',
            'password': 'test',
            'report_hz': 5.0,
            'task_hz': 2.0
        },
        uav_config={'callsign': '测试无人机1', 'sn': 'TEST001'},
        features={'position_report': True, 'target_report': False, 'task_receive': False}
    )

    # 调用位置数据生成
    data = adapter._get_real_position_data()

    # 验证
    assert data is not None, "有GPS时应该返回数据"
    assert data['userX'] == 23.123456, "纬度应该正确"
    assert data['userY'] == 113.654321, "经度应该正确"
    assert data['userZ'] == 100.0, "高度应该正确"
    assert data['validCount'] == 10, "有效GPS的validCount应为10"

    console.print("[green]✓ 有GPS时位置上报正常[/green]")
    return True


def test_position_report_without_gps():
    """测试无GPS时的位置上报"""
    console.print("\n[bold cyan]========== 测试2: 无GPS时的位置上报 ==========[/bold cyan]\n")

    from dashboard.ivas_adapter import IVASAdapter

    # 创建Mock MQTT客户端（无GPS）
    mock_mqtt = Mock()
    mock_mqtt.get_position = Mock(return_value=(None, None, None))
    mock_mqtt.get_attitude_head = Mock(return_value=0.0)
    mock_mqtt.get_speed = Mock(return_value=(0, 0, 0, 0))

    # 创建Adapter
    adapter = IVASAdapter(
        device_code=1,
        mqtt_client=mock_mqtt,
        ivas_config={
            'base_url': 'http://test',
            'account': 'test',
            'password': 'test',
            'report_hz': 5.0,
            'task_hz': 2.0
        },
        uav_config={'callsign': '测试无人机1', 'sn': 'TEST001'},
        features={'position_report': True, 'target_report': False, 'task_receive': False}
    )

    # 调用位置数据生成
    data = adapter._get_real_position_data()

    # 验证
    assert data is None, "无GPS时应该返回None"

    console.print("[green]✓ 无GPS时正确跳过上报[/green]")
    return True


def test_position_report_gps_recovery():
    """测试GPS从无到有的恢复"""
    console.print("\n[bold cyan]========== 测试3: GPS恢复场景 ==========[/bold cyan]\n")

    from dashboard.ivas_adapter import IVASAdapter

    # 创建Mock MQTT客户端
    mock_mqtt = Mock()

    # 创建Adapter
    adapter = IVASAdapter(
        device_code=1,
        mqtt_client=mock_mqtt,
        ivas_config={
            'base_url': 'http://test',
            'account': 'test',
            'password': 'test',
            'report_hz': 5.0,
            'task_hz': 2.0
        },
        uav_config={'callsign': '测试无人机1', 'sn': 'TEST001'},
        features={'position_report': True, 'target_report': False, 'task_receive': False}
    )

    # 第1次：无GPS
    mock_mqtt.get_position = Mock(return_value=(None, None, None))
    mock_mqtt.get_attitude_head = Mock(return_value=0.0)
    mock_mqtt.get_speed = Mock(return_value=(0, 0, 0, 0))
    data1 = adapter._get_real_position_data()
    assert data1 is None, "第1次无GPS应返回None"
    console.print("[yellow]第1次调用: GPS无效，返回None ✓[/yellow]")

    # 第2次：GPS恢复
    mock_mqtt.get_position = Mock(return_value=(23.5, 113.5, 50.0))
    data2 = adapter._get_real_position_data()
    assert data2 is not None, "GPS恢复后应返回数据"
    assert data2['userX'] == 23.5, "GPS恢复后数据应正确"
    console.print("[green]第2次调用: GPS恢复，正常上报 ✓[/green]")

    # 第3次：继续有GPS
    mock_mqtt.get_position = Mock(return_value=(23.6, 113.6, 60.0))
    data3 = adapter._get_real_position_data()
    assert data3 is not None, "持续有GPS应持续上报"
    assert data3['userX'] == 23.6
    console.print("[green]第3次调用: GPS持续有效，正常上报 ✓[/green]")

    console.print("\n[green]✓ GPS恢复逻辑正常[/green]")
    return True


# ============ 测试4: 睡眠间隔计算 ============

def test_sleep_interval_calculation():
    """测试睡眠间隔计算逻辑"""
    console.print("\n[bold cyan]========== 测试4: 睡眠间隔计算 ==========[/bold cyan]\n")

    from ivas.client import IVASClient

    table = Table(title="睡眠间隔计算测试")
    table.add_column("场景", style="cyan")
    table.add_column("position_report", style="yellow")
    table.add_column("task_receive", style="yellow")
    table.add_column("report_hz", style="magenta")
    table.add_column("task_hz", style="magenta")
    table.add_column("期望间隔", style="green")
    table.add_column("实际间隔", style="green")
    table.add_column("结果", style="bold")

    test_cases = [
        # (position, task, report_hz, task_hz, expected_interval, description)
        (True, False, 5.0, 2.0, 0.2, "IVASAdapter位置上报"),
        (False, True, 0.0, 2.0, 0.5, "TaskDistributor任务轮询"),
        (True, True, 5.0, 2.0, 0.2, "全功能（最小值）"),
        (False, False, 0.0, 0.0, float('inf'), "全部禁用"),
    ]

    all_passed = True

    for position, task, report_hz, task_hz, expected, desc in test_cases:
        # 创建客户端（不启动run）
        client = IVASClient(
            device_code=0,
            account='test',
            password='test',
            base_lat=0, base_lon=0, base_alt=0,
            coord_range={'lat_offset': 0, 'lon_offset': 0, 'alt_offset': 0},
            base_url='http://test',
            report_hz=report_hz,
            task_hz=task_hz,
            features={
                'position_report': position,
                'target_report': False,
                'task_receive': task
            }
        )

        # 计算active_interval（模拟run()中的逻辑）
        active_interval = client.report_interval
        if client.features.get('task_receive', True):
            active_interval = min(active_interval, client.task_interval)

        # 验证
        passed = (active_interval == expected)
        result = "✓" if passed else "✗"
        if not passed:
            all_passed = False

        table.add_row(
            desc,
            str(position),
            str(task),
            f"{report_hz:.1f}",
            f"{task_hz:.1f}",
            f"{expected:.3f}s" if expected != float('inf') else "∞",
            f"{active_interval:.3f}s" if active_interval != float('inf') else "∞",
            result
        )

    console.print(table)

    if all_passed:
        console.print("\n[green]✓ 所有睡眠间隔计算正确[/green]")
    else:
        console.print("\n[red]✗ 部分睡眠间隔计算错误[/red]")

    return all_passed


# ============ 测试5: 任务轮询和分发 ============

def test_task_polling_and_distribution():
    """测试任务轮询频率和分发逻辑"""
    console.print("\n[bold cyan]========== 测试5: 任务轮询和分发 ==========[/bold cyan]\n")

    from dashboard.task_distributor import TaskDistributor

    # 创建分发器
    distributor = TaskDistributor(ivas_config={
        'base_url': 'http://test',
        'account': 'test',
        'password': 'test',
        'task_hz': 2.0
    })

    # 模拟adapters
    class MockAdapter:
        def __init__(self, device_code):
            self.device_code = device_code
            self.uav_config = {'callsign': f'无人机{device_code}'}
            self.received_tasks = []

        def receive_task(self, task_data, force_immediate=False):
            self.received_tasks.append({
                'task': task_data,
                'force_immediate': force_immediate
            })

    adapter1 = MockAdapter(1)
    adapter2 = MockAdapter(2)
    adapter3 = MockAdapter(3)

    distributor.register(1, adapter1)
    distributor.register(2, adapter2)
    distributor.register(3, adapter3)
    distributor.finalize()

    # 测试单播路由
    console.print("[bold]测试单播: id=2 → adapter2[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 2, 'mission': 1, 'timestamp': int(time.time())}
    })

    assert len(adapter1.received_tasks) == 0, "adapter1不应收到"
    assert len(adapter2.received_tasks) == 1, "adapter2应收到"
    assert len(adapter3.received_tasks) == 0, "adapter3不应收到"
    console.print("[green]✓ 单播路由正确[/green]")

    # 测试广播
    console.print("\n[bold]测试广播: id=99 → 所有adapters[/bold]")
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 99, 'mission': 1, 'timestamp': int(time.time()) + 1}
    })

    assert len(adapter1.received_tasks) == 1, "adapter1应收到广播"
    assert len(adapter2.received_tasks) == 2, "adapter2应收到2个任务"
    assert len(adapter3.received_tasks) == 1, "adapter3应收到广播"

    # 检查force_immediate标志
    assert adapter1.received_tasks[0]['force_immediate'] == True, "广播任务应标记force_immediate"
    console.print("[green]✓ 广播分发正确，force_immediate=True[/green]")

    # 测试未知ID
    console.print("\n[bold]测试未知ID: id=999[/bold]")
    before_counts = [len(a.received_tasks) for a in [adapter1, adapter2, adapter3]]
    distributor._handle_ivas_log('task', {
        'code': 200,
        'data': {'id': 999, 'mission': 1, 'timestamp': int(time.time()) + 2}
    })
    after_counts = [len(a.received_tasks) for a in [adapter1, adapter2, adapter3]]

    assert before_counts == after_counts, "未知ID不应触发分发"
    console.print("[green]✓ 未知ID正确拒绝[/green]")

    console.print("\n[green]✓ 任务轮询和分发逻辑正确[/green]")
    return True


# ============ 测试6: IVASClient._report_position 处理 None ============

def test_ivas_client_handles_none():
    """测试IVASClient._report_position处理None的情况"""
    console.print("\n[bold cyan]========== 测试6: IVASClient处理GPS无效 ==========[/bold cyan]\n")

    from ivas.client import IVASClient

    # 创建客户端
    client = IVASClient(
        device_code=1,
        account='test',
        password='test',
        base_lat=0, base_lon=0, base_alt=0,
        coord_range={'lat_offset': 0, 'lon_offset': 0, 'alt_offset': 0},
        base_url='http://test',
        report_hz=5.0,
        task_hz=2.0,
        features={'position_report': True, 'target_report': False, 'task_receive': False}
    )

    # Mock登录成功
    client.token = 'test_token'

    # Mock _generate_position_data 返回 None
    client._generate_position_data = Mock(return_value=None)

    # Mock _request（不应该被调用）
    client._request = Mock()

    # 调用_report_position
    client._report_position()

    # 验证：_request不应被调用
    assert client._request.call_count == 0, "_request不应被调用（GPS无效时跳过）"

    console.print("[green]✓ IVASClient正确处理GPS无效情况，跳过HTTP请求[/green]")

    # 测试GPS有效的情况
    client._generate_position_data = Mock(return_value={'deviceCode': 1, 'userX': 23.0, 'userY': 113.0})
    client._request = Mock(return_value=Mock(status_code=200, json=Mock(return_value={})))

    client._report_position()

    assert client._request.call_count == 1, "GPS有效时应调用_request"
    console.print("[green]✓ GPS有效时正常发送HTTP请求[/green]")

    return True


# ============ 主测试流程 ============

def main():
    """运行所有测试"""
    console.print("\n[bold bright_cyan]╔════════════════════════════════════════════════╗[/bold bright_cyan]")
    console.print("[bold bright_cyan]║      IVAS 系统完整性检查               ║[/bold bright_cyan]")
    console.print("[bold bright_cyan]║  位置上报 + 任务分发 + 睡眠间隔        ║[/bold bright_cyan]")
    console.print("[bold bright_cyan]╚════════════════════════════════════════════════╝[/bold bright_cyan]\n")

    tests = [
        ("有GPS时的位置上报", test_position_report_with_gps),
        ("无GPS时的位置上报", test_position_report_without_gps),
        ("GPS恢复场景", test_position_report_gps_recovery),
        ("睡眠间隔计算", test_sleep_interval_calculation),
        ("任务轮询和分发", test_task_polling_and_distribution),
        ("IVASClient处理GPS无效", test_ivas_client_handles_none),
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

    # 总结
    console.print("\n[bold bright_cyan]╔════════════════════════════════════════════════╗[/bold bright_cyan]")
    console.print("[bold bright_cyan]║           测试总结                          ║[/bold bright_cyan]")
    console.print("[bold bright_cyan]╚════════════════════════════════════════════════╝[/bold bright_cyan]\n")

    total = passed + failed
    console.print(f"[bright_white]总计: {total} 个测试[/bright_white]")
    console.print(f"[bright_green]通过: {passed} 个[/bright_green]")

    if failed > 0:
        console.print(f"[bright_red]失败: {failed} 个[/bright_red]")
        console.print("\n[bold red]⚠️ 发现问题，请检查！[/bold red]")
    else:
        console.print("\n[bold bright_green]✓ 所有测试通过！系统运行正常！[/bold bright_green]")
        console.print("[bold bright_green]✓ 位置上报逻辑正确（GPS有效/无效/恢复）[/bold bright_green]")
        console.print("[bold bright_green]✓ 任务轮询和分发逻辑正确（单播/广播/未知ID）[/bold bright_green]")
        console.print("[bold bright_green]✓ 睡眠间隔计算正确（所有场景）[/bold bright_green]")

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
