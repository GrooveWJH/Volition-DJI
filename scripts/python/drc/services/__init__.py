"""
DRC 服务模块
"""
from .auth import request_control_auth, release_control_auth
from .drc_mode import enter_drc_mode, exit_drc_mode
from .live import change_live_lens, set_live_quality, start_live_push, stop_live_push
from .heartbeat import HeartbeatKeeper

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
    'HeartbeatKeeper',
]
