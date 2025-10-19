/**
 * 云端控制授权控制器
 * 负责请求和释放无人机云端飞行控制权
 */

import { deviceContext, cardStateManager } from '#lib/state.js';
import { topicServiceManager, messageRouter } from '#lib/services.js';
import { AuthStateManager } from './auth-state-manager.js';
import { ErrorHandler } from './error-handler.js';
import { LogManager } from './log-manager.js';
import { UIUpdater } from './ui-updater.js';
import debugLogger from '#lib/debug.js';

export class CloudControlCardUI {
  constructor() {
    this.elements = {};

    // 初始化模块
    this.authStateManager = new AuthStateManager();
    this.logManager = new LogManager();
    this.errorHandler = new ErrorHandler(this.logManager);
    this.uiUpdater = new UIUpdater();

    // 状态属性（将被代理管理）
    this.authStatus = 'unauthorized';
    this.controlKeys = [];
    this.logsHTML = '<div class="text-gray-500" data-log-type="系统">[系统] 云端控制授权卡片已初始化</div>';
    this.userId = 'cloud_user_001';
    this.userCallsign = 'CloudPilot';
    this.authStartTime = null;
    this.authTimeout = null;
    this.currentRequestTid = null;
    this.authorizedAt = null;
    this.authorizedUser = null;

    this.init();

    // 注册到状态管理器
    return cardStateManager.register(this, 'cloudControl', {
      debug: true
    });
  }

  init() {
    // 加载用户配置
    this.authStateManager.loadUserConfig();
    this.userId = this.authStateManager.userId;
    this.userCallsign = this.authStateManager.userCallsign;

    // 只在浏览器环境初始化DOM相关功能
    if (typeof document !== 'undefined') {
      this.bindElements();
      this.bindEvents();
      this.setupDeviceContextListener();
      this.setupMqttListener();
      this.setupStateRestoreListener();
      this.updateUI();
    }
  }

  bindElements() {
    this.elements = {
      userIdInput: document.querySelector('[data-config="user-id"]'),
      userCallsignInput: document.querySelector('[data-config="user-callsign"]'),
      requestBtn: document.getElementById('request-auth-btn'),
      requestBtnSpinner: document.getElementById('request-btn-spinner'),
      requestBtnIcon: document.getElementById('request-btn-icon'),
      requestBtnText: document.getElementById('request-btn-text'),
      confirmBtn: document.getElementById('confirm-auth-btn'),
      clearLogsBtn: document.getElementById('clear-cloud-logs-btn'),
      logFilter: document.getElementById('log-filter'),
      cloudStatus: document.getElementById('cloud-status'),
      statusText: document.querySelector('#cloud-status .status-text'),
      statusSpinner: document.getElementById('status-spinner'),
      controlKeysDisplay: document.getElementById('control-keys'),
      mqttStatus: document.getElementById('mqtt-status'),
      logs: document.getElementById('cloud-logs')
    };

    // 设置模块元素引用
    this.logManager.setElements(this.elements);
    this.uiUpdater.setElements(this.elements);
  }

  bindEvents() {
    this.elements.userIdInput?.addEventListener('input', (e) => {
      this.userId = e.target.value;
      this.authStateManager.updateUserConfig(this.userId, this.userCallsign);
    });

    this.elements.userCallsignInput?.addEventListener('input', (e) => {
      this.userCallsign = e.target.value;
      this.authStateManager.updateUserConfig(this.userId, this.userCallsign);
    });

    this.elements.requestBtn?.addEventListener('click', () => this.requestAuth());
    this.elements.confirmBtn?.addEventListener('click', () => this.confirmAuth());
    this.elements.clearLogsBtn?.addEventListener('click', () => this.logManager.clearLogs());
    this.elements.logFilter?.addEventListener('change', (e) => this.logManager.filterLogs(e.target.value));
  }

