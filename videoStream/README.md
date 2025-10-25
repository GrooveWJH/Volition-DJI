# RTMP 视频流系统使用指南

本目录包含 mediamtx 视频流服务器和 Python 播放器,用于接收和播放设备发送的 RTMP 视频流。

## 📋 系统组件

- **mediamtx**: 视频流媒体服务器,支持 RTMP/RTSP/HLS/WebRTC 等多种协议
- **rtmp_player.py**: Python 视频流播放器,用于显示接收到的视频流

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install opencv-python
```

### 2. 启动 mediamtx 服务器

```bash
# 在 videoStream 目录下
cd /Users/groovewjh/Project/work/SYSU/Volition-DJI/videoStream

# 启动 mediamtx 服务器
./mediamtx/mediamtx
```

服务器将监听以下端口:
- **RTMP**: 1935 (接收和播放)
- **RTSP**: 8554
- **HLS**: 8888
- **WebRTC**: 8889

### 3. 配置视频捕获设备

在你的视频捕获设备上,将 RTMP 推流地址设置为:

```
rtmp://192.168.5.151:1935/live
```

其中:
- `192.168.5.151` 是你的本机 IP
- `1935` 是 RTMP 默认端口
- `live` 是流名称(可以自定义)

**其他流名称示例:**
- `rtmp://192.168.5.151:1935/drone`
- `rtmp://192.168.5.151:1935/camera1`
- `rtmp://192.168.5.151:1935/mystream`

### 4. 播放视频流

```bash
# 使用默认地址 (rtmp://localhost:1935/live)
python rtmp_player.py

# 指定流名称
python rtmp_player.py --stream drone

# 指定完整地址
python rtmp_player.py --url rtmp://192.168.5.151:1935/live

# 指定 IP 和流名称
python rtmp_player.py --ip 192.168.5.151 --stream camera1

# 不显示 FPS 信息
python rtmp_player.py --no-fps
```

## 📱 完整工作流程

### 方案 1: 本地测试

1. **终端 1** - 启动 mediamtx:
   ```bash
   cd videoStream
   ./mediamtx/mediamtx
   ```

2. **设备** - 推送 RTMP 流到:
   ```
   rtmp://192.168.5.151:1935/live
   ```

3. **终端 2** - 启动播放器:
   ```bash
   cd videoStream
   python rtmp_player.py
   ```

### 方案 2: 使用自定义流名称

1. **终端 1** - 启动 mediamtx:
   ```bash
   cd videoStream
   ./mediamtx/mediamtx
   ```

2. **设备** - 推送到自定义流名称:
   ```
   rtmp://192.168.5.151:1935/drone
   ```

3. **终端 2** - 播放自定义流:
   ```bash
   cd videoStream
   python rtmp_player.py --stream drone
   ```

## 🔍 常见问题

### Q: 播放器无法连接到视频流

**检查清单:**
1. mediamtx 服务是否正在运行?
2. 设备是否正在推送视频流?
3. 设备推送的流名称与播放器使用的是否一致?
4. 网络连接是否正常?
5. 防火墙是否阻止了端口 1935?

### Q: 如何查看所有可用的流?

mediamtx 会在终端显示所有连接的流信息。你也可以使用:

```bash
# 使用 ffprobe 查看流信息
ffprobe rtmp://localhost:1935/live
```

### Q: 如何测试 RTMP 推流?

使用 FFmpeg 测试推流:

```bash
# 推送测试视频
ffmpeg -re -i test.mp4 -c copy -f flv rtmp://192.168.5.151:1935/live

# 推送摄像头视频 (macOS)
ffmpeg -f avfoundation -i "0" -c:v libx264 -preset ultrafast -f flv rtmp://192.168.5.151:1935/live

# 推送摄像头视频 (Linux)
ffmpeg -f v4l2 -i /dev/video0 -c:v libx264 -preset ultrafast -f flv rtmp://192.168.5.151:1935/live
```

### Q: 如何使用其他协议播放?

mediamtx 自动将 RTMP 流转换为其他协议:

```bash
# RTSP
ffplay rtsp://192.168.5.151:8554/live

# HLS (在浏览器中打开)
http://192.168.5.151:8888/live

# WebRTC (在浏览器中打开)
http://192.168.5.151:8889/live
```

## ⚙️ mediamtx 配置

配置文件位于: `mediamtx/mediamtx.yml`

常用配置:
- RTMP 端口: `rtmpAddress: :1935`
- RTSP 端口: `rtspAddress: :8554`
- HLS 端口: `hlsAddress: :8888`
- 日志级别: `logLevel: info` (可改为 `debug` 查看详细日志)

## 🛠️ 故障排查

### 查看 mediamtx 日志

mediamtx 会在终端显示详细的连接日志,包括:
- 客户端连接/断开
- 流发布/停止
- 错误信息

### 测试网络连接

```bash
# 检查端口是否开放
nc -zv 192.168.5.151 1935

# 或使用 telnet
telnet 192.168.5.151 1935
```

### 查看系统进程

```bash
# 查看 mediamtx 是否运行
ps aux | grep mediamtx

# 查看端口占用
lsof -i :1935
```

## 📚 参考资料

- [mediamtx GitHub](https://github.com/bluenviron/mediamtx)
- [RTMP 协议规范](https://www.adobe.com/devnet/rtmp.html)
- [OpenCV 文档](https://docs.opencv.org/)
