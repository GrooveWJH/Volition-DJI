/**
 * 视频流控制逻辑
 * 处理UI交互、状态更新和用户控制操作
 */

import { CONFIG } from '@/shared/config/app-config.js';

/**
 * 视频流控制器类
 * 负责处理UI控制逻辑和状态管理
 */
export class StreamController {
  constructor() {
    this.players = new Map();
    this.loggers = new Map();
  }

  /**
   * 注册播放器和日志记录器
   * @param {string} playerId - 播放器ID
   * @param {Object} player - 播放器实例
   * @param {Object} logger - 日志记录器实例
   */
  registerPlayer(playerId, player, logger) {
    this.players.set(playerId, player);
    this.loggers.set(playerId, logger);
  }

  /**
   * 从 localStorage 获取视频配置
   * @returns {Object} 配置对象
   */
  getVideoConfig() {
    return {
      host: localStorage.getItem('video_host') || '192.168.31.14',
      rtmpUrl: localStorage.getItem('video_rtmp_url') || 'rtmp://192.168.31.14:1935/live/cam'
    };
  }

  /**
   * 测试RTMP连接
   * @param {string} playerId - 播放器ID
   */
  async testConnection(playerId) {
    const player = this.players.get(playerId);
    const logger = this.loggers.get(playerId);

    if (!player || !logger) {
      console.error(`Video stream not found: ${playerId}`);
      return;
    }

    const config = this.getVideoConfig();
    const rtmpUrl = config.rtmpUrl;

    if (!rtmpUrl) {
      logger.log('请在设置中配置RTMP URL', 'warning');
      return;
    }

    logger.log(`开始测试连接: ${rtmpUrl}`, 'info');

    this.updateConnectionStatus(playerId, 'testing', '测试中...');

    try {
      const host = player.extractHost(rtmpUrl);
      const testUrl = `http://${host}:${CONFIG.webrtc.defaultPort}/`;

      await fetch(testUrl, {
        method: 'GET',
        mode: 'no-cors',
        signal: AbortSignal.timeout(CONFIG.connection.timeoutMs)
      });

      logger.log('连接测试成功: MediaMTX服务可达', 'success');
      this.updateConnectionStatus(playerId, 'success', '连接正常');

    } catch (error) {
      logger.log(`连接测试失败: ${error.message}`, 'error');
      this.updateConnectionStatus(playerId, 'error', '连接失败');
    }
  }

  /**
   * 切换视频流播放
   * @param {string} playerId - 播放器ID
   */
  async toggleStream(playerId) {
    const player = this.players.get(playerId);
    const logger = this.loggers.get(playerId);

    if (!player || !logger) {
      console.error(`Video stream not found: ${playerId}`);
      return;
    }

    const toggleButton = document.querySelector(`[data-action="toggle-stream"][data-player-id="${playerId}"]`);

    if (!toggleButton) {
      logger.log('未找到播放按钮', 'error');
      return;
    }

    const config = this.getVideoConfig();
    const rtmpUrl = config.rtmpUrl;

    if (player.isPlaying) {
      // 停止播放
      logger.log('停止推流播放', 'info');

      this.updatePlayButton(toggleButton, 'play');
      this.updateConnectionStatus(playerId, 'idle', '待连接');

      player.stopStream();

    } else {
      // 开始播放
      if (!rtmpUrl) {
        logger.log('请在设置中配置RTMP URL', 'warning');
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

  /**
   * 更新连接状态显示
   * @param {string} playerId - 播放器ID
   * @param {string} status - 状态类型
   * @param {string} message - 状态消息
   */
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

  /**
   * 更新播放按钮显示
   * @param {HTMLElement} button - 按钮元素
   * @param {string} state - 按钮状态
   */
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

  /**
   * 批量更新多个播放器状态
   * @param {string} status - 状态类型
   * @param {string} message - 状态消息
   */
  updateAllStatus(status, message) {
    for (const playerId of this.players.keys()) {
      this.updateConnectionStatus(playerId, status, message);
    }
  }

  /**
   * 停止所有播放器
   */
  stopAllStreams() {
    for (const [playerId, player] of this.players) {
      if (player.isPlaying) {
        const toggleButton = document.querySelector(`[data-action="toggle-stream"][data-player-id="${playerId}"]`);
        if (toggleButton) {
          this.updatePlayButton(toggleButton, 'play');
        }
        this.updateConnectionStatus(playerId, 'idle', '待连接');
        player.stopStream();
      }
    }
  }

  /**
   * 获取所有播放器状态摘要
   * @returns {Object} 状态摘要
   */
  getStatusSummary() {
    const summary = {
      total: this.players.size,
      playing: 0,
      idle: 0,
      error: 0
    };

    for (const player of this.players.values()) {
      if (player.isPlaying) {
        summary.playing++;
      } else if (player.hasError) {
        summary.error++;
      } else {
        summary.idle++;
      }
    }

    return summary;
  }

  /**
   * 清理所有资源
   */
  cleanup() {
    this.stopAllStreams();
    this.players.clear();
    this.loggers.clear();
  }
}

/**
 * 全局流控制器实例
 */
export const globalStreamController = new StreamController();