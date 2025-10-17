/**
 * 云端控制授权控制器
 * 负责请求和释放无人机云端飞行控制权
 */

import { deviceContext, cardStateManager } from '@/lib/state.js';
import { topicServiceManager, messageRouter } from '@/lib/services.js';

export class CloudControlCardUI {
  constructor() {
    this.elements = {};

    // 状态属性（将被代理管理）
    this.authStatus = 'unauthorized';  // unauthorized, requesting, authorized
    this.controlKeys = [];
    this.logsHTML = '<div class="text-gray-500">[系统] 云端控制授权卡片已初始化</div>';
    this.userId = 'cloud_user_001';
    this.userCallsign = 'CloudPilot';

    this.init();

    // 注册到状态管理器
    return cardStateManager.register(this, 'cloudControl', {
      debug: true
    });
  }

  init() {
    this.bindElements();
    this.bindEvents();
    this.setupDeviceContextListener();
    this.setupMqttListener();
    this.setupStateRestoreListener();
    this.updateUI();
  }

  bindElements() {
    this.elements = {
      serialInput: document.querySelector('[data-config="device-serial"]'),
      userIdInput: document.querySelector('[data-config="user-id"]'),
      userCallsignInput: document.querySelector('[data-config="user-callsign"]'),
      requestBtn: document.getElementById('request-auth-btn'),
      releaseBtn: document.getElementById('release-control-btn'),
      clearLogsBtn: document.getElementById('clear-cloud-logs-btn'),
      cloudStatus: document.getElementById('cloud-status'),
      controlKeysDisplay: document.getElementById('control-keys'),
      mqttStatus: document.getElementById('mqtt-status'),
      logs: document.getElementById('cloud-logs')
    };
  }

  bindEvents() {
    this.elements.userIdInput?.addEventListener('input', (e) => {
      this.userId = e.target.value;
    });

    this.elements.userCallsignInput?.addEventListener('input', (e) => {
      this.userCallsign = e.target.value;
    });

    this.elements.requestBtn?.addEventListener('click', () => this.requestAuth());
    this.elements.releaseBtn?.addEventListener('click', () => this.releaseControl());
    this.elements.clearLogsBtn?.addEventListener('click', () => this.clearLogs());
  }

  setupDeviceContextListener() {
    if (typeof window !== 'undefined') {
      window.addEventListener('device-changed', (event) => {
        const currentSN = event.detail?.currentSN;
        if (this.elements.serialInput) {
          this.elements.serialInput.value = currentSN || '';
        }
        this.updateMqttStatus();
      });

      // 初始化时设置当前设备
      const currentDevice = deviceContext.getCurrentDevice();
      if (currentDevice && this.elements.serialInput) {
        this.elements.serialInput.value = currentDevice;
      }
    }
  }

  setupMqttListener() {
    if (typeof window !== 'undefined') {
      // 监听MQTT连接状态变化
      window.addEventListener('mqtt-connection-changed', () => {
        this.updateMqttStatus();
      });

      // 使用MessageRouter注册服务回复处理
      this.registerServiceHandlers();
    }
  }

  /**
   * 注册服务回复处理器
   */
  registerServiceHandlers() {
    // 注册云端控制服务的消息处理
    messageRouter.registerServiceRoute('cloud_control_auth_request', (message) => {
      this.handleAuthRequestReply(message);
    });

    messageRouter.registerServiceRoute('cloud_control_release', (message) => {
      this.handleReleaseReply(message);
    });

    this.addLog('信息', '已注册云端控制服务消息处理器');
  }

  setupStateRestoreListener() {
    if (typeof window !== 'undefined') {
      window.addEventListener('card-state-restored', () => {
        console.log('[CloudControlCard] 状态已恢复，更新UI');
        this.updateUI();
        this.restoreLogsFromState();
        this.restoreInputsFromState();
      });
    }
  }

  /**
   * 请求云端控制授权
   */
  async requestAuth() {
    const currentSN = deviceContext.getCurrentDevice();
    if (!currentSN) {
      this.addLog('错误', '未选择设备');
      return;
    }

    this.addLog('信息', '发送授权请求...');
    this.authStatus = 'requesting';
    this.updateUI();

    try {
      const result = await topicServiceManager.callService(sn, 'cloud_control_auth', {
        user_id: this.userId || 'cloud_user_001',
        user_callsign: this.userCallsign || 'CloudPilot'
      });

      if (result.success) {
        this.addLog('成功', `已发送授权请求 (用户: ${this.userCallsign})`);
        this.addLog('信息', `发送消息:\n${JSON.stringify(result.data, null, 2)}`);
      } else {
        this.addLog('错误', `发送失败: ${result.error}`);
        this.authStatus = 'unauthorized';
        this.updateUI();
      }
    } catch (error) {
      this.addLog('错误', `请求异常: ${error.message}`);
      this.authStatus = 'unauthorized';
      this.updateUI();
    }
  }

  /**
   * 释放云端控制
   */
  async releaseControl() {
    const currentSN = deviceContext.getCurrentDevice();
    if (!currentSN) {
      this.addLog('错误', '未选择设备');
      return;
    }

    this.addLog('信息', '发送释放控制请求...');

    try {
      const result = await topicServiceManager.callService(sn, 'cloud_control_release', {});

      if (result.success) {
        this.addLog('成功', '已发送释放控制请求');
        this.addLog('信息', `发送消息:\n${JSON.stringify(result.data, null, 2)}`);
      } else {
        this.addLog('错误', `发送失败: ${result.error}`);
      }
    } catch (error) {
      this.addLog('错误', `请求异常: ${error.message}`);
    }
  }

