"""
DJI Cloud API Python SDK

专业级 DJI 无人机云端控制 Python 库，支持远程控制 (DRC)、实时视频、飞行任务、多机编队等功能。
采用模块化设计，从简单控制到复杂任务编排都能轻松应对。

主要功能：
- 完整的 DRC 控制：连接管理、控制权申请、DRC 模式、心跳维持
- 专业视频直播：多镜头支持、画质控制、RTMP/RTSP 推流
- 高级飞行任务：轨迹飞行、任务编排、并行执行
- 智能数据管理：实时监控、状态追踪、频率监控

快速开始：
    >>> from djisdk import setup_drc_connection, fly_to_point, return_home
    >>> mqtt, caller, heartbeat = setup_drc_connection(gateway_sn, mqtt_config)
    >>> fly_to_point(caller, latitude=39.042751, longitude=117.723825, height=100.0)
    >>> return_home(caller)

详细文档：
- README.md - 完整使用指南
- API.md - API参考文档
"""
from .core import MQTTClient, ServiceCaller
from .services import (
    request_control_auth,
    release_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    change_live_lens,
    start_live_push,
    stop_live_push,
    return_home,
    fly_to_point,
    start_heartbeat,
    stop_heartbeat,
    send_stick_control,
    set_camera_zoom,
    camera_look_at,
    camera_aim,
    reset_gimbal,
    setup_drc_connection,
    setup_multiple_drc_connections,
    DRCConnectionManager,
    ConnectionState,
)
from .utils import (
    print_json_message,
    get_key,
    wait_for_camera_data,
    build_video_id,
)
from .live_utils import (
    start_live,
    stop_live,
    set_live_quality,  # 使用带详细日志的版本
    zoom_control_loop,
)
from .primitives import (
    wait_for_condition,
    send_stick_repeatedly,
    fly_to_waypoint,
    monitor_flyto_progress,
)
from .tasks import (
    MissionRunner,
    run_parallel_missions,
    cleanup_missions,
    create_takeoff_mission,
    load_trajectory,
    fly_trajectory_sequence,
    create_trajectory_mission,
    create_takeoff_table,
    create_trajectory_table,
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
    'return_home',
    'fly_to_point',
    'start_heartbeat',
    'stop_heartbeat',
    'send_stick_control',
    'set_camera_zoom',
    'camera_look_at',
    'camera_aim',
    'reset_gimbal',
    'setup_drc_connection',
    'setup_multiple_drc_connections',
    'DRCConnectionManager',
    'ConnectionState',
    # Utils
    'print_json_message',
    'get_key',
    'wait_for_camera_data',
    'build_video_id',
    # Live Utils
    'start_live',
    'stop_live',
    'zoom_control_loop',
    # Primitives
    'wait_for_condition',
    'send_stick_repeatedly',
    'fly_to_waypoint',
    'monitor_flyto_progress',
    # Tasks
    'MissionRunner',
    'run_parallel_missions',
    'cleanup_missions',
    'create_takeoff_mission',
    'load_trajectory',
    'fly_trajectory_sequence',
    'create_trajectory_mission',
    'create_takeoff_table',
    'create_trajectory_table',
]
