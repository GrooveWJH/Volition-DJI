/**
 * DRC模式业务逻辑控制器
 * 纯业务逻辑，无DOM依赖，可在任何环境运行
 */

import { deviceContext } from '#lib/state.js';
import { topicServiceManager, messageRouter } from '#lib/services.js';
import { DrcStateManager } from './drc-state-manager.js';
import { ErrorHandler } from './error-handler.js';
import { LogManager } from './log-manager.js';
import debugLogger from '#lib/debug.js';

export class DrcModeController {
  constructor() {
    // 初始化子模块
    this.drcStateManager = new DrcStateManager();
    this.logManager = new LogManager();
    this.errorHandler = new ErrorHandler(this.logManager);

    // 状态属性
    this.drcStatus = 'idle';
    this.mqttBrokerConfig = {
      address: '',
      client_id: '',
      username: '',
      password: '',
      enable_tls: true,
      anonymous: false
    };
    this.osdFrequency = 30;
    this.hsiFrequency = 10;
    this.heartbeatActive = false;
    this.heartbeatInterval = null;
    this.heartbeatSeq = 0;
    this.logsHTML = '<div class="text-gray-500" data-log-type="系统">[系统] DRC模式管理卡片已初始化</div>';
    this.lastError = null;
    this.enteredAt = null;

    this.init();
  }

  init() {
    this.drcStateManager.loadConfig();
    this.syncFromDrcState();
    this.registerServiceHandlers();
    this.logManager.addLog('系统', 'DRC模式控制器已初始化');
  }

  registerServiceHandlers() {
    // 只在浏览器环境注册消息处理器
    if (typeof window !== 'undefined' && messageRouter && messageRouter.addHandler) {
      messageRouter.addHandler('cloud_control_auth_reply', (message) => {
        this.handleCloudControlAuthReply(message);
      });

      messageRouter.addHandler('drc_mode_enter_reply', (message) => {
        this.handleDrcEnterReply(message);
      });

      messageRouter.addHandler('drc_mode_exit_reply', (message) => {
        this.handleDrcExitReply(message);
      });

      messageRouter.addHandler('hb_ack', (message) => {
        this.handleHeartbeatAck(message);
      });
    }
  }

  syncFromDrcState() {
    this.mqttBrokerConfig = { ...this.drcStateManager.mqttBrokerConfig };
    this.osdFrequency = this.drcStateManager.osdFrequency;
    this.hsiFrequency = this.drcStateManager.hsiFrequency;
  }

  syncToDrcState() {
    this.drcStateManager.mqttBrokerConfig = { ...this.mqttBrokerConfig };
    this.drcStateManager.osdFrequency = this.osdFrequency;
    this.drcStateManager.hsiFrequency = this.hsiFrequency;
    this.drcStateManager.saveConfig();
  }

  async enterDrcMode() {
    const currentSN = deviceContext.getCurrentDevice();
    if (!currentSN) {
      throw new Error('未选择设备');
    }

    try {
      this.drcStatus = 'entering';
      this.lastError = null;
      this.logManager.addLog('DRC', '开始进入DRC模式...');

      this.syncToDrcState();

      const requestData = this.buildMqttBrokerMessage();

      debugLogger.service('发送DRC模式进入请求', {
        topic: 'drc_mode_enter',
        data: requestData
      });

      const result = await topicServiceManager.callService(currentSN, 'drc_mode_enter', requestData);

      debugLogger.service('DRC模式进入回复', {
        topic: 'drc_mode_enter_reply',
        result: result
      });

      if (!result.success) {
        throw new Error(result.error || 'DRC模式进入失败');
      }

      this.logManager.addLog('DRC', 'DRC模式进入请求发送成功');
      return { success: true, data: result.data };

    } catch (error) {
      this.drcStatus = 'error';
      this.lastError = error.message;
      this.logManager.addLog('错误', `DRC模式进入失败: ${error.message}`);
      throw error;
    }
  }

  async exitDrcMode() {
    const currentSN = deviceContext.getCurrentDevice();
    if (!currentSN) {
      throw new Error('未选择设备');
    }

    try {
      this.drcStatus = 'exiting';
      this.lastError = null;
      this.logManager.addLog('DRC', '开始退出DRC模式...');

      const result = await topicServiceManager.callService(currentSN, 'drc_mode_exit', {});

      if (!result.success) {
        throw new Error(result.error || 'DRC模式退出失败');
      }

      this.stopHeartbeat();
      this.logManager.addLog('DRC', 'DRC模式退出成功');
      return { success: true, data: result.data };

    } catch (error) {
      this.drcStatus = 'error';
      this.lastError = error.message;
      this.logManager.addLog('错误', `DRC模式退出失败: ${error.message}`);
      throw error;
    }
  }

