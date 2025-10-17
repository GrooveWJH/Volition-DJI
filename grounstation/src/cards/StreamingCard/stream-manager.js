// 视频流协议管理器 - 基于WebRTC的低延迟视频流播放管理
import { SimpleVideoPlayer } from '@/cards/StreamingCard/webrtc-player.js';
import debugLogger from '@/lib/debug.js';
import { globalStreamController } from '@/cards/StreamingCard/stream-controls.js';

export class VideoStreamManager {
  constructor() {
    this.players = new Map();
    this.loggers = new Map();
    this.controller = globalStreamController;
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

    // 创建logger适配器来兼容原有的TerminalLogger接口
    const logger = {
      log: (message, type = 'info') => {
        const prefix = `[${playerId}]`;
        switch(type) {
          case 'error':
            debugLogger.error(prefix, message);
            break;
          case 'warning':
          case 'warn':
            debugLogger.warn(prefix, message);
            break;
          case 'success':
            debugLogger.info(prefix, '✅', message);
            break;
          default:
            debugLogger.info(prefix, message);
        }
      }
    };
    this.loggers.set(playerId, logger);

    const player = new SimpleVideoPlayer(container, logger, playerId);
    this.players.set(playerId, player);

    // 注册到控制器
    this.controller.registerPlayer(playerId, player, logger);

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

  // 测试RTMP连接 - 委托给控制器
  async testConnection(playerId) {
    return this.controller.testConnection(playerId);
  }

  // 切换视频流播放 - 委托给控制器
  async toggleStream(playerId) {
    return this.controller.toggleStream(playerId);
  }

  // 更新连接状态显示 - 委托给控制器
  updateConnectionStatus(playerId, status, message) {
    return this.controller.updateConnectionStatus(playerId, status, message);
  }

  // 更新播放按钮显示 - 委托给控制器
  updatePlayButton(button, state) {
    return this.controller.updatePlayButton(button, state);
  }

  // 获取播放器实例
  getPlayer(playerId) {
    return this.players.get(playerId);
  }

  // 获取日志记录器
  getLogger(playerId) {
    return this.loggers.get(playerId);
  }

  // 获取状态摘要
  getStatusSummary() {
    return this.controller.getStatusSummary();
  }

  // 停止所有流
  stopAllStreams() {
    return this.controller.stopAllStreams();
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
    this.controller.cleanup();
  }
}

// 全局实例
export const videoStreamManager = new VideoStreamManager();
