/**
 * DRC控制卡片UI交互逻辑
 * 处理DRC工作流程的用户界面交互
 */

import { defaultDrcController } from './drc-controller.js';
import { DrcWorkflowManager, createStepProgressHTML } from '@/cards/DrcControlCard/workflow/drc-workflow.js';
import { globalEventManager } from '@/shared/utils/event-manager.js';
import { globalStorage } from '@/shared/core/storage.js';

export class DrcControlCardUI {
  constructor() {
    this.controller = defaultDrcController;
    this.workflowManager = new DrcWorkflowManager();
    this.elements = {};
    this.init();
  }

  init() {
    this.bindElements();
    this.bindEvents();
    this.loadStoredConfig();
    this.setupEventListeners();
    this.setupDeviceContextListener();
    this.controller.init(this.getConfigFromInputs());
    this.updateUI();
  }

  bindElements() {
    this.elements = {
      serialInput: document.querySelector('[data-config="device-serial"]'),
      timeoutInput: document.querySelector('[data-config="timeout"]'),
      retriesInput: document.querySelector('[data-config="retries"]'),
      startBtn: document.getElementById('start-drc-btn'),
      cancelBtn: document.getElementById('cancel-drc-btn'),
      confirmBtn: document.getElementById('confirm-auth-btn'),
      exitBtn: document.getElementById('exit-drc-btn'),
      clearLogsBtn: document.getElementById('clear-drc-logs-btn'),
      workflowProgress: document.getElementById('workflow-progress'),
      currentStatus: document.getElementById('current-status'),
      deviceConnection: document.getElementById('device-connection'),
      authStatus: document.getElementById('auth-status'),
      logs: document.getElementById('drc-logs')
    };
  }

  bindEvents() {
    ['serialInput', 'timeoutInput', 'retriesInput'].forEach(key => {
      this.elements[key]?.addEventListener('input', () => this.updateConfig());
    });

    this.elements.startBtn?.addEventListener('click', () => this.startDrcFlow());
    this.elements.cancelBtn?.addEventListener('click', () => this.cancelOperation());
    this.elements.confirmBtn?.addEventListener('click', () => this.confirmAuth());
    this.elements.exitBtn?.addEventListener('click', () => this.exitDrc());
    this.elements.clearLogsBtn?.addEventListener('click', () => this.clearLogs());
  }

  setupEventListeners() {
    globalEventManager.on('drc:step-changed', (data) => {
      this.updateWorkflowProgress(data.newStep);
      this.updateButtonStates(data.newStep);
    });

    globalEventManager.on('drc:status-changed', (data) => {
      this.updateStatusDisplay(data.newStatus);
    });

    globalEventManager.on('drc:log', (logEntry) => {
      this.addLog(logEntry.type, logEntry.message);
    });

    globalEventManager.on('drc:error', (error) => {
      this.addLog('错误', error.message);
    });
  }

  setupDeviceContextListener() {
    // 监听设备切换事件，更新设备序列号输入框
    if (typeof window !== 'undefined') {
      window.addEventListener('device-context-changed', (event) => {
        const newDeviceSN = event.detail?.newDevice;
        if (this.elements.serialInput) {
          this.elements.serialInput.value = newDeviceSN || '';
          this.updateConfig();
        }
      });

      // 初始化时设置当前设备
      import('@/shared/core/device-context.js').then(({ default: deviceContext }) => {
        const currentDevice = deviceContext.getCurrentDevice();
        if (currentDevice && this.elements.serialInput) {
          this.elements.serialInput.value = currentDevice;
        }
      });
    }
  }

  loadStoredConfig() {
    const inputs = [this.elements.serialInput, this.elements.timeoutInput, this.elements.retriesInput];
    inputs.forEach(input => {
      if (input && input.dataset.storageKey) {
        const stored = globalStorage.getValue(globalStorage.getStorageKey(input.dataset.storageKey));
        if (stored) input.value = stored;
      }
    });
  }

  getConfigFromInputs() {
    return {
      serialNumber: this.elements.serialInput?.value || '',
      timeoutMs: (parseInt(this.elements.timeoutInput?.value) || 30) * 1000,
      retryCount: parseInt(this.elements.retriesInput?.value) || 3
    };
  }

  updateConfig() {
    const config = this.getConfigFromInputs();
    this.controller.updateConfig(config);
    
    globalStorage.saveValue(globalStorage.getStorageKey('drc-device-serial'), config.serialNumber);
    globalStorage.saveValue(globalStorage.getStorageKey('drc-timeout'), config.timeoutMs / 1000);
    globalStorage.saveValue(globalStorage.getStorageKey('drc-retries'), config.retryCount);
  }

  async startDrcFlow() {
    this.addLog('信息', '开始DRC授权流程...');
    await this.controller.startDrcAuthorization();
  }

  cancelOperation() {
    this.controller.cancelOperation();
  }

  confirmAuth() {
    globalEventManager.emit('drc:manual-confirm');
  }

  async exitDrc() {
    await this.controller.exitDrcMode();
  }

  updateWorkflowProgress(currentStep) {
    if (this.elements.workflowProgress) {
      this.elements.workflowProgress.innerHTML = createStepProgressHTML(currentStep);
    }
  }

  updateButtonStates(currentStep) {
    const status = this.controller.getStatusInfo();
    
    // 显示/隐藏按钮
    this.elements.startBtn?.classList.toggle('hidden', currentStep !== 'idle');
    this.elements.cancelBtn?.classList.toggle('hidden', !status.canCancel);
    this.elements.confirmBtn?.classList.toggle('hidden', !status.canConfirm);
    this.elements.exitBtn?.classList.toggle('hidden', !status.isActive);
  }

  updateStatusDisplay(status) {
    const statusText = {
      'inactive': '待机',
      'requesting': '请求中',
      'pending': '等待确认',
      'active': '已激活',
      'error': '错误'
    };

    if (this.elements.currentStatus) {
      this.elements.currentStatus.textContent = statusText[status] || status;
    }
  }

  updateUI() {
    const status = this.controller.getStatusInfo();
    this.updateWorkflowProgress(status.currentStep);
    this.updateButtonStates(status.currentStep);
    this.updateStatusDisplay(status.status);
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
export const drcControlCardUI = new DrcControlCardUI();
