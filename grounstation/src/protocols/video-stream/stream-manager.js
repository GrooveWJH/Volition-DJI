// 视频流协议管理器 - 基于WebRTC的低延迟视频流播放管理
import { SimpleVideoPlayer } from './webrtc-player.js';
import { TerminalLogger } from '../../shared/core/terminal.js';

export class VideoStreamManager {
  constructor() {
    this.players = new Map();
    this.loggers = new Map();
  }

  // 初始化视频流协议 - 增强容器选择器鲁棒性
  initialize(playerId) {
    if (this.players.has(playerId)) {
      return this.players.get(playerId);
    }

    // 多重容器选择策略，避免选错DOM元素
    const selectors = [
      `div[data-player-id="${playerId}"][style*="aspect-ratio"]`, // 优先：视频容器div
      `div[data-player-id="${playerId}"].bg-black`,              // 备选：黑色背景视频容器
      `[data-player-id="${playerId}"]`,                          // 最后：任意匹配元素
    ];

    let container = null;
    for (const selector of selectors) {
      const elements = document.querySelectorAll(selector);
      
      // 验证找到的元素是否为有效的容器元素
      for (const element of elements) {
        if (this.isValidVideoContainer(element)) {
          container = element;
          console.log(`✅ 找到有效视频容器 (${selector}):`, element);
          break;
        } else {
          console.warn(`⚠️  跳过无效容器元素 (${selector}):`, element);
        }
      }
      
      if (container) break;
    }

    if (!container) {
      console.error('❌ 找不到有效的视频容器:', playerId);
      console.log('📝 页面上所有data-player-id元素:', document.querySelectorAll(`[data-player-id="${playerId}"]`));
      return null;
    }

    const logger = new TerminalLogger(playerId);
    this.loggers.set(playerId, logger);

    const player = new SimpleVideoPlayer(container, logger, playerId);
    this.players.set(playerId, player);

    logger.log(`视频播放器 ${playerId} 已初始化`, 'info');
    
    return player;
  }

  // 验证是否为有效的视频容器元素
  isValidVideoContainer(element) {
    // 检查是否为可以包含子元素的HTML元素
    if (!element || !element.appendChild || !element.tagName) {
      return false;
    }
    
    // 排除输入元素
    const invalidTags = ['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA'];
    if (invalidTags.includes(element.tagName.toUpperCase())) {
      return false;
    }
    
    // 检查是否有视频容器的特征属性
    const hasVideoContainerFeatures = 
      element.style.aspectRatio ||                           // 有宽高比样式
      element.className.includes('bg-black') ||             // 黑色背景
      element.className.includes('video') ||                // 类名包含video
      element.querySelector('.video-placeholder');          // 包含视频占位符
    
    return hasVideoContainerFeatures;
  }

  // 测试RTMP连接 - 简化版本
  async testConnection(playerId) {
    const player = this.players.get(playerId);
    const logger = this.loggers.get(playerId);
    
    if (!player || !logger) {
      console.error(`Video stream not found: ${playerId}`);
      return;
    }

    const rtmpInput = document.querySelector(`[data-input="rtmp-url"][data-player-id="${playerId}"]`);
    if (!rtmpInput) {
      logger.log('未找到RTMP输入框', 'error');
      return;
    }

    const rtmpUrl = rtmpInput.value.trim();
    if (!rtmpUrl) {
      logger.log('请输入RTMP URL', 'warning');
      return;
    }

    logger.log(`开始测试连接: ${rtmpUrl}`, 'info');
    
    this.updateConnectionStatus(playerId, 'testing', '测试中...');

    try {
      const host = player.extractHost(rtmpUrl);
      const testUrl = `http://${host}:8889/`;
      
      const response = await fetch(testUrl, { 
        method: 'GET', 
        mode: 'no-cors',
        signal: AbortSignal.timeout(3000)
      });
      
      logger.log('连接测试成功: MediaMTX服务可达', 'success');
      this.updateConnectionStatus(playerId, 'success', '连接正常');
      
    } catch (error) {
      logger.log(`连接测试失败: ${error.message}`, 'error');
      this.updateConnectionStatus(playerId, 'error', '连接失败');
    }
  }

