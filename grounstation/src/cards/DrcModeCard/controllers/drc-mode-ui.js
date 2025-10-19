/**
 * DRC模式控制器 - 极简版
 * UI层：绑定DOM和事件
 */

import { deviceContext, cardStateManager } from '#lib/state.js';
import { DrcStateManager } from './drc-state-manager.js';
import { LogManager } from './log-manager.js';
import debugLogger from '#lib/debug.js';

const HEARTBEAT_INTERVAL_MS = 1000; // 1Hz

export class DrcModeUI {
  constructor() {
    this.elements = {};

    // 子模块
    this.stateManager = new DrcStateManager();
    this.logManager = new LogManager();

    // 内部状态（不保存到cardStateManager，避免干扰）
    this.drcStatus = 'idle'; // idle | entering | active | exiting | error
    this.heartbeatActive = false;
    this.heartbeatInterval = null;
    this.logsHTML = this.logManager.getLogsHTML();

    this.init();

    // 不注册到cardStateManager，避免状态持久化干扰长连接
  }

  init() {
    if (typeof document === 'undefined') return;

    this.bindElements();
    this.bindEvents();
    this.setupDeviceListener();
    this.updateUI();
  }

  bindElements() {
    this.elements = {
      // MQTT配置
      mqttAddress: document.getElementById('mqtt-address'),
      mqttClientId: document.getElementById('mqtt-client-id'),
      mqttUsername: document.getElementById('mqtt-username'),
      mqttPassword: document.getElementById('mqtt-password'),
      mqttTls: document.getElementById('mqtt-tls-toggle'),
      mqttAnonymous: document.getElementById('mqtt-anonymous'),

      // 频率
      osdFrequency: document.getElementById('osd-frequency'),
      osdFrequencyValue: document.getElementById('osd-frequency-value'),
      hsiFrequency: document.getElementById('hsi-frequency'),
      hsiFrequencyValue: document.getElementById('hsi-frequency-value'),

      // 控制按钮
      enterBtn: document.getElementById('enter-drc-btn'),
      exitBtn: document.getElementById('exit-drc-btn'),
      enterBtnText: document.getElementById('enter-btn-text'),
      enterBtnSpinner: document.getElementById('enter-btn-spinner'),
      enterBtnIcon: document.getElementById('enter-btn-icon'),

      // 心跳指示器
      heartbeatIndicator: document.getElementById('heartbeat-indicator'),
      heartbeatStatus: document.getElementById('heartbeat-status'),

      // 日志
      logs: document.getElementById('drc-logs'),
      logFilter: document.getElementById('drc-log-filter'),
      clearLogsBtn: document.getElementById('clear-drc-logs-btn'),
    };

    this.logManager.setElements(this.elements);
    this.restoreInputs();
  }

  bindEvents() {
    // MQTT配置
    this.elements.mqttAddress?.addEventListener('input', (e) => {
      this.stateManager.mqttBrokerConfig.address = e.target.value;
      this.stateManager.saveConfig();
    });

    this.elements.mqttUsername?.addEventListener('input', (e) => {
      this.stateManager.mqttBrokerConfig.username = e.target.value;
      this.stateManager.saveConfig();
    });

    this.elements.mqttPassword?.addEventListener('input', (e) => {
      this.stateManager.mqttBrokerConfig.password = e.target.value;
      this.stateManager.saveConfig();
    });

    this.elements.mqttTls?.addEventListener('change', (e) => {
      this.stateManager.mqttBrokerConfig.enable_tls = e.target.checked;
      this.stateManager.saveConfig();
    });

    this.elements.mqttAnonymous?.addEventListener('change', (e) => {
      this.stateManager.mqttBrokerConfig.anonymous = e.target.checked;
      if (e.target.checked) {
        this.stateManager.mqttBrokerConfig.username = '';
        this.stateManager.mqttBrokerConfig.password = '';
        this.elements.mqttUsername.value = '';
        this.elements.mqttPassword.value = '';
      }
      this.stateManager.saveConfig();
    });

    // 频率
    this.elements.osdFrequency?.addEventListener('input', (e) => {
      this.stateManager.osdFrequency = parseInt(e.target.value);
      this.elements.osdFrequencyValue.textContent = `${this.stateManager.osdFrequency}Hz`;
      this.stateManager.saveConfig();
    });

    this.elements.hsiFrequency?.addEventListener('input', (e) => {
      this.stateManager.hsiFrequency = parseInt(e.target.value);
      this.elements.hsiFrequencyValue.textContent = `${this.stateManager.hsiFrequency}Hz`;
      this.stateManager.saveConfig();
    });

    // 按钮
    this.elements.enterBtn?.addEventListener('click', () => this.handleEnterDrc());
    this.elements.exitBtn?.addEventListener('click', () => this.handleExitDrc());

    // 日志
    this.elements.clearLogsBtn?.addEventListener('click', () => {
      this.logManager.clearLogs();
      this.logsHTML = this.logManager.getLogsHTML();
    });

    this.elements.logFilter?.addEventListener('change', () => {
      this.logManager.updateDisplay();
    });
  }

