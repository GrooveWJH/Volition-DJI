/**
 * DRC模式UI适配器
 * 负责DOM交互，业务逻辑委托给DrcModeController
 */

import { deviceContext, cardStateManager } from '#lib/state.js';
import { DrcModeController } from './drc-mode-controller.js';
import { UIUpdater } from './ui-updater.js';

export class DrcModeCardUI {
  constructor() {
    this.elements = {};

    // 创建业务逻辑控制器
    this.controller = new DrcModeController();
    this.uiUpdater = new UIUpdater();

    // 只在浏览器环境初始化DOM相关功能
    if (typeof document !== 'undefined') {
      this.init();
    }

    // 注册到状态管理器
    return cardStateManager.register(this.controller, 'drcMode', {
      debug: true
    });
  }

  init() {
    this.bindElements();
    this.bindEvents();
    this.setupDeviceContextListener();
    this.setupMqttListener();
    this.setupStateRestoreListener();

    // 初始化UI状态
    this.updateHeartbeatUI();
    this.updateUI();
  }

  bindElements() {
    this.elements = {
      // DRC状态显示
      drcStatus: document.getElementById('drc-status'),
      drcStatusText: document.getElementById('drc-status-text'),
      drcStatusDescription: document.getElementById('drc-status-description'),
      drcStatusSpinner: document.getElementById('drc-status-spinner'),

      // 控制按钮
      enterDrcBtn: document.getElementById('enter-drc-btn'),
      enterBtnText: document.getElementById('enter-btn-text'),
      enterBtnSpinner: document.getElementById('enter-btn-spinner'),
      enterBtnIcon: document.getElementById('enter-btn-icon'),
      exitDrcBtn: document.getElementById('exit-drc-btn'),
      exitBtnText: document.getElementById('exit-btn-text'),

      // MQTT配置
      mqttAddressInput: document.getElementById('mqtt-address'),
      mqttClientIdInput: document.getElementById('mqtt-client-id'),
      mqttUsernameInput: document.getElementById('mqtt-username'),
      mqttPasswordInput: document.getElementById('mqtt-password'),
      mqttTlsToggle: document.getElementById('mqtt-tls-toggle'),
      mqttAnonymousToggle: document.getElementById('mqtt-anonymous-toggle'),
      mqttStatus: document.getElementById('drc-mqtt-status'),

      // 频率控制
      osdFrequencySlider: document.getElementById('osd-frequency'),
      osdFrequencyValue: document.getElementById('osd-frequency-value'),
      hsiFrequencySlider: document.getElementById('hsi-frequency'),
      hsiFrequencyValue: document.getElementById('hsi-frequency-value'),

      // 心跳状态
      heartbeatIndicator: document.getElementById('heartbeat-indicator'),
      heartbeatStatus: document.getElementById('heartbeat-status'),

      // 日志和结果显示
      logsContainer: document.getElementById('drc-logs'),
      operationResult: document.getElementById('operation-result')
    };

    this.uiUpdater.setElements(this.elements);
  }

  bindEvents() {
    // 进入DRC模式按钮
    this.elements.enterDrcBtn?.addEventListener('click', () => {
      this.onEnterDrcClick();
    });

    // 退出DRC模式按钮
    this.elements.exitDrcBtn?.addEventListener('click', () => {
      this.onExitDrcClick();
    });

    // MQTT配置输入事件
    this.elements.mqttAddressInput?.addEventListener('input', (e) => {
      this.controller.updateMqttConfig({ address: e.target.value });
    });

    this.elements.mqttClientIdInput?.addEventListener('input', (e) => {
      this.controller.updateMqttConfig({ client_id: e.target.value });
    });

    this.elements.mqttUsernameInput?.addEventListener('input', (e) => {
      this.controller.updateMqttConfig({ username: e.target.value });
    });

    this.elements.mqttPasswordInput?.addEventListener('input', (e) => {
      this.controller.updateMqttConfig({ password: e.target.value });
    });

    this.elements.mqttTlsToggle?.addEventListener('change', (e) => {
      this.controller.updateMqttConfig({ enable_tls: e.target.checked });
    });

    this.elements.mqttAnonymousToggle?.addEventListener('change', (e) => {
      this.controller.updateAnonymousMode(e.target.checked);
      this.updateUI();
    });

    // 频率滑块事件
    this.elements.osdFrequencySlider?.addEventListener('input', (e) => {
      this.controller.updateFrequency('osd', parseInt(e.target.value));
      this.updateUI();
    });

    this.elements.hsiFrequencySlider?.addEventListener('input', (e) => {
      this.controller.updateFrequency('hsi', parseInt(e.target.value));
      this.updateUI();
    });
  }

