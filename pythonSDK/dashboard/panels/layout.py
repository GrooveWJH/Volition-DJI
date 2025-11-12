"""
布局模块

负责组织和排列所有面板，生成最终的 Dashboard 布局。

布局策略：
- UAV 面板：3列固定网格（不换行）
- VRPN 面板：与 UAV 面板横向合并
"""
from typing import List, Dict, Any, Optional
from rich.table import Table
from rich.columns import Columns

from .uav_panel import create_uav_panel
from .vrpn_panel import create_vrpn_panel


def create_dashboard_layout(
    uav_clients: List[Dict[str, Any]],
    vrpn_clients: List[Optional[Dict[str, Any]]],
    uav_configs: List[Dict[str, str]],
    elapsed: int,
    offline_timeout: float = 2.0,
):
    """
    生成整个 Dashboard 布局（3列UAV网格）

    多架无人机以3列网格形式显示：
    - 1-3架：第1行
    - 4-6架：第2行
    - 以此类推

    使用 Table 布局确保无论终端宽度如何，始终保持3列不换行。

    Args:
        uav_clients: 无人机客户端列表
        vrpn_clients: VRPN 客户端列表（可为空）
        uav_configs: 无人机配置列表
        elapsed: 运行时间（秒）
        offline_timeout: 离线超时时间（秒）

    Returns:
        Rich 可渲染对象
    """
    panels = []

    for i, uav in enumerate(uav_clients):
        # 创建 DJI 面板
        uav_panel = create_uav_panel(uav, uav_configs[i], elapsed, offline_timeout)

        # 如果有对应的 VRPN 数据，横向合并显示
        if vrpn_clients and i < len(vrpn_clients) and vrpn_clients[i] is not None:
            vrpn_client = vrpn_clients[i]['client']
            device_name = vrpn_clients[i]['device_name']
            vrpn_panel = create_vrpn_panel(vrpn_client, device_name, elapsed)
            # 横向合并两个面板
            merged_panel = Columns([uav_panel, vrpn_panel], equal=False, expand=False, padding=0)
            panels.append(merged_panel)
        else:
            panels.append(uav_panel)

    # 创建 UAV 网格
    if len(panels) == 1:
        return panels[0]
    else:
        # 多机：使用 Table 实现固定3列网格（不会自动换行）
        uav_grid = Table.grid(padding=0)

        # 添加3列
        for _ in range(3):
            uav_grid.add_column(justify="left")

        # 按每3个面板一行添加到表格
        for i in range(0, len(panels), 3):
            row_panels = panels[i:i+3]
            # 不足3个时用空字符串填充（避免布局错乱）
            while len(row_panels) < 3:
                row_panels.append("")
            uav_grid.add_row(*row_panels)

        return uav_grid
