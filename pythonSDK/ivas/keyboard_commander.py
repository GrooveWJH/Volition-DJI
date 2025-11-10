#!/usr/bin/env python3
"""
IVAS 键盘控制器 - 通过键盘发送任务指令

用于本地测试，替代真实 IVAS 服务器发送任务。

使用方法：
    python ivas/keyboard_commander.py
"""
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# 任务菜单配置
MISSIONS = {
    '1': {'name': '起飞10米', 'mission': 1, 'needs_coords': False},
    '2': {'name': '降落', 'mission': 2, 'needs_coords': False},
    '3': {'name': '返航', 'mission': 3, 'needs_coords': False},
    '4': {'name': '飞向指定点', 'mission': 4, 'needs_coords': True},
    '5': {'name': '轨迹任务1', 'mission': 5, 'needs_coords': False},
    '6': {'name': '轨迹任务2', 'mission': 6, 'needs_coords': False},
    '7': {'name': '轨迹任务3', 'mission': 7, 'needs_coords': False},
}


def send_task_to_mock_server(base_url: str, device_id: int, mission_data: dict) -> bool:
    """
    发送任务到 Mock Server

    Args:
        base_url: Mock Server 地址
        device_id: 设备 ID (1-3 或 99，仅用于向后兼容)
        mission_data: 任务数据（包含 id 字段，99=广播）

    Returns:
        bool: 发送成功返回 True，失败返回 False

    注意：
        - 广播逻辑在 server 端实现（检测 task['id']==99）
        - 客户端只负责发送任务数据
    """
    try:
        resp = requests.post(
            f"{base_url}/mock/push_task",
            json={'device_id': device_id, 'task': mission_data},
            timeout=3
        )

        if resp.status_code == 200:
            result = resp.json()
            # 如果服务器返回了广播信息，显示出来
            if result.get('broadcast'):
                devices = result.get('devices', [])
                console.print(f"[green]✓ 服务器已广播到设备: {devices}[/green]")
            return True
        else:
            # 处理错误响应
            try:
                error_data = resp.json()
                console.print(f"[red]服务器拒绝: {error_data.get('message', '未知错误')}[/red]")
            except:
                pass
            return False

    except Exception as e:
        console.print(f"[red]发送失败: {e}[/red]")
        return False


def create_menu_table(current_device: int) -> Table:
    """创建任务菜单表格"""
    table = Table(title="[bold cyan]IVAS 任务菜单[/bold cyan]", show_header=True)
    table.add_column("按键", style="bold yellow", justify="center", width=6)
    table.add_column("任务名称", style="bright_white", width=18)
    table.add_column("任务类型", style="cyan", width=20)

    for key, mission in MISSIONS.items():
        mission_type = f"mission={mission['mission']}"
        if mission['needs_coords']:
            mission_type += " (需坐标)"

        table.add_row(key, mission['name'], mission_type)

    table.add_row("", "", "")

    # 显示当前设备（带广播提示）
    device_display = f"设备 {current_device}"
    if current_device == 99:
        device_display = "[bold magenta]所有设备 (广播)[/bold magenta]"

    table.add_row("k", f"切换设备", f"[dim]当前: {device_display}[/dim]")
    table.add_row("", "", "[dim]1-3=单机 | 99=所有设备[/dim]")
    table.add_row("s", "查看统计", "[dim]Mock Server 状态[/dim]")
    table.add_row("c", "清空队列", "[dim]清空所有任务[/dim]")
    table.add_row("q", "退出", "[dim]关闭程序[/dim]")

    return table


def get_server_stats(base_url: str) -> dict:
    """
    获取 Mock Server 统计信息

    Args:
        base_url: Mock Server 地址

    Returns:
        dict: 统计信息字典
    """
    try:
        resp = requests.get(f"{base_url}/mock/stats", timeout=3)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {}
    except Exception as e:
        console.print(f"[red]获取统计失败: {e}[/red]")
        return {}


def clear_server_queues(base_url: str) -> bool:
    """
    清空 Mock Server 所有任务队列

    Args:
        base_url: Mock Server 地址

    Returns:
        bool: 成功返回 True
    """
    try:
        resp = requests.post(f"{base_url}/mock/clear", timeout=3)
        if resp.status_code == 200:
            result = resp.json()
            console.print(f"[green]✓ 已清空所有队列，共清除 {result['cleared']} 个任务[/green]")
            return True
        else:
            return False
    except Exception as e:
        console.print(f"[red]清空失败: {e}[/red]")
        return False


