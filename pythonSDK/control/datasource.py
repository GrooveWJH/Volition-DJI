"""
数据源抽象层
提供统一的位置和航向角数据获取接口，支持多种数据源切换

支持的数据源:
  - 位置数据: VRPN, UWB
  - 航向角数据: VRPN, 无人机自身姿态

使用示例:
    from control.datasource import create_datasource
    from control.config import POSITION_SOURCE, YAW_SOURCE

    # 创建数据源
    datasource = create_datasource(
        position_source=POSITION_SOURCE,
        yaw_source=YAW_SOURCE,
        vrpn_client=vrpn_client,
        mqtt_client=mqtt_client,
        uwb_client=uwb_client  # 可选
    )

    # 获取数据
    x, y, z = datasource.get_position()
    yaw = datasource.get_yaw()
"""

from typing import Optional, Tuple
from abc import ABC, abstractmethod
import math


def quaternion_to_yaw(quat):
    """
    从四元数提取Yaw角（偏航角）

    Args:
        quat: 四元数格式 (qx, qy, qz, qw)

    Returns:
        Yaw角度（度），范围 [-180, 180]
    """
    qx, qy, qz, qw = quat
    yaw_rad = math.atan2(2.0 * (qw * qz + qx * qy),
                         1.0 - 2.0 * (qy * qy + qz * qz))
    return math.degrees(yaw_rad)


class DataSource(ABC):
    """数据源抽象基类"""

    @abstractmethod
    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """
        获取位置数据 (x, y, z)

        Returns:
            (x, y, z) 位置坐标（米），如果数据不可用返回 None
        """
        pass

    @abstractmethod
    def get_yaw(self) -> Optional[float]:
        """
        获取航向角

        Returns:
            Yaw角度（度），范围 [-180, 180]，如果数据不可用返回 None
        """
        pass

    @abstractmethod
    def stop(self):
        """停止数据源，释放资源"""
        pass


class VRPNDataSource(DataSource):
    """VRPN数据源（位置 + 航向角都来自VRPN）"""

    def __init__(self, vrpn_client):
        """
        Args:
            vrpn_client: VRPNClient实例
        """
        self.vrpn_client = vrpn_client

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """从VRPN获取位置"""
        pose = self.vrpn_client.pose
        if pose is None:
            return None
        return tuple(pose.position)  # (x, y, z)

    def get_yaw(self) -> Optional[float]:
        """从VRPN获取Yaw角（从四元数转换）"""
        pose = self.vrpn_client.pose
        if pose is None:
            return None
        return quaternion_to_yaw(pose.rotation)

    def stop(self):
        """停止VRPN客户端"""
        self.vrpn_client.stop()


class UWBDataSource(DataSource):
    """UWB数据源（位置来自UWB，航向角来自无人机）"""

    def __init__(self, uwb_client, mqtt_client):
        """
        Args:
            uwb_client: UWB客户端实例
            mqtt_client: MQTT客户端实例（用于获取无人机航向角）
        """
        self.uwb_client = uwb_client
        self.mqtt_client = mqtt_client

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """从UWB获取位置"""
        # 假设UWB客户端有类似VRPN的接口
        if hasattr(self.uwb_client, 'position'):
            pos = self.uwb_client.position
            if pos is None:
                return None
            return tuple(pos)
        elif hasattr(self.uwb_client, 'get_position'):
            return self.uwb_client.get_position()
        else:
            raise AttributeError("UWB客户端缺少position属性或get_position()方法")

    def get_yaw(self) -> Optional[float]:
        """从无人机MQTT数据获取Yaw角"""
        return self.mqtt_client.get_attitude_head()

    def stop(self):
        """停止UWB客户端"""
        if hasattr(self.uwb_client, 'stop'):
            self.uwb_client.stop()