  // 切换视频流播放
  async toggleStream(playerId) {
    const player = this.players.get(playerId);
    const logger = this.loggers.get(playerId);
    
    if (!player || !logger) {
      console.error(`Video stream not found: ${playerId}`);
      return;
    }

    const rtmpInput = document.querySelector(`[data-input="rtmp-url"][data-player-id="${playerId}"]`);
    const toggleButton = document.querySelector(`[data-action="toggle-stream"][data-player-id="${playerId}"]`);
    
    if (!rtmpInput) {
      logger.log('未找到RTMP输入框', 'error');
      return;
    }
    
    if (!toggleButton) {
      logger.log('未找到播放按钮', 'error');
      return;
    }

    const rtmpUrl = rtmpInput.value.trim();
    
    if (player.isPlaying) {
      // 停止播放
      logger.log('停止推流播放', 'info');
      
      this.updatePlayButton(toggleButton, 'play');
      this.updateConnectionStatus(playerId, 'idle', '待连接');
      
      player.stopStream();
      
    } else {
      // 开始播放
      if (!rtmpUrl) {
        logger.log('请输入RTMP URL', 'warning');
        return;
      }
      
      this.updatePlayButton(toggleButton, 'connecting');
      
      const success = await player.startStream(rtmpUrl);
      
      if (success) {
        this.updatePlayButton(toggleButton, 'stop');
        this.updateConnectionStatus(playerId, 'streaming', '正在播放');
      } else {
        this.updatePlayButton(toggleButton, 'play');
        this.updateConnectionStatus(playerId, 'error', '播放失败');
      }
    }
  }

  // 更新连接状态显示
  updateConnectionStatus(playerId, status, message) {
    const statusElement = document.querySelector(`[data-status="${playerId}"]`);
    if (!statusElement) return;

    const statusClasses = {
      testing: 'status-indicator status-warning',
      success: 'status-indicator status-success', 
      error: 'status-indicator status-error',
      idle: 'status-indicator status-info',
      streaming: 'status-indicator status-success'
    };

    const statusIcons = {
      testing: 'hourglass_empty',
      success: 'check_circle',
      error: 'error', 
      idle: 'pending',
      streaming: 'play_circle'
    };

    statusElement.className = statusClasses[status] || 'status-indicator status-info';
    statusElement.innerHTML = `
      <span class="material-symbols-outlined text-sm mr-1 ${status === 'testing' ? 'animate-spin' : ''}">
        ${statusIcons[status] || 'help'}
      </span>
      ${message}
    `;
  }

  // 更新播放按钮显示
  updatePlayButton(button, state) {
    const buttonStates = {
      play: {
        icon: 'play_arrow',
        text: '开始推流',
        class: 'px-6 py-3 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg shadow-md transition-all duration-200 flex items-center'
      },
      connecting: {
        icon: 'hourglass_empty',
        text: '连接中...',
        class: 'px-6 py-3 bg-yellow-500 hover:bg-yellow-600 text-white font-semibold rounded-lg shadow-md transition-all duration-200 flex items-center'
      },
      stop: {
        icon: 'stop',
        text: '停止推流', 
        class: 'px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg shadow-md transition-all duration-200 flex items-center'
      }
    };

    const config = buttonStates[state] || buttonStates.play;
    
    button.className = config.class;
    button.innerHTML = `
      <span class="material-symbols-outlined mr-2 text-xl ${config.class.includes('animate-spin') ? 'animate-spin' : ''}">
        ${config.icon}
      </span>
      ${config.text}
    `;
  }

  // 获取播放器实例
  getPlayer(playerId) {
    return this.players.get(playerId);
  }

  // 获取日志记录器
  getLogger(playerId) {
    return this.loggers.get(playerId);
  }

  // 清理资源
  cleanup() {
    this.players.forEach((player) => {
      if (player.isPlaying) {
        player.stopStream();
      }
    });
    
    this.players.clear();
    this.loggers.clear();
  }
}

// 全局实例
export const videoStreamManager = new VideoStreamManager();