  buildMqttBrokerMessage() {
    return {
      mqtt_broker: {
        address: this.mqttBrokerConfig.address,
        client_id: this.mqttBrokerConfig.client_id,
        username: this.mqttBrokerConfig.anonymous ? '' : this.mqttBrokerConfig.username,
        password: this.mqttBrokerConfig.anonymous ? '' : this.mqttBrokerConfig.password,
        enable_tls: this.mqttBrokerConfig.enable_tls
      },
      osd_frequency: this.osdFrequency,
      hsi_frequency: this.hsiFrequency
    };
  }

  handleCloudControlAuthReply(message) {
    this.logManager.addLog('云控', `云端授权回复: ${JSON.stringify(message)}`);
  }

  handleDrcEnterReply(message) {
    try {
      const data = message.data || message;
      this.logManager.addLog('DRC', `DRC进入回复: ${JSON.stringify(data)}`);

      if (data.result === 0) {
        this.drcStatus = 'active';
        this.enteredAt = Date.now();
        this.logManager.addLog('DRC', 'DRC模式已激活');
        this.startHeartbeat();
      } else {
        this.drcStatus = 'error';
        this.lastError = `DRC进入失败，错误码: ${data.result}`;
        this.logManager.addLog('错误', this.lastError);
      }
    } catch (error) {
      this.drcStatus = 'error';
      this.lastError = `处理DRC进入回复时出错: ${error.message}`;
      this.logManager.addLog('错误', this.lastError);
    }
  }

  handleDrcExitReply(message) {
    try {
      const data = message.data || message;
      this.logManager.addLog('DRC', `DRC退出回复: ${JSON.stringify(data)}`);

      if (data.result === 0) {
        this.drcStatus = 'idle';
        this.enteredAt = null;
        this.stopHeartbeat();
        this.logManager.addLog('DRC', 'DRC模式已退出');
      } else {
        this.drcStatus = 'error';
        this.lastError = `DRC退出失败，错误码: ${data.result}`;
        this.logManager.addLog('错误', this.lastError);
      }
    } catch (error) {
      this.drcStatus = 'error';
      this.lastError = `处理DRC退出回复时出错: ${error.message}`;
      this.logManager.addLog('错误', this.lastError);
    }
  }

  handleHeartbeatAck(message) {
    const data = message.data || message;
    this.logManager.addLog('心跳', `心跳确认: seq=${data.seq}`);
  }

  startHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    this.heartbeatActive = true;
    this.heartbeatSeq = 0;

    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, 200); // 5Hz = 200ms

    this.logManager.addLog('心跳', '心跳发送已启动 (5Hz)');
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    this.heartbeatActive = false;
    this.logManager.addLog('心跳', '心跳发送已停止');
  }

  async sendHeartbeat() {
    const currentSN = deviceContext.getCurrentDevice();
    if (!currentSN) return;

    try {
      this.heartbeatSeq++;
      const heartbeatData = {
        seq: Date.now(),
        timestamp: Date.now()
      };

      debugLogger.service('发送心跳请求', {
        topic: 'heart_beat',
        data: heartbeatData
      });

      const result = await topicServiceManager.callService(currentSN, 'heart_beat', heartbeatData);

      debugLogger.service('心跳回复', {
        topic: 'heart_beat_reply',
        result: result
      });

      if (result.success) {
        this.logManager.addLog('心跳', `心跳发送成功: seq=${heartbeatData.seq}`);
      }
    } catch (error) {
      this.logManager.addLog('错误', `心跳发送失败: ${error.message}`);
    }
  }

  updateFrequency(type, value) {
    if (type === 'osd') {
      this.osdFrequency = value;
    } else if (type === 'hsi') {
      this.hsiFrequency = value;
    }
    this.syncToDrcState();
  }

  updateMqttConfig(config) {
    this.mqttBrokerConfig = { ...this.mqttBrokerConfig, ...config };
    this.syncToDrcState();
  }

  updateAnonymousMode(enabled) {
    this.mqttBrokerConfig.anonymous = enabled;
    if (enabled) {
      this.mqttBrokerConfig.username = '';
      this.mqttBrokerConfig.password = '';
    }
    this.syncToDrcState();
  }

  updateClientIdSuggestion(deviceSN) {
    if (deviceSN && !this.mqttBrokerConfig.client_id) {
      this.mqttBrokerConfig.client_id = `drc-${deviceSN}`;
      this.syncToDrcState();
    }
  }

  getDrcDuration() {
    if (!this.enteredAt) return 0;
    return Math.floor((Date.now() - this.enteredAt) / 1000);
  }

  getState() {
    return {
      drcStatus: this.drcStatus,
      mqttBrokerConfig: this.mqttBrokerConfig,
      osdFrequency: this.osdFrequency,
      hsiFrequency: this.hsiFrequency,
      heartbeatActive: this.heartbeatActive,
      lastError: this.lastError,
      enteredAt: this.enteredAt,
      logsHTML: this.logsHTML
    };
  }
}