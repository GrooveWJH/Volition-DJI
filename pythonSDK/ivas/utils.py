"""
IVAS 辅助函数

通用的辅助函数，用于IVAS系统的各种操作。
"""

import time


def build_report_url(
    base_url: str,
    ivas_user_info_id: int,
    device_code: int,
    lat: float,
    lon: float,
    alt: float,
    azimuth: int,
    motion: int,
    user_name: str,
    room_id: int = 22
) -> str:
    """
    构建 IVAS 位置上报的完整 URL（用于调试）

    Args:
        base_url: IVAS 服务器基础 URL
        ivas_user_info_id: IVAS 用户信息 ID
        device_code: 设备编号
        lat: 纬度
        lon: 经度
        alt: 高度（米）
        azimuth: 航向角（度）
        motion: 运动状态（0:静止, 1:运动）
        user_name: 用户名称
        room_id: 房间ID（默认22）

    Returns:
        完整的 HTTP GET 请求 URL（带所有参数）
    """
    local_time = int(time.time() * 1000)

    return (
        f"{base_url}/jk-ivas/third/controller/reportUserData?"
        f"ivasUserInfoId={ivas_user_info_id}&"
        f"deviceCode={device_code}&"
        f"userX={lat:.6f}&"
        f"userY={lon:.6f}&"
        f"userZ={alt:.4f}&"
        f"azimuth={azimuth}&"
        f"localTime={local_time}&"
        f"motion={motion}&"
        f"validCount=10&"
        f"roomId={room_id}&"
        f"refPositionType=0&"
        f"userName={user_name}"
    )
