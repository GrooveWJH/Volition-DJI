#!/bin/bash

# RTMP 视频流系统启动脚本

# ANSI 颜色代码
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 获取本机 IP
get_local_ip() {
    # macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n 1
    # Linux
    else
        hostname -I | awk '{print $1}'
    fi
}

LOCAL_IP=$(get_local_ip)

echo -e "${CYAN}${BOLD}========================================${NC}"
echo -e "${CYAN}${BOLD}   RTMP 视频流系统${NC}"
echo -e "${CYAN}${BOLD}========================================${NC}"
echo ""

# 检查 mediamtx 是否存在
if [ ! -f "mediamtx/mediamtx" ]; then
    echo -e "${RED}✗ 错误: mediamtx 不存在${NC}"
    echo -e "${YELLOW}  请确保 mediamtx 已下载到 mediamtx/ 目录${NC}"
    exit 1
fi

# 检查 mediamtx 是否可执行
if [ ! -x "mediamtx/mediamtx" ]; then
    echo -e "${YELLOW}⚠ mediamtx 没有执行权限,正在添加...${NC}"
    chmod +x mediamtx/mediamtx
fi

echo -e "${GREEN}✓ mediamtx 已就绪${NC}"
echo ""

echo -e "${BLUE}${BOLD}系统信息:${NC}"
echo -e "${CYAN}本机 IP:${NC} ${BOLD}${LOCAL_IP}${NC}"
echo -e "${CYAN}RTMP 端口:${NC} ${BOLD}1935${NC}"
echo -e "${CYAN}RTSP 端口:${NC} ${BOLD}8554${NC}"
echo -e "${CYAN}HLS 端口:${NC} ${BOLD}8888${NC}"
echo -e "${CYAN}WebRTC 端口:${NC} ${BOLD}8889${NC}"
echo ""

echo -e "${YELLOW}${BOLD}视频捕获设备推流地址:${NC}"
echo -e "${GREEN}${BOLD}  rtmp://${LOCAL_IP}:1935/live${NC}"
echo ""

echo -e "${YELLOW}${BOLD}其他可用的流名称示例:${NC}"
echo -e "  rtmp://${LOCAL_IP}:1935/drone"
echo -e "  rtmp://${LOCAL_IP}:1935/camera1"
echo ""

echo -e "${BLUE}${BOLD}启动播放器 (在另一个终端):${NC}"
echo -e "  ${GREEN}python rtmp_player.py${NC}"
echo -e "  ${GREEN}python rtmp_player.py --stream drone${NC}"
echo ""

echo -e "${CYAN}${BOLD}========================================${NC}"
echo -e "${YELLOW}正在启动 mediamtx 服务器...${NC}"
echo -e "${CYAN}${BOLD}========================================${NC}"
echo ""

# 启动 mediamtx（指定配置文件）
./mediamtx/mediamtx ./mediamtx/mediamtx.yml
