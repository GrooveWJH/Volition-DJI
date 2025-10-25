#!/bin/bash
# RTMP 视频流播放器 - 使用 ffplay

# ==================== 配置参数 ====================
RTMP_SERVER_IP="192.168.8.151"  # mediamtx 服务器 IP
RTMP_PORT=1935                  # RTMP 端口
STREAM_NAME="drone003"          # 流名称
# ================================================

# ANSI 颜色
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
CYAN='\033[96m'
END='\033[0m'

STREAM_URL="rtmp://${RTMP_SERVER_IP}:${RTMP_PORT}/${STREAM_NAME}"

echo -e "${CYAN}RTMP 视频流播放器 (ffplay)${END}"
echo -e "${CYAN}流地址: ${STREAM_URL}${END}"
echo -e "${YELLOW}正在启动...${END}\n"

# 使用 ffplay 播放（带 FPS 显示）
ffplay -i "${STREAM_URL}" \
  -window_title "RTMP Stream - ${STREAM_NAME}" \
  -vf "drawtext=fontsize=30:fontcolor=white:text='FPS\: %{pts}':x=10:y=10" \
  -stats
