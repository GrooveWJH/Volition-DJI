"""
DJI 服务模块
"""
from .commands import (
    request_control_auth,
    release_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    change_live_lens,
    set_live_quality,
    start_live_push,
    stop_live_push,
)
from .heartbeat import start_heartbeat, stop_heartbeat

__all__ = [
    # 控制权
    'request_control_auth',
    'release_control_auth',
    # DRC 模式
    'enter_drc_mode',
    'exit_drc_mode',
    # 直播
    'change_live_lens',
    'set_live_quality',
    'start_live_push',
    'stop_live_push',
    # 心跳
    'start_heartbeat',
    'stop_heartbeat',
]
