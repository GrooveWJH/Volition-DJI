"""
IVAS 线程生命周期管理器

提供统一的线程管理接口，消除重复的线程启动/停止代码。

设计目标：
- 零重复：所有线程使用统一的 spawn() / stop_all() 接口
- 类型安全：ManagedThread 封装线程 + stop_event
- 优雅退出：自动处理线程停止和超时
"""

from dataclasses import dataclass
from typing import Callable, List, Any, Dict
import threading
from rich.console import Console

console = Console()


@dataclass
class ManagedThread:
    """
    线程 + 停止事件的封装

    Attributes:
        name: 线程名称（用于日志显示）
        thread: threading.Thread 对象
        stop_event: threading.Event 停止信号
    """
    name: str
    thread: threading.Thread
    stop_event: threading.Event

    def stop(self, timeout: float = 2.0):
        """
        优雅停止线程

        Args:
            timeout: 等待超时时间（秒）
        """
        self.stop_event.set()
        self.thread.join(timeout=timeout)


class ThreadManager:
    """
    线程生命周期管理器

    使用方式:
        manager = ThreadManager()

        # 启动线程（stop_event 自动管理）
        manager.spawn(
            "position-reporter",
            uwb_position_reporter,
            uwb_position, ivas_client, device_code, ...
        )

        # 优雅停止所有线程
        manager.stop_all()
    """

    def __init__(self):
        self.threads: List[ManagedThread] = []

    def spawn(
        self,
        name: str,
        target: Callable,
        *args,
        **kwargs
    ) -> ManagedThread:
        """
        创建并启动线程

        Args:
            name: 线程名称（用于日志和调试）
            target: 线程目标函数
            *args: 传递给 target 的位置参数
            **kwargs: 传递给 target 的关键字参数

        Returns:
            ManagedThread: 托管的线程对象

        重要：
            target 函数必须接受一个 stop_event 参数（通常是最后一个参数）
            ThreadManager 会自动创建 stop_event 并追加到 args
        """
        stop_event = threading.Event()

        # 自动追加 stop_event 到参数列表
        thread = threading.Thread(
            target=target,
            args=args + (stop_event,),
            kwargs=kwargs,
            daemon=True,
            name=name
        )

        managed = ManagedThread(name, thread, stop_event)
        thread.start()
        self.threads.append(managed)

        console.print(f"[bright_green]✓ 线程 {name} 已启动[/bright_green]")
        return managed

    def stop_all(self, timeout: float = 2.0):
        """
        优雅停止所有线程

        Args:
            timeout: 每个线程的等待超时时间（秒）
        """
        if not self.threads:
            return

        console.print("\n[bold]🧹 停止所有线程...[/bold]")

        for t in self.threads:
            console.print(f"[bright_cyan]停止 {t.name}...[/bright_cyan]")
            t.stop(timeout)
            console.print(f"[bright_green]✓ {t.name} 已停止[/bright_green]")

    def __len__(self) -> int:
        """返回管理的线程数量"""
        return len(self.threads)
