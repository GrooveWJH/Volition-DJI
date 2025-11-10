#!/usr/bin/env python3
"""
数据源抽象层测试脚本

测试所有数据源配置是否正常工作。
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from control.datasource import create_datasource, VRPNDataSource, UWBDataSource, HybridDataSource
from uwb import MockUWBClient


class MockVRPNClient:
    """Mock VRPN客户端用于测试"""

    class Pose:
        def __init__(self):
            self.position = [1.0, 2.0, 0.5]
            self.rotation = [0.0, 0.0, 0.0, 1.0]  # 单位四元数

    def __init__(self):
        self.pose = self.Pose()

    def stop(self):
        pass


class MockMQTTClient:
    """Mock MQTT客户端用于测试"""

    def get_attitude_head(self):
        return 45.0  # 返回45度


def test_vrpn_datasource():
    """测试纯VRPN数据源"""
    print("\n[测试 1] VRPN数据源（位置 + 航向角）")
    print("=" * 50)

    vrpn_client = MockVRPNClient()
    datasource = create_datasource(
        position_source='vrpn',
        yaw_source='vrpn',
        vrpn_client=vrpn_client
    )

    position = datasource.get_position()
    yaw = datasource.get_yaw()

    print(f"✓ 位置: {position}")
    print(f"✓ 航向角: {yaw:.2f}°")

    assert position == (1.0, 2.0, 0.5), "位置数据不正确"
    assert yaw == 0.0, "航向角数据不正确"

    datasource.stop()
    print("✓ 测试通过")


def test_uwb_datasource():
    """测试UWB+无人机数据源"""
    print("\n[测试 2] UWB数据源（位置 from UWB + 航向角 from 无人机）")
    print("=" * 50)

    uwb_client = MockUWBClient('drone1', x=3.0, y=4.0, z=1.0)
    mqtt_client = MockMQTTClient()

    datasource = create_datasource(
        position_source='uwb',
        yaw_source='drone',
        uwb_client=uwb_client,
        mqtt_client=mqtt_client
    )

    position = datasource.get_position()
    yaw = datasource.get_yaw()

    print(f"✓ 位置: {position}")
    print(f"✓ 航向角: {yaw:.2f}°")

    assert position == (3.0, 4.0, 1.0), "UWB位置数据不正确"
    assert yaw == 45.0, "无人机航向角数据不正确"

    datasource.stop()
    print("✓ 测试通过")


def test_hybrid_datasource_vrpn_drone():
    """测试混合数据源：VRPN位置 + 无人机航向角"""
    print("\n[测试 3] 混合数据源（位置 from VRPN + 航向角 from 无人机）")
    print("=" * 50)

    vrpn_client = MockVRPNClient()
    mqtt_client = MockMQTTClient()

    datasource = create_datasource(
        position_source='vrpn',
        yaw_source='drone',
        vrpn_client=vrpn_client,
        mqtt_client=mqtt_client
    )

    position = datasource.get_position()
    yaw = datasource.get_yaw()

    print(f"✓ 位置: {position}")
    print(f"✓ 航向角: {yaw:.2f}°")

    assert position == (1.0, 2.0, 0.5), "VRPN位置数据不正确"
    assert yaw == 45.0, "无人机航向角数据不正确"

    datasource.stop()
    print("✓ 测试通过")


def test_hybrid_datasource_uwb_vrpn():
    """测试混合数据源：UWB位置 + VRPN航向角"""
    print("\n[测试 4] 混合数据源（位置 from UWB + 航向角 from VRPN）")
    print("=" * 50)

    uwb_client = MockUWBClient('drone1', x=5.0, y=6.0, z=1.5)
    vrpn_client = MockVRPNClient()

    datasource = create_datasource(
        position_source='uwb',
        yaw_source='vrpn',
        uwb_client=uwb_client,
        vrpn_client=vrpn_client
    )

    position = datasource.get_position()
    yaw = datasource.get_yaw()

    print(f"✓ 位置: {position}")
    print(f"✓ 航向角: {yaw:.2f}°")

    assert position == (5.0, 6.0, 1.5), "UWB位置数据不正确"
    assert yaw == 0.0, "VRPN航向角数据不正确"

    datasource.stop()
    print("✓ 测试通过")


def test_error_handling():
    """测试错误处理"""
    print("\n[测试 5] 错误处理")
    print("=" * 50)

    # 测试缺少必需客户端
    try:
        datasource = create_datasource(
            position_source='vrpn',
            yaw_source='vrpn',
            vrpn_client=None  # 缺少VRPN客户端
        )
        print("✗ 应该抛出异常")
        assert False
    except ValueError as e:
        print(f"✓ 正确捕获异常: {e}")

    # 测试无效的数据源类型
    try:
        datasource = create_datasource(
            position_source='invalid',
            yaw_source='vrpn',
            vrpn_client=MockVRPNClient()
        )
        print("✗ 应该抛出异常")
        assert False
    except ValueError as e:
        print(f"✓ 正确捕获异常: {e}")

    print("✓ 测试通过")


def main():
    print("\n" + "=" * 60)
    print(" 数据源抽象层测试")
    print("=" * 60)

    try:
        test_vrpn_datasource()
        test_uwb_datasource()
        test_hybrid_datasource_vrpn_drone()
        test_hybrid_datasource_uwb_vrpn()
        test_error_handling()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
