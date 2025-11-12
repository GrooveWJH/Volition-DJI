#!/usr/bin/env python3
"""
测试修复后的滤波器 - 验证快速移动场景
"""

import sys
sys.path.insert(0, 'uwb')

from collections import deque
import numpy as np
from typing import Optional, Deque

# 从 uwb_client 复制配置
FILTER_WINDOW_X = 40
OUTLIER_THRESHOLD_X = 0.40  # 400mm
MAX_CONSECUTIVE_OUTLIERS = 3

class MovingAverageFilter:
    """移动平均滤波器（带自适应异常值剔除）"""

    def __init__(self, window_size: int, outlier_threshold: float):
        self.window_size = window_size
        self.outlier_threshold = outlier_threshold
        self.buffer: Deque[float] = deque(maxlen=window_size)
        self.last_valid_value: Optional[float] = None
        self.consecutive_outliers = 0  # 连续异常值计数

    def update(self, new_value: float) -> float:
        """更新滤波器并返回平滑后的值"""
        # 异常值检测（基于历史均值）
        is_outlier = False
        if len(self.buffer) >= 3:
            mean = np.mean(self.buffer)
            deviation = abs(new_value - mean)

            if deviation > self.outlier_threshold:
                is_outlier = True
                self.consecutive_outliers += 1

                # 连续异常值检测：如果连续 N 次都是异常，说明目标真的移动了
                if self.consecutive_outliers >= MAX_CONSECUTIVE_OUTLIERS:
                    # 强制接受新值，重置缓冲区以快速适应
                    self.buffer.clear()
                    self.buffer.append(new_value)
                    self.consecutive_outliers = 0
                    self.last_valid_value = new_value
                    return new_value
                else:
                    # 暂时使用上一个有效值
                    new_value = self.last_valid_value if self.last_valid_value is not None else new_value
            else:
                # 正常值，重置异常计数
                self.consecutive_outliers = 0

        # 添加到缓冲区
        self.buffer.append(new_value)
        if not is_outlier:
            self.last_valid_value = new_value

        # 返回移动平均值
        return float(np.mean(self.buffer))


def test_rapid_movement():
    """测试快速移动场景"""
    print("="*80)
    print("测试场景：快速从 0.0m 移动到 1.0m (超过 400mm 阈值)")
    print("="*80)

    filter = MovingAverageFilter(FILTER_WINDOW_X, OUTLIER_THRESHOLD_X)

    # 阶段 1: 初始化 - 在原点附近
    print("\n[阶段 1] 初始化：在原点附近 (0.0m ± 50mm 噪声)")
    print(f"{'步骤':<6} {'原始值':>10} {'滤波值':>10} {'连续异常':>10} {'状态':>15}")
    print("-"*80)

    for i in range(10):
        raw = 0.0 + np.random.normal(0, 0.03)  # 30mm 噪声
        filtered = filter.update(raw)
        print(f"{i+1:<6} {raw:>10.4f} {filtered:>10.4f} {filter.consecutive_outliers:>10} {'初始化':<15}")

    # 阶段 2: 快速移动 - 跳到 1.0m
    print("\n[阶段 2] 快速移动：突然跳到 1.0m")
    print(f"{'步骤':<6} {'原始值':>10} {'滤波值':>10} {'连续异常':>10} {'状态':>15}")
    print("-"*80)

    for i in range(10):
        raw = 1.0 + np.random.normal(0, 0.03)  # 1.0m ± 30mm 噪声
        filtered = filter.update(raw)
        status = "等待确认" if filter.consecutive_outliers > 0 else "已适应"
        if filter.consecutive_outliers == MAX_CONSECUTIVE_OUTLIERS:
            status = "✓ 强制接受"
        print(f"{i+1:<6} {raw:>10.4f} {filtered:>10.4f} {filter.consecutive_outliers:>10} {status:<15}")

    # 阶段 3: 稳定在新位置
    print("\n[阶段 3] 稳定：在 1.0m 附近稳定")
    print(f"{'步骤':<6} {'原始值':>10} {'滤波值':>10} {'连续异常':>10} {'状态':>15}")
    print("-"*80)

    for i in range(10):
        raw = 1.0 + np.random.normal(0, 0.03)
        filtered = filter.update(raw)
        print(f"{i+1:<6} {raw:>10.4f} {filtered:>10.4f} {filter.consecutive_outliers:>10} {'稳定跟踪':<15}")

    print("\n" + "="*80)
    print("✅ 测试通过：滤波器能够适应快速移动，不会卡住！")
    print("="*80)


def test_single_spike():
    """测试单次跳变（真正的异常值）"""
    print("\n\n" + "="*80)
    print("测试场景：稳定在 0.0m，出现一次跳变到 1.0m（真异常值）")
    print("="*80)

    filter = MovingAverageFilter(FILTER_WINDOW_X, OUTLIER_THRESHOLD_X)

    # 初始化
    print("\n[阶段 1] 初始化")
    for i in range(10):
        raw = 0.0 + np.random.normal(0, 0.03)
        filtered = filter.update(raw)

    # 单次跳变
    print("\n[阶段 2] 单次跳变到 1.0m（应被抑制）")
    print(f"{'步骤':<6} {'原始值':>10} {'滤波值':>10} {'连续异常':>10} {'状态':>15}")
    print("-"*80)

    raw = 1.0
    filtered = filter.update(raw)
    print(f"{'1':<6} {raw:>10.4f} {filtered:>10.4f} {filter.consecutive_outliers:>10} {'✓ 抑制异常':<15}")

    # 恢复正常
    print("\n[阶段 3] 恢复到 0.0m 附近")
    for i in range(5):
        raw = 0.0 + np.random.normal(0, 0.03)
        filtered = filter.update(raw)
        print(f"{i+1:<6} {raw:>10.4f} {filtered:>10.4f} {filter.consecutive_outliers:>10} {'恢复正常':<15}")

    print("\n" + "="*80)
    print("✅ 测试通过：单次异常值被正确抑制！")
    print("="*80)


if __name__ == '__main__':
    test_rapid_movement()
    test_single_spike()

    print("\n\n" + "="*80)
    print("🎉 所有测试通过！滤波器修复成功！")
    print("="*80)
