#!/usr/bin/env python3
"""检查 OpenCV 的视频后端支持"""

import cv2

print("=" * 60)
print("OpenCV 视频后端支持检查")
print("=" * 60)
print(f"\nOpenCV 版本: {cv2.__version__}")
print(f"构建信息:")
print("-" * 60)
print(cv2.getBuildInformation())