  setupDeviceListener() {
    if (typeof window === 'undefined') return;

    window.addEventListener('device-changed', (event) => {
      const { currentSN } = event.detail;
      if (currentSN) {
        this.stateManager.mqttBrokerConfig.client_id = `station-${currentSN}`;
        if (this.elements.mqttClientId) {
          this.elements.mqttClientId.value = this.stateManager.mqttBrokerConfig.client_id;
        }
      }
    });
  }

  restoreInputs() {
    if (!this.elements.mqttAddress) return;

    this.elements.mqttAddress.value = this.stateManager.mqttBrokerConfig.address;
    this.elements.mqttClientId.value = this.stateManager.mqttBrokerConfig.client_id;
    this.elements.mqttUsername.value = this.stateManager.mqttBrokerConfig.username;
    this.elements.mqttPassword.value = this.stateManager.mqttBrokerConfig.password;
    this.elements.mqttTls.checked = this.stateManager.mqttBrokerConfig.enable_tls;
    this.elements.mqttAnonymous.checked = this.stateManager.mqttBrokerConfig.anonymous;

    this.elements.osdFrequency.value = this.stateManager.osdFrequency;
    this.elements.osdFrequencyValue.textContent = `${this.stateManager.osdFrequency}Hz`;
    this.elements.hsiFrequency.value = this.stateManager.hsiFrequency;
    this.elements.hsiFrequencyValue.textContent = `${this.stateManager.hsiFrequency}Hz`;
  }

  async handleEnterDrc() {
    const sn = deviceContext.getCurrentDevice();

    if (!sn) {
      this.addLog('错误', '未选择设备');
      return;
    }

    if (this.drcStatus === 'entering' || this.drcStatus === 'active') {
      this.addLog('警告', 'DRC模式已在运行中');
      return;
    }

    this.drcStatus = 'entering';
    this.updateUI();
    this.addLog('信息', `开始进入 DRC 模式 (设备: ${sn})`);

    try {
      const mqttHost = this.stateManager.mqttBrokerConfig.address.split(':')[0] || '192.168.31.73';
      this.addLog('调试', `MQTT配置: ws://${mqttHost}:8083/mqtt`);

      // 调用API
      const result = await this.callDrcAPI('enter', {
        sn,
        mqttHost,
        mqttPort: 8083,
        username: this.stateManager.mqttBrokerConfig.anonymous ? '' : this.stateManager.mqttBrokerConfig.username,
        password: this.stateManager.mqttBrokerConfig.anonymous ? '' : this.stateManager.mqttBrokerConfig.password,
        osdFreq: this.stateManager.osdFrequency,
        hsiFreq: this.stateManager.hsiFrequency,
        enableTls: this.stateManager.mqttBrokerConfig.enable_tls,
      });

      if (!result.success) {
        this.drcStatus = 'error';
        this.addLog('错误', `进入DRC失败: ${result.error || 'Unknown error'}`);
        this.updateUI();
        return;
      }

      this.stateManager.setDrcActive();
      this.drcStatus = 'active';
      this.addLog('成功', '✓ 已成功进入DRC模式');
      this.startHeartbeat();
      this.updateUI();
    } catch (error) {
      this.drcStatus = 'error';
      this.addLog('错误', `进入DRC失败: ${error.message}`);
      this.updateUI();
    }
  }

  async handleExitDrc() {
    const sn = deviceContext.getCurrentDevice();

    if (!sn) {
      this.addLog('错误', '未选择设备');
      return;
    }

    this.drcStatus = 'exiting';
    this.updateUI();
    this.addLog('信息', `开始退出 DRC 模式 (设备: ${sn})`);

    try {
      const mqttHost = this.stateManager.mqttBrokerConfig.address.split(':')[0] || '192.168.31.73';

      // 调用API
      const result = await this.callDrcAPI('exit', {
        sn,
        mqttHost,
        mqttPort: 8083,
        username: this.stateManager.mqttBrokerConfig.anonymous ? '' : this.stateManager.mqttBrokerConfig.username,
        password: this.stateManager.mqttBrokerConfig.anonymous ? '' : this.stateManager.mqttBrokerConfig.password,
      });

      if (!result.success) {
        this.drcStatus = 'error';
        this.addLog('错误', `退出DRC失败: ${result.error || 'Unknown error'}`);
        this.updateUI();
        return;
      }

      this.stopHeartbeat();
      this.stateManager.resetDrcState();
      this.drcStatus = 'idle';
      this.addLog('成功', '✓ 已退出DRC模式');
      this.updateUI();
    } catch (error) {
      this.drcStatus = 'error';
      this.addLog('错误', `退出DRC失败: ${error.message}`);
      this.updateUI();
    }
  }

