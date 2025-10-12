/**
 * WebRTC调试连接管理器
 * 处理视频流播放和连接逻辑
 */

import { debugLogger } from './debug-logger.js';

export class DebugWebRTCPlayer {
  constructor(config) {
    this.config = config;
    this.pc = null;
    this.videoElement = null;
    this.isPlaying = false;
  }

  async testConnection() {
    const host = document.getElementById('host').value || this.config.host;
    debugLogger.log(`测试MediaMTX连接: ${host}`);

    const testUrls = [
      `http://${host}:${this.config.webrtcPort}/`,
      ...this.config.apiEndpoints.map((endpoint) => `http://${host}${endpoint}`)
    ];

    for (const url of testUrls) {
      try {
        await fetch(url, {
          method: 'GET',
          mode: 'no-cors',
          signal: AbortSignal.timeout(this.config.timeoutMs)
        });
        debugLogger.log(`✅ ${url} 可访问`, 'success');
        return;
      } catch (error) {
        debugLogger.log(`❌ ${url} 不可访问: ${error.message}`, 'warning');
      }
    }

    debugLogger.log('所有测试端点均不可访问', 'error');
  }

  async startPlay() {
    if (this.isPlaying) {
      debugLogger.log('已经在播放中', 'warning');
      return;
    }

    const host = document.getElementById('host').value || this.config.host;
    const streamPath = document.getElementById('streamPath').value || this.config.streamPath;
    const rtmpUrl = `rtmp://${host}:${this.config.rtmpPort}/${streamPath}`;
    const whepUrl = `http://${host}:${this.config.webrtcPort}/${streamPath}/whep`;

    debugLogger.log(`🚀 开始播放: ${rtmpUrl}`);
    debugLogger.log(`WHEP端点: ${whepUrl}`);
    debugLogger.updateStatus('connecting', '连接中...');

    try {
      this.createVideoElement();
      await this.createWebRTCConnection(whepUrl);
      debugLogger.log('✅ 播放启动完成', 'success');
    } catch (error) {
      debugLogger.log(`❌ 播放失败: ${error.message}`, 'error');
      debugLogger.updateStatus('failed', '连接失败');
    }
  }

  createVideoElement() {
    const container = document.getElementById('video-container');
    container.innerHTML = '';

    this.videoElement = document.createElement('video');
    this.videoElement.controls = true;
    this.videoElement.autoplay = true;
    this.videoElement.muted = true;
    this.videoElement.playsInline = true;

    this.videoElement.addEventListener('loadedmetadata', () => {
      debugLogger.log(`📐 视频尺寸: ${this.videoElement.videoWidth}x${this.videoElement.videoHeight}`, 'info');
    });

    this.videoElement.addEventListener('playing', () => {
      debugLogger.log('▶️ 视频开始播放', 'success');
      this.isPlaying = true;
      debugLogger.updateStatus('connected', '播放中');
    });

    this.videoElement.addEventListener('pause', () => {
      debugLogger.log('⏸️ 视频已暂停', 'info');
    });

    this.videoElement.addEventListener('error', (e) => {
      debugLogger.log(`❌ 视频错误: ${e.message || '未知错误'}`, 'error');
      debugLogger.log(`错误代码: ${this.videoElement.error?.code || 'N/A'}`, 'error');
    });

    container.appendChild(this.videoElement);
    debugLogger.log('✅ Video元素创建完成', 'success');
  }

