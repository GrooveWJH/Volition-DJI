"""
IVAS 线程函数 - 统一导出入口

为保持向后兼容，所有函数已拆分到独立模块：
- reporters.py: 所有上报线程（户外 + 室内）
- task_dispatcher.py: 任务轮询和分发

设计原则：
- 纯函数，无状态
- 精确定时（使用 perf_counter）
- 通过 stop_event 优雅退出
"""

# ========== 户外系统上报线程 ==========

from .reporters import (
    position_reporter,
    target_reporter,
    fake_target_reporter,
)

# ========== 室内系统上报线程 ==========

from .reporters import (
    uwb_position_reporter,
    uwb_trigger_target_reporter,
)

# ========== 任务分发控制 ==========

from .task_dispatcher import (
    task_poller,
    task_mqtt_forwarder,
)

# ========== 统一导出 ==========

__all__ = [
    # 户外上报
    'position_reporter',
    'target_reporter',
    'fake_target_reporter',
    # 室内上报
    'uwb_position_reporter',
    'uwb_trigger_target_reporter',
    # 任务分发
    'task_poller',
    'task_mqtt_forwarder',
]
