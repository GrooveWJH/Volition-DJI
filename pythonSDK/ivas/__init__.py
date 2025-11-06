"""
IVAS Python SDK

提供与 IVAS 服务器交互的客户端工具。

主要功能：
- 无人机位置数据上报
- 目标检测数据上报
- 任务轮询
- 自动 token 管理和过期处理

使用示例:
    from ivas import IVASClient

    client = IVASClient(
        device_code=1,
        account='ZSDX001',
        password='your_password',
        base_lat=23.0,
        base_lon=113.0,
        base_alt=100.0,
        coord_range={
            'lat_offset': 0.001,
            'lon_offset': 0.001,
            'alt_offset': 10.0
        },
        base_url='http://localhost:5001',
        report_hz=1.0,
        task_hz=0.2
    )

    client.run()
"""

from .client import IVASClient

__version__ = '1.0.0'
__author__ = 'IVAS Team'
__all__ = ['IVASClient']
