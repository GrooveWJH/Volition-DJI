// WebRTC视频播放器 - 基于WHEP协议的低延迟视频流播放
import { CONFIG } from '../../shared/config/app-config.js';

export class SimpleVideoPlayer {
  constructor(container, logger, playerId) {
    this.container = container;
    this.logger = logger;
    this.playerId = playerId;
    this.pc = null;
    this.videoElement = null;
    this.isPlaying = false;
    
    // 验证容器元素有效性
    if (!this.container || !this.container.appendChild) {
      throw new Error(`无效的视频容器元素: ${playerId}`);
    }
  }
  
  async startStream(rtmpUrl) {
    if (this.isPlaying) {
      this.logger.log('已经在播放中', 'warning');
      return false;
    }
    
    const host = this.extractHost(rtmpUrl);
    const streamPath = this.extractStreamPath(rtmpUrl);
    const whepUrl = CONFIG.webrtc.buildUrl(host, streamPath);
    
    this.logger.log(`开始播放: ${rtmpUrl}`, 'info');
    this.logger.log(`WHEP端点: ${whepUrl}`, 'info');
    
    try {
      this.createVideoElement();
      await this.createWebRTCConnection(whepUrl);
      
      this.logger.log('播放启动完成', 'success');
      return true;
      
    } catch (error) {
      this.logger.log(`播放失败: ${error.message}`, 'error');
      return false;
    }
  }
  
  createVideoElement() {
    // 清空容器
    this.container.innerHTML = '';
    
    // 创建video元素
    this.videoElement = document.createElement('video');
    this.videoElement.controls = true;
    this.videoElement.autoplay = true;
    this.videoElement.muted = true;
    this.videoElement.playsInline = true;
    
    // 设置样式
    this.videoElement.style.width = '100%';
    this.videoElement.style.height = '100%';
    this.videoElement.style.objectFit = 'cover';
    
    // 事件监听
    this.videoElement.addEventListener('loadedmetadata', () => {
      this.logger.log(`视频尺寸: ${this.videoElement.videoWidth}x${this.videoElement.videoHeight}`, 'info');
    });
    
    this.videoElement.addEventListener('playing', () => {
      this.logger.log('视频开始播放', 'success');
      this.isPlaying = true;
    });
    
    this.videoElement.addEventListener('pause', () => {
      this.logger.log('视频已暂停', 'info');
    });
    
    this.videoElement.addEventListener('error', (e) => {
      this.logger.log(`视频错误: ${e.message || '未知错误'}`, 'error');
      this.logger.log(`错误代码: ${this.videoElement.error?.code || 'N/A'}`, 'error');
    });
    
    // 添加到容器
    this.container.appendChild(this.videoElement);
    this.logger.log('Video元素创建并添加完成', 'success');
  }
  
  async createWebRTCConnection(whepUrl) {
    this.pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' }
      ]
    });
    
    // ontrack事件
    this.pc.ontrack = (event) => {
      this.logger.log('接收到WebRTC流', 'success');
      this.logger.log(`流数量: ${event.streams.length}`, 'info');
      
      const stream = event.streams[0];
      this.logger.log(`轨道数量: ${stream.getTracks().length}`, 'info');
      
      stream.getTracks().forEach((track, index) => {
        this.logger.log(`轨道 ${index}: ${track.kind} - ${track.readyState}`, 'info');
      });
      
      // 设置stream
      this.videoElement.srcObject = stream;
      
      this.videoElement.play().then(() => {
        this.logger.log('视频播放成功', 'success');
        this.isPlaying = true;
      }).catch(error => {
        this.logger.log(`视频播放失败: ${error.message}`, 'error');
      });
    };
    
    // ICE连接状态
    this.pc.oniceconnectionstatechange = () => {
      this.logger.log(`ICE连接状态: ${this.pc.iceConnectionState}`, 'info');
      
      if (this.pc.iceConnectionState === 'failed') {
        this.logger.log('WebRTC连接失败', 'error');
      }
    };
    
    // ICE收集状态
    this.pc.onicegatheringstatechange = () => {
      if (this.pc.iceGatheringState === 'failed') {
        this.logger.log('ICE收集失败', 'error');
      }
    };
    
    // 创建offer
    const offer = await this.pc.createOffer({
      offerToReceiveVideo: true,
      offerToReceiveAudio: true
    });
    
    await this.pc.setLocalDescription(offer);
    this.logger.log('本地SDP已设置', 'info');
    
    // 发送WHEP请求
    const response = await fetch(whepUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/sdp' },
      body: offer.sdp
    });
    
    if (!response.ok) {
      throw new Error(`WHEP请求失败: ${response.status} ${response.statusText}`);
    }
    
    const answerSdp = await response.text();
    await this.pc.setRemoteDescription({
      type: 'answer',
      sdp: answerSdp
    });
    
    this.logger.log('远程SDP已设置', 'success');
    this.logger.log('WebRTC握手完成', 'success');
  }
  
  stopStream() {
    this.isPlaying = false;
    
    if (this.pc) {
      this.pc.close();
      this.pc = null;
      this.logger.log('WebRTC连接已关闭', 'info');
    }
    
    if (this.videoElement) {
      this.videoElement.pause();
      this.videoElement.srcObject = null;
      this.videoElement = null;
      this.logger.log('视频播放已停止', 'info');
    }
    
    // 恢复占位符
    this.container.innerHTML = `
      <div class="video-placeholder text-center text-gray-400">
        <div class="space-y-4">
          <span class="material-symbols-outlined text-6xl">play_circle</span>
          <div class="space-y-2">
            <p class="text-lg font-medium">推流预览</p>
            <p class="text-sm opacity-75">配置RTMP地址后点击开始推流</p>
          </div>
        </div>
      </div>
    `;
    
    this.logger.log('停止完成', 'success');
  }
  
  // 辅助方法
  extractHost(rtmpUrl) {
    try {
      const url = new URL(rtmpUrl.replace('rtmp://', 'http://'));
      return url.hostname;
    } catch {
      return CONFIG.rtmp.defaultHost;
    }
  }
  
  extractStreamPath(rtmpUrl) {
    try {
      const url = new URL(rtmpUrl.replace('rtmp://', 'http://'));
      return url.pathname.substring(1); // 移除开头的 '/'
    } catch {
      return `${CONFIG.rtmp.defaultApp}/${CONFIG.rtmp.defaultStream}`;
    }
  }
}
