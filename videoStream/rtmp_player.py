#!/usr/bin/env python3
"""RTMP 低延迟视频流播放器 - 支持 540p/720p/1080p 自适应"""

# ==================== 配置参数 ====================
RTMP_SERVER_IP = "192.168.31.73"
RTMP_PORT = 1935
STREAM_NAME = "drone001"
SHOW_INFO = True
# ================================================

import cv2
import os
from datetime import datetime

os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'fflags;nobuffer|rtmp_buffer;0|rtmp_live;live'

stream_url = f"rtmp://{RTMP_SERVER_IP}:{RTMP_PORT}/{STREAM_NAME}"
print(f"\033[96m播放: {stream_url}\033[0m", flush=True)

cap = cv2.VideoCapture(stream_url)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    print("\033[91m✗ 无法连接！请检查 mediamtx 和推流设备\033[0m")
    exit(1)

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"\033[92m✓ 已连接 | 分辨率: {width}x{height} | 按 q 退出\033[0m\n")

frame_count, fps = 0, 0.0
fps_update_interval = 0.1
last_fps_update = cv2.getTickCount()

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if SHOW_INFO:
            frame_count += 1
            current_time = cv2.getTickCount()
            elapsed = (current_time - last_fps_update) / cv2.getTickFrequency()

            if elapsed >= fps_update_interval:
                fps = frame_count / elapsed
                frame_count = 0
                last_fps_update = current_time

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            now = datetime.now()
            timestamp = now.strftime("%H:%M:%S") + f".{now.microsecond // 10000:02d}"
            cv2.putText(frame, timestamp, (10, height - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow('RTMP Stream', frame)
        if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:
            break

except KeyboardInterrupt:
    pass
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("\033[92m已关闭\033[0m")