  setupDeviceContextListener() {
    if (typeof window !== 'undefined') {
      window.addEventListener('device-changed', (event) => {
        this.uiUpdater.updateMqttStatus();
      });
    }
  }

  setupMqttListener() {
    if (typeof window !== 'undefined') {
      // 监听MQTT连接状态变化
      window.addEventListener('mqtt-connection-changed', (event) => {
        this.uiUpdater.updateMqttStatus();
        this.handleMqttConnectionChange(event.detail);
      });

      // 使用MessageRouter注册服务回复处理
      this.registerServiceHandlers();
    }
  }

  /**
   * 处理MQTT连接状态变化
   */
  handleMqttConnectionChange(connectionInfo) {
    const result = this.errorHandler.handleMqttConnectionChange(connectionInfo, this.authStateManager);
    if (result.shouldUpdateUI) {
      this.syncFromAuthState();
      this.updateUI();
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

    this.logManager.addLog('信息', '已注册云端控制服务消息处理器');
  }

  setupStateRestoreListener() {
    if (typeof window !== 'undefined') {
      window.addEventListener('card-state-restored', () => {
        console.log('[CloudControlCard] 状态已恢复，更新UI');
        this.syncToAuthState();
        this.updateUI();
        this.logManager.restoreLogsFromState();
        this.uiUpdater.restoreInputsFromState(this.authStateManager);
      });
    }
  }

  /**
   * 同步状态到AuthStateManager
   */
  syncToAuthState() {
    this.authStateManager.authStatus = this.authStatus;
    this.authStateManager.controlKeys = this.controlKeys;
    this.authStateManager.userId = this.userId;
    this.authStateManager.userCallsign = this.userCallsign;
    this.authStateManager.authStartTime = this.authStartTime;
    this.authStateManager.currentRequestTid = this.currentRequestTid;
    this.authStateManager.authorizedAt = this.authorizedAt;
    this.authStateManager.authorizedUser = this.authorizedUser;
  }

  /**
   * 从AuthStateManager同步状态
   */
  syncFromAuthState() {
    this.authStatus = this.authStateManager.authStatus;
    this.controlKeys = this.authStateManager.controlKeys;
    this.userId = this.authStateManager.userId;
    this.userCallsign = this.authStateManager.userCallsign;
    this.authStartTime = this.authStateManager.authStartTime;
    this.currentRequestTid = this.authStateManager.currentRequestTid;
    this.authorizedAt = this.authStateManager.authorizedAt;
    this.authorizedUser = this.authStateManager.authorizedUser;
  }

  /**
   * 请求云端控制授权
   */
  async requestAuth() {
    this.logManager.addLog('信息', '▶ 按钮被点击，开始处理授权请求...');
    this.logAuthProgress('request.start', '收到请求授权指令');

    const currentSN = deviceContext.getCurrentDevice();
    this.logAuthProgress('request.deviceContext', `当前设备SN: ${currentSN || '未选择'}`);

    // 验证授权请求参数
    const validation = this.errorHandler.validateAuthRequest(this.userId, this.userCallsign, currentSN);
    if (!validation.isValid) {
      const connectionInfo = (typeof window !== 'undefined' && currentSN)
        ? window.mqttManager?.getConnection(currentSN)
        : null;
      this.logAuthProgress(
        'request.validation_context',
        JSON.stringify({
          userId: this.userId,
          userCallsign: this.userCallsign,
          deviceSN: currentSN,
          connectionFound: !!connectionInfo,
          connectionState: connectionInfo ? connectionInfo.isConnected : null
        })
      );
      this.logAuthProgress('request.validation_failed', validation.errors.map(error => error.type).join(', ') || '未知错误');
      validation.errors.forEach(error => {
        this.logManager.addLog('错误', error.message);
        this.errorHandler.showErrorAdvice(error.type);
      });
      return;
    }
    this.logAuthProgress('request.validation_passed', `用户: ${this.userCallsign}, 控制权: flight`);

    // 防止重复请求
    if (this.authStatus === 'requesting') {
      this.logManager.addLog('警告', '授权请求进行中，请勿重复发送');
      this.logAuthProgress('request.duplicate', '检测到重复点击，已阻止');
      return;
    }

    this.logManager.addLog('信息', `发送授权请求 (设备: ${currentSN})`);
    this.logAuthProgress('request.prepare_state', '状态管理器开始记录请求');
    this.authStateManager.startAuthRequest(null);
    this.authStateManager.setAuthTimeout(30000, () => {
      this.logManager.addLog('警告', '授权请求超时，已自动取消');
      this.syncFromAuthState();
      this.updateUI();
      this.errorHandler.showErrorAdvice('timeout');
    });

    this.syncFromAuthState();
    this.updateUI();
    this.logAuthProgress('request.ui_synced', 'UI已切换到请求中状态');

    try {
      const requestData = {
        user_id: this.userId,
        user_callsign: this.userCallsign,
        control_keys: ['flight']
      };

      this.logAuthProgress('request.service_call', `调用服务 cloud_control_auth_request: ${JSON.stringify(requestData)}`);
      const result = await topicServiceManager.callService(currentSN, 'cloud_control_auth_request', requestData);
      this.logAuthProgress('request.service_reply', `收到服务返回: ${result.success ? 'success' : result.error?.type || 'unknown'}`);

      if (result.success) {
        this.authStateManager.currentRequestTid = result.data?.tid;
        this.logManager.addLog('成功', `已发送授权请求 (用户: ${this.userCallsign})`);
        this.logManager.addLog('调试', `TID: ${result.data?.tid || 'N/A'}`);
        this.logAuthProgress('request.wait_for_reply', `已记录TID: ${result.data?.tid || 'N/A'}`);
      } else {
        this.errorHandler.handleServiceError(null, result);
        this.authStateManager.resetAuth();
        this.syncFromAuthState();
        this.updateUI();
        this.logAuthProgress('request.service_error', result.error?.message || '未知错误');
      }
    } catch (error) {
      this.errorHandler.handleServiceError(error, null);
      this.authStateManager.resetAuth();
      this.syncFromAuthState();
      this.updateUI();
      this.logAuthProgress('request.exception', error.message || String(error));
    }
  }

  /**
   * 手动确认授权已在遥控器上完成
   */
  confirmAuth() {
    this.authStateManager.setAuthorized();
    const authDuration = this.authStateManager.getAuthDuration();
    this.logManager.addLog('成功', '✓ 已手动确认云端控制授权');
    this.logManager.addLog('信息', `授权用户: ${this.userCallsign} (耗时: ${authDuration}秒)`);
    this.logManager.addLog('信息', '现在可以使用云端控制功能');
    this.syncFromAuthState();
    this.updateUI();
  }

  /**
   * 处理授权请求回复
   */
  handleAuthRequestReply(msg) {
    const result = this.errorHandler.handleAuthReply(msg, this.authStateManager);
    if (result.shouldUpdateUI) {
      this.syncFromAuthState();
      this.updateUI();
    }
  }

  /**
   * 更新UI显示
   */
  updateUI() {
    this.syncToAuthState();
    this.uiUpdater.updateUI(this.authStateManager);

    // 发出全局状态变化事件，通知其他组件
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('cloud-control-status-changed', {
        detail: {
          authStatus: this.authStatus,
          controlKeys: this.controlKeys,
          authorizedUser: this.authorizedUser
        }
      }));
    }
  }

  /**
   * 添加日志
   */
  addLog(type, message) {
    this.logManager.addLog(type, message);
    this.logsHTML = this.logManager.getLogsHTML();
  }

  /**
   * 记录授权流程的详细阶段
   */
  logAuthProgress(stage, detail) {
    this.logManager.addLog('调试', `[AUTH][${stage}] ${detail}`);
  }
}

// 全局实例
export const cloudControlCardUI = new CloudControlCardUI();