  async createWebRTCConnection(whepUrl) {
    this.pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });

    this.pc.ontrack = (event) => {
      debugLogger.log('🎬 接收到WebRTC流', 'success');
      debugLogger.log(`流数量: ${event.streams.length}`, 'info');

      const stream = event.streams[0];
      debugLogger.log(`轨道数量: ${stream.getTracks().length}`, 'info');

      stream.getTracks().forEach((track, index) => {
        debugLogger.log(`轨道 ${index}: ${track.kind} - ${track.readyState}`, 'info');
      });

      this.videoElement.srcObject = stream;

      this.videoElement.play()
        .then(() => debugLogger.log('✅ 视频播放成功', 'success'))
        .catch((error) => debugLogger.log(`❌ 视频播放失败: ${error.message}`, 'error'));
    };

    this.pc.oniceconnectionstatechange = () => {
      debugLogger.log(`🔗 ICE连接状态: ${this.pc.iceConnectionState}`, 'info');

      switch (this.pc.iceConnectionState) {
        case 'connected':
          debugLogger.updateStatus('connected', '已连接');
          break;
        case 'failed':
          debugLogger.updateStatus('failed', '连接失败');
          debugLogger.log('❌ WebRTC连接失败', 'error');
          break;
        case 'disconnected':
          debugLogger.updateStatus('idle', '已断开');
          break;
      }
    };

    this.pc.onicegatheringstatechange = () => {
      debugLogger.log(`🧊 ICE收集状态: ${this.pc.iceGatheringState}`, 'info');
    };

    const offer = await this.pc.createOffer({
      offerToReceiveVideo: true,
      offerToReceiveAudio: true
    });

    await this.pc.setLocalDescription(offer);
    debugLogger.log('📤 本地SDP已设置', 'info');

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

    debugLogger.log('📥 远程SDP已设置', 'success');
    debugLogger.log('🤝 WebRTC握手完成', 'success');
  }

  stopPlay() {
    if (this.pc) {
      this.pc.close();
      this.pc = null;
      debugLogger.log('🔌 WebRTC连接已关闭', 'info');
    }

    if (this.videoElement) {
      this.videoElement.pause();
      this.videoElement.srcObject = null;
      this.videoElement = null;
      debugLogger.log('⏹️ 视频播放已停止', 'info');
    }

    const container = document.getElementById('video-container');
    container.innerHTML = '🎥 点击开始播放以显示视频流';

    this.isPlaying = false;
    debugLogger.updateStatus('idle', '待连接');
    debugLogger.log('✅ 停止完成', 'success');
  }

  debugVideo() {
    debugLogger.log('=== 🔍 调试信息 ===', 'info');

    if (this.videoElement) {
      debugLogger.log(`Video元素存在: ${this.videoElement ? '是' : '否'}`, 'info');
      debugLogger.log(`srcObject设置: ${this.videoElement.srcObject ? '是' : '否'}`, 'info');
      debugLogger.log(`readyState: ${this.videoElement.readyState}`, 'info');
      debugLogger.log(`paused: ${this.videoElement.paused}`, 'info');
      debugLogger.log(`currentTime: ${this.videoElement.currentTime}`, 'info');
      debugLogger.log(`duration: ${this.videoElement.duration}`, 'info');
      debugLogger.log(`videoWidth: ${this.videoElement.videoWidth}`, 'info');
      debugLogger.log(`videoHeight: ${this.videoElement.videoHeight}`, 'info');
      debugLogger.log(`volume: ${this.videoElement.volume}`, 'info');
      debugLogger.log(`muted: ${this.videoElement.muted}`, 'info');

      if (this.videoElement.srcObject) {
        const stream = this.videoElement.srcObject;
        debugLogger.log(`Stream active: ${stream.active}`, 'info');
        debugLogger.log(`Stream id: ${stream.id}`, 'info');

        stream.getTracks().forEach((track, index) => {
          debugLogger.log(
            `Track ${index}: ${track.kind}, enabled: ${track.enabled}, muted: ${track.muted}, readyState: ${track.readyState}`,
            'info'
          );
        });
      }
    } else {
      debugLogger.log('Video元素不存在', 'warning');
    }

    if (this.pc) {
      debugLogger.log(`WebRTC连接状态: ${this.pc.connectionState}`, 'info');
      debugLogger.log(`ICE连接状态: ${this.pc.iceConnectionState}`, 'info');
      debugLogger.log(`ICE收集状态: ${this.pc.iceGatheringState}`, 'info');
      debugLogger.log(`信令状态: ${this.pc.signalingState}`, 'info');
    } else {
      debugLogger.log('RTCPeerConnection不存在', 'warning');
    }
  }
}