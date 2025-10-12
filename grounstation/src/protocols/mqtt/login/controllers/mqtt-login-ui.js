/**
 * MQTT登录卡片UI交互逻辑
 * 处理用户界面交互和事件管理
 */

import { defaultMqttLoginController } from './mqtt-login-controller.js';
import { globalEventManager } from '../../../../shared/utils/event-manager.js';
import { globalStorage } from '../../../../shared/core/storage.js';

export class MqttLoginCardUI {
  constructor() {
    this.controller = defaultMqttLoginController;
    this.elements = {};
    this.init();
  }

  init() {
    this.bindElements();
    this.bindEvents();
    this.loadStoredConfig();
    this.setupEventListeners();
    this.controller.init(this.getConfigFromInputs());
  }

  bindElements() {
    this.elements = {
      hostInput: document.querySelector('[data-config="mqtt-host"]'),
      portInput: document.querySelector('[data-config="mqtt-port"]'),
      usernameInput: document.querySelector('[data-config="mqtt-username"]'),
      passwordInput: document.querySelector('[data-config="mqtt-password"]'),
      generateBtn: document.getElementById('generate-login-page-btn'),
      testBtn: document.getElementById('test-connection-btn'),
      previewBtn: document.getElementById('preview-page-btn'),
      downloadBtn: document.getElementById('download-page-btn'),
      clearLogsBtn: document.getElementById('clear-logs-btn'),
      pageInfo: document.getElementById('generated-page-info'),
      generationTime: document.getElementById('generation-time'),
      mqttStatus: document.getElementById('mqtt-status'),
      logs: document.getElementById('mqtt-logs')
    };
  }

  bindEvents() {
    ['hostInput', 'portInput', 'usernameInput', 'passwordInput'].forEach(key => {
      this.elements[key]?.addEventListener('input', () => this.updateConfig());
    });

    this.elements.generateBtn?.addEventListener('click', () => this.generateLoginPage());
    this.elements.testBtn?.addEventListener('click', () => this.testConnection());
    this.elements.previewBtn?.addEventListener('click', () => this.previewPage());
    this.elements.downloadBtn?.addEventListener('click', () => this.downloadPage());
    this.elements.clearLogsBtn?.addEventListener('click', () => this.clearLogs());
  }

  setupEventListeners() {
    globalEventManager.on('login:generated', (data) => {
      this.showPageInfo();
      this.addLog('成功', `登录页面已生成: ${data.config.host}:${data.config.port}`);
    });

    globalEventManager.on('login:error', (error) => {
      this.addLog('错误', `生成失败: ${error.message || '未知错误'}`);
    });

    globalEventManager.on('connection:testing', () => {
      this.updateConnectionStatus('testing', '测试中...');
      this.addLog('信息', '正在测试MQTT连接...');
    });

    globalEventManager.on('connection:success', () => {
      this.updateConnectionStatus('success', '连接成功');
      this.addLog('成功', 'MQTT连接测试成功');
    });

    globalEventManager.on('connection:failed', () => {
      this.updateConnectionStatus('failed', '连接失败');
      this.addLog('错误', 'MQTT连接测试失败');
    });
  }

  loadStoredConfig() {
    const inputs = [this.elements.hostInput, this.elements.portInput, 
                   this.elements.usernameInput, this.elements.passwordInput];
    
    inputs.forEach(input => {
      if (input && input.dataset.storageKey) {
        const stored = globalStorage.getValue(input.dataset.storageKey);
        if (stored) input.value = stored;
      }
    });
  }

  getConfigFromInputs() {
    return {
      host: this.elements.hostInput?.value || '',
      port: this.elements.portInput?.value || '',
      username: this.elements.usernameInput?.value || '',
      password: this.elements.passwordInput?.value || ''
    };
  }

  updateConfig() {
    const config = this.getConfigFromInputs();
    this.controller.updateConfig(config);
    
    globalStorage.saveValue('mqtt-host', config.host);
    globalStorage.saveValue('mqtt-port', config.port);
    globalStorage.saveValue('mqtt-username', config.username);
    globalStorage.saveValue('mqtt-password', config.password);
  }

  generateLoginPage() {
    this.addLog('信息', '开始生成登录页面...');
    this.controller.generateLoginPage();
  }

  async testConnection() {
    await this.controller.testConnection();
  }

  previewPage() {
    const status = this.controller.getStatus();
    if (status.blobUrl) {
      window.open(status.blobUrl, '_blank');
      this.addLog('信息', '已在新窗口打开预览页面');
    } else {
      this.addLog('警告', '没有可预览的页面，请先生成登录页面');
    }
  }

  downloadPage() {
    const status = this.controller.getStatus();
    if (status.blobUrl) {
      const a = document.createElement('a');
      a.href = status.blobUrl;
      a.download = `dji-login-${Date.now()}.html`;
      a.click();
      this.addLog('信息', '登录页面已下载');
    } else {
      this.addLog('警告', '没有可下载的页面，请先生成登录页面');
    }
  }

  showPageInfo() {
    this.elements.pageInfo?.classList.remove('hidden');
    if (this.elements.generationTime) {
      this.elements.generationTime.textContent = new Date().toLocaleString();
    }
  }

  updateConnectionStatus(type, message) {
    if (this.elements.mqttStatus) {
      this.elements.mqttStatus.textContent = message;
      this.elements.mqttStatus.className = type === 'success' ? 'text-green-600' : 
                                         type === 'failed' ? 'text-red-600' : 'text-yellow-600';
    }
  }

  addLog(type, message) {
    const timestamp = new Date().toLocaleTimeString();
    const logClass = type === '成功' ? 'text-green-400' : 
                    type === '错误' ? 'text-red-400' : 
                    type === '警告' ? 'text-yellow-400' : 'text-blue-400';
    
    const logEntry = `<div class="${logClass}">[${timestamp}] [${type}] ${message}</div>`;
    
    if (this.elements.logs) {
      this.elements.logs.innerHTML += logEntry;
      this.elements.logs.scrollTop = this.elements.logs.scrollHeight;
    }
  }

  clearLogs() {
    if (this.elements.logs) {
      this.elements.logs.innerHTML = '<div class="text-gray-500">[系统] 日志已清空</div>';
    }
  }
}

// 全局实例
export const mqttLoginCardUI = new MqttLoginCardUI();