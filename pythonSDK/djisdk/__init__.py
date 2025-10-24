"""
DJI DRC Python SDK

简洁实用的 DJI 无人机远程控制工具包
"""
from .core import MQTTClient, ServiceCaller
from .services import (
    request_control_auth,
    release_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    change_live_lens,
    set_live_quality,
    start_live_push,
    stop_live_push,
    start_heartbeat,
    stop_heartbeat,
    send_stick_control,
    setup_drc_connection,
    setup_multiple_drc_connections,
)

__version__ = '1.0.0'

__all__ = [
    # Core
    'MQTTClient',
    'ServiceCaller',
    # Services
    'request_control_auth',
    'release_control_auth',
    'enter_drc_mode',
    'exit_drc_mode',
    'change_live_lens',
    'set_live_quality',
    'start_live_push',
    'stop_live_push',
    'start_heartbeat',
    'stop_heartbeat',
    'send_stick_control',
    'setup_drc_connection',
    'setup_multiple_drc_connections',
]
