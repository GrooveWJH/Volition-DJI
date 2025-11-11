"""
IVAS 任务分发器 - 单点轮询，智能路由

职责：
1. 单点轮询IVAS服务器（避免多个adapter竞争消费）
2. 根据任务ID智能路由：id=99广播，id=1/2/3单播
3. 内置广播逻辑（去重+类型验证）

设计原则：
- 简单直接，用字典映射消除if/else特殊情况
- 线程安全（注册时加锁，运行时只读）
- 统一分发接口（广播和单播都是分发）
"""
import sys
import os
import time
import threading
from typing import Dict, Any, Optional
from rich.console import Console

# 添加 ivas 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ivas'))

from ivas import IVASClient

console = Console()


class TaskDistributor:
    """
    统一任务分发器

    核心数据结构：
    - adapters: {device_code: IVASAdapter}  # adapter映射表
    - executed_tasks: set()                 # 广播任务去重

    职责：
    - 单点轮询IVAS服务器
    - 单播分发：id=1/2/3 → 对应adapter
    - 广播分发：id=99 → 所有adapters（内置去重+验证）
    """

    def __init__(self, ivas_config: Dict[str, Any]):
        """
        初始化任务分发器

        Args:
            ivas_config: IVAS配置（base_url, account, password, task_hz）
        """
        self.adapters: Dict[int, Any] = {}  # device_code → adapter
        self.executed_tasks = set()  # 广播任务去重（task_signature）
        self.lock = threading.Lock()  # 保护共享数据
        self.finalized = False
        self.thread: Optional[threading.Thread] = None

        # 创建IVASClient用于轮询（复用现有代码）
        # 关键：deviceCode设为0，因为不再用于过滤
        self.ivas_client = IVASClient(
            device_code=0,  # 占位符，不用于过滤
            account=ivas_config['account'],
            password=ivas_config['password'],
            base_lat=0.0, base_lon=0.0, base_alt=0.0,
            coord_range={'lat_offset': 0, 'lon_offset': 0, 'alt_offset': 0},
            base_url=ivas_config['base_url'],
            report_hz=0.0,  # 禁用位置上报
            task_hz=ivas_config['task_hz'],
            features={
                'position_report': False,
                'target_report': False,
                'task_receive': True  # 只启用任务轮询
            }
        )

        # 覆盖任务处理方法
        self.ivas_client._log = self._handle_ivas_log

        console.print("[dim][TaskDistributor] 任务分发器初始化完成[/dim]")

    def register(self, device_code: int, adapter) -> None:
        """
        注册adapter（初始化阶段调用）

        Args:
            device_code: 设备编号（1, 2, 3等）
            adapter: IVASAdapter实例
        """
        with self.lock:
            if self.finalized:
                raise RuntimeError("Cannot register after finalization")
            self.adapters[device_code] = adapter
            console.print(f"[dim][TaskDistributor] 注册 device_code={device_code}[/dim]")

    def finalize(self) -> None:
        """
        完成注册（之后adapters变为只读）

        调用此方法后：
        - 不再接受新的adapter注册
        - adapters字典变为只读（无需加锁访问）
        """
        with self.lock:
            self.finalized = True
            console.print(f"[green][TaskDistributor] 注册完成，共 {len(self.adapters)} 个设备[/green]")

    def start(self) -> None:
        """启动轮询线程"""
        if not self.finalized:
            raise RuntimeError("Must finalize before start")

        self.thread = threading.Thread(
            target=self.ivas_client.run,
            daemon=True
        )
        self.thread.start()
        console.print("[green][TaskDistributor] 轮询线程已启动[/green]")

    def stop(self) -> None:
        """停止轮询"""
        self.ivas_client.stop()
        if self.thread:
            self.thread.join(timeout=2.0)

    def _handle_ivas_log(self, log_type: str, data: Any) -> None:
        """
        处理IVASClient的日志输出（覆盖IVASClient._log）

        这是任务接收的入口点，解析任务并分发。

        Args:
            log_type: 日志类型（只关心'task'）
            data: 日志数据
        """
        if log_type != 'task':
            return

        # 解析任务数据
        if not isinstance(data, dict) or data.get('code') != 200:
            return

        task_data = data.get('data')
        if not task_data:
            return

        target_id = task_data.get('id', 0)
        mission = task_data.get('mission', 0)

        # 路由分发
        if target_id == 99:
            # 广播模式：分发给所有adapter
            self._distribute_broadcast(task_data)
        elif target_id in self.adapters:
            # 单播模式：分发给指定adapter
            console.print(f"[cyan][TaskDistributor] 路由任务到 device_code={target_id} (mission={mission})[/cyan]")
            adapter = self.adapters[target_id]
            adapter.receive_task(task_data)
        else:
            # 未知ID
            console.print(f"[yellow][TaskDistributor] ⚠️ 未知任务ID: {target_id} (mission={mission})[/yellow]")

    def _distribute_broadcast(self, task_data: Dict[str, Any]) -> None:
        """
        广播分发（原TaskBroadcaster的逻辑）

        步骤：
        1. 验证任务类型（只有1/2/3支持广播）
        2. 任务去重（避免重复执行）
        3. 分发给所有adapter

        Args:
            task_data: IVAS任务数据
        """
        mission = task_data.get('mission', 0)
        mission_names = {1: "起飞", 2: "降落", 3: "返航"}

        # 1. 类型验证：只有1/2/3支持广播
        if mission not in [1, 2, 3]:
            mission_names_full = {
                1: "起飞", 2: "降落", 3: "返航", 4: "前往指定点",
                5: "多航点任务1", 6: "多航点任务2", 7: "多航点任务3"
            }
            console.print(
                f"[red][TaskDistributor] 任务类型 {mission_names_full.get(mission, mission)} "
                f"不支持广播（id=99），仅支持起飞/降落/返航[/red]"
            )
            return

        # 2. 任务去重（使用 mission+timestamp 作为唯一标识）
        task_signature = f"{mission}_{task_data.get('timestamp', int(time.time()))}"

        with self.lock:
            if task_signature in self.executed_tasks:
                console.print(
                    f"[dim][TaskDistributor] 任务 {task_signature} 已执行过，跳过重复广播[/dim]"
                )
                return

            # 标记任务已执行
            self.executed_tasks.add(task_signature)

            # 清理旧任务记录（保留最近100条）
            if len(self.executed_tasks) > 100:
                old_tasks = list(self.executed_tasks)[:50]
                for old_task in old_tasks:
                    self.executed_tasks.discard(old_task)

        # 3. 广播分发
        mission_name = mission_names.get(mission, f"任务{mission}")
        console.print(
            f"[bold cyan][TaskDistributor] 广播任务: {mission_name} (ID:99) "
            f"→ {len(self.adapters)} 个设备[/bold cyan]"
        )

        success_count = 0
        for device_code, adapter in self.adapters.items():
            try:
                # 调用adapter的接收方法（所有任务强制立即执行）
                adapter.receive_task(task_data)
                success_count += 1
                console.print(
                    f"[green]  ✓ 设备 {device_code} 已接收任务[/green]"
                )
            except Exception as e:
                console.print(
                    f"[red]  ✗ 设备 {device_code} 接收任务失败: {e}[/red]"
                )

        console.print(
            f"[bold green][TaskDistributor] 广播完成: {success_count}/{len(self.adapters)} "
            f"个设备成功接收[/bold green]"
        )

    def get_adapter_count(self) -> int:
        """获取已注册adapter数量"""
        return len(self.adapters)