  setupDeviceContextListener() {
    window.addEventListener('device-changed', () => {
      const currentDevice = deviceContext.getCurrentDevice();
      if (currentDevice) {
        this.controller.updateClientIdSuggestion(currentDevice);
        this.updateUI();
      }
    });
  }

  setupMqttListener() {
    window.addEventListener('mqtt-connection-changed', () => {
      this.updateUI();
    });
  }

  setupStateRestoreListener() {
    window.addEventListener('card-state-restored', () => {
      this.updateUI();
    });
  }

  async onEnterDrcClick() {
    try {
      await this.controller.enterDrcMode();
      this.updateUI();
      this.uiUpdater.showOperationResult(true, 'DRC模式进入请求已发送');
    } catch (error) {
      this.updateUI();
      this.uiUpdater.showOperationResult(false, `进入失败: ${error.message}`);
    }
  }

  async onExitDrcClick() {
    try {
      await this.controller.exitDrcMode();
      this.updateUI();
      this.uiUpdater.showOperationResult(true, 'DRC模式退出成功');
    } catch (error) {
      this.updateUI();
      this.uiUpdater.showOperationResult(false, `退出失败: ${error.message}`);
    }
  }

  updateUI() {
    if (!this.uiUpdater.elements) return;

    this.uiUpdater.updateDrcStatusDisplay(this.controller);
    this.uiUpdater.updateButtonStates(this.controller);
    this.uiUpdater.updateConfigurationDisplay(this.controller);
    this.uiUpdater.updateMqttStatus();
    this.updateLogsDisplay();
  }

  updateHeartbeatUI() {
    if (!this.elements.heartbeatIndicator || !this.elements.heartbeatStatus) return;

    if (this.controller.heartbeatActive) {
      this.elements.heartbeatIndicator.classList.add('animate-pulse', 'bg-green-500');
      this.elements.heartbeatIndicator.classList.remove('bg-gray-400');
      this.elements.heartbeatStatus.textContent = '运行中 (5Hz)';
      this.elements.heartbeatStatus.classList.add('text-green-600');
      this.elements.heartbeatStatus.classList.remove('text-gray-600');
    } else {
      this.elements.heartbeatIndicator.classList.remove('animate-pulse', 'bg-green-500');
      this.elements.heartbeatIndicator.classList.add('bg-gray-400');
      this.elements.heartbeatStatus.textContent = '未激活';
      this.elements.heartbeatStatus.classList.remove('text-green-600');
      this.elements.heartbeatStatus.classList.add('text-gray-600');
    }
  }

  updateLogsDisplay() {
    if (this.elements.logsContainer) {
      this.elements.logsContainer.innerHTML = this.controller.logsHTML;
      this.elements.logsContainer.scrollTop = this.elements.logsContainer.scrollHeight;
    }
  }

  // 暴露控制器状态供外部访问（兼容性）
  get drcStatus() { return this.controller.drcStatus; }
  get mqttBrokerConfig() { return this.controller.mqttBrokerConfig; }
  get osdFrequency() { return this.controller.osdFrequency; }
  get hsiFrequency() { return this.controller.hsiFrequency; }
  get heartbeatActive() { return this.controller.heartbeatActive; }
  get lastError() { return this.controller.lastError; }
  get logsHTML() { return this.controller.logsHTML; }

  // 业务方法代理（兼容性）
  async enterDrcMode() { return this.controller.enterDrcMode(); }
  async exitDrcMode() { return this.controller.exitDrcMode(); }
  getDrcDuration() { return this.controller.getDrcDuration(); }
}

// 保持现有导出方式
export const drcModeCardUI = new DrcModeCardUI();