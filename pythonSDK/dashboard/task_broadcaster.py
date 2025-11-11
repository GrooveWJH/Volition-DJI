"""
IVAS 任务广播管理器

问题：真实IVAS服务器把广播任务(id=99)当普通任务处理，第一个adapter消费后从队列删除，
     导致其他adapter拿不到数据。

解决方案：在dashboard端实现集中式广播管理器
- 第一个收到id=99任务的adapter触发广播
- 广播给所有adapter并执行
- 任务去重防止重复执行

设计原则：
- 简单直接，不使用复杂设计模式
- 线程安全（使用锁保护共享状态）
- 优雅降级（没有broadcaster时adapter独立工作）
"""
import threading
import time
from typing import List, Dict, Any, Optional
from rich.console import Console

console = Console()


class TaskBroadcaster:
    """
    全局任务广播管理器（单例模式）

    职责：
    1. 注册所有 IVASAdapter 实例
    2. 检测广播任务（id=99）
    3. 分发给所有adapter
    4. 任务去重（避免重复执行）
    """

    def __init__(self):
        """初始化广播管理器"""
        self.adapters: List[Any] = []  # IVASAdapter 实例列表
        self.lock = threading.Lock()  # 线程安全锁
        self.executed_tasks = set()  # 已执行任务ID集合（去重）
        self.finalized = False  # 是否已完成注册

    def register_adapter(self, adapter) -> None:
        """
        注册 IVASAdapter 实例

        Args:
            adapter: IVASAdapter 实例
        """
        with self.lock:
            self.adapters.append(adapter)
            console.print(
                f"[dim][TaskBroadcaster] 注册适配器 #{len(self.adapters)} "
                f"(device_code={adapter.device_code})[/dim]"
            )

    def finalize(self) -> None:
        """
        完成所有adapter注册

        调用此方法后，不再接受新的adapter注册
        """
        with self.lock:
            self.finalized = True
            console.print(
                f"[green][TaskBroadcaster] 已完成注册，共 {len(self.adapters)} 个适配器[/green]"
            )

    def broadcast_task(self, task_data: Dict[str, Any], source_adapter) -> bool:
        """
        广播任务给所有adapter（由第一个收到任务的adapter触发）

        Args:
            task_data: IVAS 任务数据（包含 id, mission 等字段）
            source_adapter: 触发广播的adapter（用于日志）

        Returns:
            是否成功广播（False表示任务已执行过，跳过）
        """
        task_id = task_data.get('id', 0)
        mission = task_data.get('mission', 0)

        # 检查是否为广播任务
        if task_id != 99:
            console.print(
                f"[yellow][TaskBroadcaster] 任务 ID={task_id} 不是广播任务，跳过[/yellow]"
            )
            return False

        # 检查任务类型是否支持广播
        if mission not in [1, 2, 3]:
            mission_names = {
                1: "起飞", 2: "降落", 3: "返航", 4: "前往指定点",
                5: "多航点任务1", 6: "多航点任务2", 7: "多航点任务3"
            }
            console.print(
                f"[red][TaskBroadcaster] 任务类型 {mission_names.get(mission, mission)} "
                f"不支持广播（id=99），仅支持起飞/降落/返航[/red]"
            )
            return False

        # 任务去重（使用 mission+timestamp 作为唯一标识）
        task_signature = f"{mission}_{task_data.get('timestamp', int(time.time()))}"

        with self.lock:
            if task_signature in self.executed_tasks:
                console.print(
                    f"[dim][TaskBroadcaster] 任务 {task_signature} 已执行过，跳过重复广播[/dim]"
                )
                return False

            # 标记任务已执行
            self.executed_tasks.add(task_signature)

            # 清理旧的任务记录（保留最近100条）
            if len(self.executed_tasks) > 100:
                # 转换为列表后删除最旧的50条
                old_tasks = list(self.executed_tasks)[:50]
                for old_task in old_tasks:
                    self.executed_tasks.discard(old_task)

        # 广播给所有adapter
        mission_names = {1: "起飞", 2: "降落", 3: "返航"}
        mission_name = mission_names.get(mission, f"任务{mission}")

        console.print(
            f"[bold cyan][TaskBroadcaster] 广播任务: {mission_name} (ID:{task_id}) "
            f"→ {len(self.adapters)} 个设备[/bold cyan]"
        )

        success_count = 0
        for i, adapter in enumerate(self.adapters):
            try:
                # 调用adapter的广播接收方法
                adapter.receive_broadcast_task(task_data)
                success_count += 1
                console.print(
                    f"[green]  ✓ 设备 {adapter.device_code} ({adapter.uav_config['callsign']}) "
                    f"已接收任务[/green]"
                )
            except Exception as e:
                console.print(
                    f"[red]  ✗ 设备 {adapter.device_code} 接收任务失败: {e}[/red]"
                )

        console.print(
            f"[bold green][TaskBroadcaster] 广播完成: {success_count}/{len(self.adapters)} "
            f"个设备成功接收[/bold green]"
        )

        return True

    def get_adapter_count(self) -> int:
        """获取已注册adapter数量"""
        with self.lock:
            return len(self.adapters)

    def is_finalized(self) -> bool:
        """检查是否已完成注册"""
        with self.lock:
            return self.finalized
