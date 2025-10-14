// 主入口文件 - 轻量化协议管理器
import { videoStreamManager } from '@/cards/StreamingCard/stream-manager.js';

console.log('🚀 初始化协议测试系统...');

// 从localStorage加载配置
function loadStoredConfig() {
  const storedHosts = JSON.parse(localStorage.getItem('streaming-hosts') || '{}');
  
  // 更新页面上的host输入框
  Object.entries(storedHosts).forEach(([playerId, host]) => {
    const hostInput = document.querySelector(`[data-input="host"][data-player-id="${playerId}"]`);
    if (hostInput) {
      hostInput.value = host;
      
      // 同时更新RTMP URL
      const rtmpInput = document.querySelector(`[data-input="rtmp-url"][data-player-id="${playerId}"]`);
      if (rtmpInput) {
        const currentRtmp = rtmpInput.value;
        if (currentRtmp.includes('://')) {
          const parts = currentRtmp.split('://');
          const protocol = parts[0];
          const pathPart = parts[1].split('/').slice(1).join('/');
          rtmpInput.value = `${protocol}://${host}/${pathPart}`;
        }
      }
    }
  });
}

// 页面加载完成后加载配置
document.addEventListener('DOMContentLoaded', () => {
  loadStoredConfig();
});

// 全局函数，供Astro组件内联调用
window.updateHostConfig = (playerId, newHost) => {
  // 保存到localStorage
  const storedHosts = JSON.parse(localStorage.getItem('streaming-hosts') || '{}');
  storedHosts[playerId] = newHost;
  localStorage.setItem('streaming-hosts', JSON.stringify(storedHosts));
  
  // 同时更新RTMP URL中的host部分
  const rtmpInput = document.querySelector(`[data-input="rtmp-url"][data-player-id="${playerId}"]`);
  if (rtmpInput) {
    const currentRtmp = rtmpInput.value;
    if (currentRtmp.includes('://')) {
      const parts = currentRtmp.split('://');
      const protocol = parts[0];
      const pathPart = parts[1].split('/').slice(1).join('/');
      rtmpInput.value = `${protocol}://${newHost}/${pathPart}`;
    }
  }
  
  console.log(`更新host配置: ${playerId} -> ${newHost}`);
};

window.testVideoStreamConnection = (playerId) => {
  const player = videoStreamManager.initialize(playerId);
  if (player) {
    videoStreamManager.testConnection(playerId);
  }
};

window.toggleVideoStream = (playerId) => {
  const player = videoStreamManager.initialize(playerId);
  if (player) {
    videoStreamManager.toggleStream(playerId);
  }
};

window.clearVideoStreamLog = (playerId) => {
  const logger = videoStreamManager.getLogger(playerId);
  if (logger) {
    logger.clear();
  }
};

window.runVideoStreamDiagnostics = (playerId) => {
  const player = videoStreamManager.initialize(playerId);
  if (player) {
    videoStreamManager.testConnection(playerId);
  }
};

window.runSystemDiagnostics = (host) => {
  console.log(`系统诊断: ${host}`);
};

window.runAutoSystemDiagnostics = (host) => {
  console.log(`自动系统诊断: ${host}`);
};

window.clearDiagnosticLog = (host) => {
  console.log(`清除诊断日志: ${host}`);
};

// 页面卸载时清理视频流资源
window.addEventListener('beforeunload', () => {
  videoStreamManager.cleanup();
});

console.log('✅ 协议系统初始化完成');