  startHeartbeat() {
    if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);

    this.heartbeatActive = true;
    this.heartbeatInterval = setInterval(() => this.sendHeartbeatInternal(), HEARTBEAT_INTERVAL_MS);
    this.addLog('心跳', '心跳发送已启动 (1Hz)');
    this.updateUI();
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    this.heartbeatActive = false;
    this.addLog('心跳', '心跳发送已停止');
    this.updateUI();
  }

  async sendHeartbeatInternal() {
    const sn = deviceContext.getCurrentDevice();
    if (!sn || !this.heartbeatActive) return;

    try {
      // 使用长连接发送心跳，不创建临时连接
      if (typeof window !== 'undefined' && window.mqttManager) {
        const connection = window.mqttManager.getConnection(sn);

        if (!connection || !connection.isConnected) {
          debugLogger.warn('[DRC] 长连接未建立，跳过心跳');
          this.addLog('警告', '长连接断开，心跳发送失败');
          return;
        }

        const topic = `thing/product/${sn}/drc/down`;
        const message = {
          seq: Date.now(),
          method: 'heart_beat',
          data: { timestamp: Date.now() },
        };

        // 同步发送，不等待完成
        connection.publish(topic, message, { qos: 0 });

        // 打印每次心跳的JSON
        const timestamp = new Date().toLocaleTimeString();
        this.addLog('心跳', `[${timestamp}] ${JSON.stringify(message)}`);
      }
    } catch (error) {
      debugLogger.error('[DRC] 心跳发送失败:', error);
      this.addLog('错误', `心跳发送失败: ${error.message}`);
    }
  }

  updateUI() {
    if (!this.elements.enterBtn) return;

    // 按钮状态
    switch (this.drcStatus) {
      case 'entering':
        this.elements.enterBtn.disabled = true;
        this.elements.enterBtnSpinner.classList.remove('hidden');
        this.elements.enterBtnIcon.classList.add('hidden');
        this.elements.enterBtnText.textContent = '正在进入...';
        this.elements.exitBtn.classList.add('hidden');
        break;

      case 'active':
        this.elements.enterBtn.classList.add('hidden');
        this.elements.exitBtn.classList.remove('hidden');
        this.elements.exitBtn.disabled = false;
        const exitBtnTextActive = this.elements.exitBtn.querySelector('span:last-child');
        if (exitBtnTextActive) exitBtnTextActive.textContent = '退出DRC模式';
        break;

      case 'exiting':
        this.elements.exitBtn.disabled = true;
        const exitBtnText = this.elements.exitBtn.querySelector('span:last-child');
        if (exitBtnText) exitBtnText.textContent = '正在退出...';
        break;

      case 'idle':
      case 'error':
        this.elements.enterBtn.disabled = false;
        this.elements.enterBtn.classList.remove('hidden');
        this.elements.enterBtnSpinner.classList.add('hidden');
        this.elements.enterBtnIcon.classList.remove('hidden');
        this.elements.enterBtnText.textContent = '进入DRC模式';
        this.elements.exitBtn.classList.add('hidden');
        this.elements.exitBtn.disabled = false;
        break;
    }

    // 心跳指示器
    if (this.heartbeatActive) {
      this.elements.heartbeatIndicator.classList.remove('bg-gray-400');
      this.elements.heartbeatIndicator.classList.add('bg-green-500', 'animate-pulse');
      this.elements.heartbeatStatus.textContent = '运行中';
      this.elements.heartbeatStatus.classList.remove('text-gray-600');
      this.elements.heartbeatStatus.classList.add('text-green-600');
    } else {
      this.elements.heartbeatIndicator.classList.remove('bg-green-500', 'animate-pulse');
      this.elements.heartbeatIndicator.classList.add('bg-gray-400');
      this.elements.heartbeatStatus.textContent = '未启动';
      this.elements.heartbeatStatus.classList.remove('text-green-600');
      this.elements.heartbeatStatus.classList.add('text-gray-600');
    }
  }

  async callDrcAPI(action, params) {
    const response = await fetch('/api/drc', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action,
        ...params,
      }),
    });

    if (!response.ok) {
      throw new Error(`API请求失败: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  }

  addLog(type, message) {
    this.logManager.addLog(type, message);
  }
}

// 全局实例
export const drcModeCardUI = new DrcModeUI();
