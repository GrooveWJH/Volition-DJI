"""
Dashboard - 多无人机实时监控系统

使用方式:
    from dashboard import run
    run()

或者:
    python -m dashboard
"""

from .config import (
    MQTT_CONFIG,
    UAV_CONFIGS,
    OSD_FREQUENCY,
    HSI_FREQUENCY,
    GUI_REFRESH_RATE,
    OFFLINE_TIMEOUT,
    ENABLE_VRPN,
    SKIP_DRC_SETUP,
    HEARTBEAT_INTERVAL,
    # IVAS 配置
    ENABLE_IVAS,
    IVAS_FEATURES,
    IVAS_SERVER,
)

__all__ = [
    'run',
    'MQTT_CONFIG',
    'UAV_CONFIGS',
    'OSD_FREQUENCY',
    'HSI_FREQUENCY',
    'GUI_REFRESH_RATE',
    'OFFLINE_TIMEOUT',
    'ENABLE_VRPN',
    'SKIP_DRC_SETUP',
    'HEARTBEAT_INTERVAL',
    # IVAS
    'ENABLE_IVAS',
    'IVAS_FEATURES',
    'IVAS_SERVER',
]

__version__ = '1.0.0'


def run():
    """运行 Dashboard 监控系统"""
    from .monitor import run as monitor_run
    monitor_run()


# 支持 python -m dashboard
if __name__ == '__main__':
    run()
