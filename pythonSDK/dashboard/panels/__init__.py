"""
Panels 包 - Dashboard UI 组件

模块化的面板生成系统，包括：
- UAV 面板：无人机实时数据监控
- VRPN 面板：动捕系统数据显示
- Layout：整体布局组织

所有面板遵循统一的设计风格和 Rich 库的使用规范。
"""

from .uav_panel import create_uav_panel, create_battery_bar
from .vrpn_panel import create_vrpn_panel
from .layout import create_dashboard_layout

__all__ = [
    # UAV 面板
    'create_uav_panel',
    'create_battery_bar',
    # VRPN 面板
    'create_vrpn_panel',
    # 布局
    'create_dashboard_layout',
]

__version__ = '1.0.0'