  /**
   * 处理授权请求回复
   */
  handleAuthRequestReply(msg) {
    const result = msg.data?.result;
    const status = msg.data?.output?.status;

    if (result === 0 && status === 'ok') {
      this.authStatus = 'authorized';
      this.controlKeys = ['flight'];
      this.addLog('成功', '✓ 云端控制授权已批准');
    } else {
      this.authStatus = 'unauthorized';
      this.controlKeys = [];
      this.addLog('错误', `授权请求被拒绝 (result: ${result})`);
    }

    this.updateUI();
  }

  /**
   * 处理释放控制回复
   */
  handleReleaseReply(msg) {
    const result = msg.data?.result;
    const status = msg.data?.output?.status;

    if (result === 0 && status === 'ok') {
      this.authStatus = 'unauthorized';
      this.controlKeys = [];
      this.addLog('成功', '✓ 云端控制已释放');
    } else {
      this.addLog('错误', `释放控制失败 (result: ${result})`);
    }

    this.updateUI();
  }

  /**
   * 更新MQTT连接状态显示
   */
  updateMqttStatus() {
    if (!this.elements.mqttStatus) return;

    const currentSN = deviceContext.getCurrentDevice();
    if (!currentSN) {
      this.elements.mqttStatus.textContent = '未选择设备';
      return;
    }

    const connection = window.mqttManager?.getConnection(currentSN);
    if (connection && connection.isConnected()) {
      this.elements.mqttStatus.textContent = '已连接';
      this.elements.mqttStatus.classList.add('text-green-600');
      this.elements.mqttStatus.classList.remove('text-gray-600');
    } else {
      this.elements.mqttStatus.textContent = '未连接';
      this.elements.mqttStatus.classList.add('text-gray-600');
      this.elements.mqttStatus.classList.remove('text-green-600');
    }
  }

  /**
   * 更新UI显示
   */
  updateUI() {
    // 更新状态显示
    if (this.elements.cloudStatus) {
      const statusText = {
        'unauthorized': '未授权',
        'requesting': '请求中...',
        'authorized': '已授权'
      };
      this.elements.cloudStatus.textContent = statusText[this.authStatus] || this.authStatus;

      // 更新颜色
      this.elements.cloudStatus.classList.remove('text-gray-600', 'text-yellow-600', 'text-green-600');
      if (this.authStatus === 'authorized') {
        this.elements.cloudStatus.classList.add('text-green-600');
      } else if (this.authStatus === 'requesting') {
        this.elements.cloudStatus.classList.add('text-yellow-600');
      } else {
        this.elements.cloudStatus.classList.add('text-gray-600');
      }
    }

    // 更新控制权显示
    if (this.elements.controlKeysDisplay) {
      this.elements.controlKeysDisplay.textContent =
        this.controlKeys.length > 0 ? this.controlKeys.join(', ') : '-';
    }

    // 更新按钮显示
    if (this.authStatus === 'authorized') {
      this.elements.requestBtn?.classList.add('hidden');
      this.elements.releaseBtn?.classList.remove('hidden');
    } else {
      this.elements.requestBtn?.classList.remove('hidden');
      this.elements.releaseBtn?.classList.add('hidden');
    }

    // 禁用/启用请求按钮
    if (this.elements.requestBtn) {
      this.elements.requestBtn.disabled = (this.authStatus === 'requesting');
    }

    this.updateMqttStatus();
  }

  /**
   * 添加日志
   */
  addLog(type, message) {
    const timestamp = new Date().toLocaleTimeString();
    const logClass = type === '成功' ? 'text-green-400' :
                    type === '错误' ? 'text-red-400' :
                    type === '警告' ? 'text-yellow-400' : 'text-blue-400';

    const logEntry = `<div class="${logClass}">[${timestamp}] [${type}] ${message}</div>`;

    // 更新状态属性（自动保存）
    this.logsHTML = (this.logsHTML || '') + logEntry;

    // 同时更新DOM
    if (this.elements.logs) {
      this.elements.logs.innerHTML = this.logsHTML;
      this.elements.logs.scrollTop = this.elements.logs.scrollHeight;
    }
  }

  /**
   * 清空日志
   */
  clearLogs() {
    this.logsHTML = '<div class="text-gray-500">[系统] 日志已清空</div>';
    if (this.elements.logs) {
      this.elements.logs.innerHTML = this.logsHTML;
    }
  }

  /**
   * 从状态恢复日志显示
   */
  restoreLogsFromState() {
    if (this.elements.logs && this.logsHTML) {
      this.elements.logs.innerHTML = this.logsHTML;
      this.elements.logs.scrollTop = this.elements.logs.scrollHeight;
    }
  }

  /**
   * 从状态恢复输入框
   */
  restoreInputsFromState() {
    if (this.elements.userIdInput && this.userId) {
      this.elements.userIdInput.value = this.userId;
    }
    if (this.elements.userCallsignInput && this.userCallsign) {
      this.elements.userCallsignInput.value = this.userCallsign;
    }
  }

  /**
   * 生成UUID
   */
  generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
}

// 全局实例
export const cloudControlCardUI = new CloudControlCardUI();