class HybridDataSource(DataSource):
    """混合数据源（位置和航向角来自不同源）"""

    def __init__(self, position_client, yaw_client, position_type: str, yaw_type: str):
        """
        Args:
            position_client: 位置数据源客户端（VRPN或UWB）
            yaw_client: 航向角数据源客户端（VRPN或MQTT）
            position_type: 位置数据源类型 ('vrpn' 或 'uwb')
            yaw_type: 航向角数据源类型 ('vrpn' 或 'drone')
        """
        self.position_client = position_client
        self.yaw_client = yaw_client
        self.position_type = position_type
        self.yaw_type = yaw_type

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """获取位置数据"""
        if self.position_type == 'vrpn':
            pose = self.position_client.pose
            if pose is None:
                return None
            return tuple(pose.position)
        elif self.position_type == 'uwb':
            if hasattr(self.position_client, 'position'):
                pos = self.position_client.position
                if pos is None:
                    return None
                return tuple(pos)
            elif hasattr(self.position_client, 'get_position'):
                return self.position_client.get_position()
        return None

    def get_yaw(self) -> Optional[float]:
        """获取航向角"""
        if self.yaw_type == 'vrpn':
            pose = self.yaw_client.pose
            if pose is None:
                return None
            return quaternion_to_yaw(pose.rotation)
        elif self.yaw_type == 'drone':
            return self.yaw_client.get_attitude_head()
        return None

    def stop(self):
        """停止所有客户端"""
        # 停止位置数据源
        if self.position_type == 'vrpn' and hasattr(self.position_client, 'stop'):
            self.position_client.stop()
        elif self.position_type == 'uwb' and hasattr(self.position_client, 'stop'):
            self.position_client.stop()


def create_datasource(
    position_source: str,
    yaw_source: str,
    vrpn_client=None,
    mqtt_client=None,
    uwb_client=None
) -> DataSource:
    """
    创建数据源实例（工厂函数）

    Args:
        position_source: 位置数据源 ('vrpn' 或 'uwb')
        yaw_source: 航向角数据源 ('vrpn' 或 'drone')
        vrpn_client: VRPN客户端实例（可选）
        mqtt_client: MQTT客户端实例（可选）
        uwb_client: UWB客户端实例（可选）

    Returns:
        DataSource实例

    Raises:
        ValueError: 如果配置无效或缺少必需的客户端
    """
    # 验证配置
    valid_position_sources = ['vrpn', 'uwb']
    valid_yaw_sources = ['vrpn', 'drone']

    if position_source not in valid_position_sources:
        raise ValueError(f"无效的位置数据源: {position_source}，必须是 {valid_position_sources}")

    if yaw_source not in valid_yaw_sources:
        raise ValueError(f"无效的航向角数据源: {yaw_source}，必须是 {valid_yaw_sources}")

    # 场景1: 位置和航向角都来自VRPN
    if position_source == 'vrpn' and yaw_source == 'vrpn':
        if vrpn_client is None:
            raise ValueError("使用VRPN数据源时必须提供vrpn_client")
        return VRPNDataSource(vrpn_client)

    # 场景2: 位置来自UWB，航向角来自无人机
    elif position_source == 'uwb' and yaw_source == 'drone':
        if uwb_client is None:
            raise ValueError("使用UWB位置数据源时必须提供uwb_client")
        if mqtt_client is None:
            raise ValueError("使用无人机航向角数据源时必须提供mqtt_client")
        return UWBDataSource(uwb_client, mqtt_client)

    # 场景3: 混合数据源（位置和航向角来自不同源）
    else:
        # 确定位置数据源客户端
        if position_source == 'vrpn':
            if vrpn_client is None:
                raise ValueError("使用VRPN位置数据源时必须提供vrpn_client")
            position_client = vrpn_client
        else:  # uwb
            if uwb_client is None:
                raise ValueError("使用UWB位置数据源时必须提供uwb_client")
            position_client = uwb_client

        # 确定航向角数据源客户端
        if yaw_source == 'vrpn':
            if vrpn_client is None:
                raise ValueError("使用VRPN航向角数据源时必须提供vrpn_client")
            yaw_client = vrpn_client
        else:  # drone
            if mqtt_client is None:
                raise ValueError("使用无人机航向角数据源时必须提供mqtt_client")
            yaw_client = mqtt_client

        return HybridDataSource(position_client, yaw_client, position_source, yaw_source)