def main():
    """主函数"""
    # 配置
    BASE_URL = "http://localhost:5001"
    current_device_id = 1  # 初始设备

    # 显示标题
    console.print(Panel.fit(
        "[bold cyan]IVAS 键盘控制器[/bold cyan]\n"
        f"[dim]Mock Server: {BASE_URL}[/dim]",
        border_style="cyan"
    ))
    console.print()

    # 主循环
    while True:
        # 显示菜单（带当前设备提示）
        console.print(create_menu_table(current_device_id))

        # 显示当前控制设备（特殊高亮广播模式）
        if current_device_id == 99:
            console.print(f"\n[bold bright_magenta]当前控制模式: 广播模式 (所有设备)[/bold bright_magenta]")
        else:
            console.print(f"\n[bold bright_magenta]当前控制设备: {current_device_id}[/bold bright_magenta]")

        console.print()

        # 获取用户输入
        choice = console.input("[bold yellow]选择任务 (输入按键): [/bold yellow]").strip().lower()

        if choice == 'q':
            console.print("[cyan]退出程序[/cyan]")
            break

        elif choice == 'k':
            # 切换设备
            console.print(f"\n[cyan]当前控制设备: {current_device_id}[/cyan]")
            try:
                new_device = int(console.input("[yellow]输入新的设备 ID (1-3 单机 | 99 所有): [/yellow]").strip())
                if (1 <= new_device <= 3) or new_device == 99:
                    current_device_id = new_device
                    if new_device == 99:
                        console.print(f"[bold green]✓ 已切换到 [bold magenta]广播模式[/bold magenta] (所有设备)[/bold green]\n")
                    else:
                        console.print(f"[green]✓ 已切换到设备 {current_device_id}[/green]\n")
                else:
                    console.print("[red]✗ 设备 ID 必须是 1-3 或 99[/red]\n")
            except ValueError:
                console.print("[red]✗ 请输入有效的数字[/red]\n")

        elif choice == 's':
            # 查看统计
            console.print("\n[cyan]正在获取统计信息...[/cyan]")
            stats = get_server_stats(BASE_URL)

            if stats:
                console.print(f"\n[bold green]Mock Server 统计[/bold green]")
                console.print(f"  任务推送总数: {stats['stats']['tasks_pushed']}")
                console.print(f"  任务拉取总数: {stats['stats']['tasks_fetched']}")
                console.print(f"  当前队列状态:")
                for device_id, queue_size in stats['queues'].items():
                    console.print(f"    设备 {device_id}: {queue_size} 个任务")
            console.print()

        elif choice == 'c':
            # 清空队列
            console.print("\n[yellow]正在清空所有任务队列...[/yellow]")
            clear_server_queues(BASE_URL)
            console.print()

        elif choice in MISSIONS:
            # 发送任务
            mission_config = MISSIONS[choice]
            mission_data = {
                'mission': mission_config['mission'],
                'id': current_device_id
            }

            # 任务4需要额外坐标
            if mission_config['needs_coords']:
                console.print(f"\n[cyan]任务 {mission_config['name']} 需要提供坐标信息[/cyan]")
                try:
                    lat = float(console.input("  纬度 (latitude): "))
                    lon = float(console.input("  经度 (longitude): "))
                    alt = float(console.input("  高度 (altitude, 米): "))

                    mission_data.update({'lat': lat, 'lon': lon, 'alt': alt})
                except ValueError:
                    console.print("[red]✗ 坐标格式错误，请输入数字[/red]\n")
                    continue

            # 发送任务
            if current_device_id == 99:
                console.print(f"\n[bold magenta]正在广播任务: {mission_config['name']} → 所有设备...[/bold magenta]")
            else:
                console.print(f"\n[cyan]正在发送任务: {mission_config['name']} → 设备 {current_device_id}...[/cyan]")

            if send_task_to_mock_server(BASE_URL, current_device_id, mission_data):
                if current_device_id == 99:
                    console.print(f"[bold green]✓ 任务已广播到所有设备[/bold green]")
                else:
                    console.print(f"[bold green]✓ 任务已推送到 Mock Server[/bold green]")
                console.print(f"[dim]IVAS Client 将在下次轮询时接收此任务[/dim]\n")
            else:
                console.print(f"[bold red]✗ 任务发送失败[/bold red]\n")

        else:
            console.print(f"[red]✗ 无效按键: {choice}[/red]\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]程序被中断 (Ctrl+C)[/yellow]")
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
