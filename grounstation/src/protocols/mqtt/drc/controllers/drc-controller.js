/**
 * DRC控制器（简化版）
 * 协调DRC各个模块的操作流程
 */

import { DrcWorkflowSteps, DrcStatus } from '../workflow/drc-enums.js';
import { drcConfigManager } from '../config/drc-config.js';
import { drcAuthManager } from '../auth/drc-auth.js';
import { drcStatusManager } from '../status/drc-status.js';
import { globalEventManager } from '../../../shared/utils/event-manager.js';

/**
 * DRC控制器类
 */
export class DrcController {
  constructor() {
    this.configManager = drcConfigManager;
    this.authManager = drcAuthManager;
    this.statusManager = drcStatusManager;
    this.retryAttempts = 0;
  }

  /**
   * 初始化控制器
   * @param {Object} initialConfig - 初始配置
   */
  init(initialConfig = {}) {
    this.configManager.updateConfig(initialConfig);
    this.setupEventListeners();
    this.statusManager.logStep('系统', 'DRC控制器已初始化');
  }

  /**
   * 设置事件监听器
   */
  setupEventListeners() {
    globalEventManager.on('config:drc-updated', (newConfig) => {
      this.configManager.updateConfig(newConfig);
    });

    globalEventManager.on('drc:manual-confirm', () => {
      this.handleManualConfirmation();
    });

    globalEventManager.on('drc:cancel', () => {
      this.cancelOperation();
    });
  }

  /**
   * 更新配置
   * @param {Object} newConfig - 新配置
   */
  updateConfig(newConfig) {
    this.configManager.updateConfig(newConfig);
  }

  /**
   * 开始DRC授权流程
   * @returns {Promise<Object>} 操作结果
   */
  async startDrcAuthorization() {
    try {
      // 验证配置
      const validation = this.configManager.validateConfig();
      if (!validation.isValid) {
        this.statusManager.setError('配置验证失败', validation.errors);
        return { success: false, errors: validation.errors };
      }

      this.statusManager.setStep(DrcWorkflowSteps.AUTH_REQUEST);
      this.statusManager.setStatus(DrcStatus.REQUESTING);
      
      this.statusManager.logStep('请求', '开始DRC授权请求...');
      
      const config = this.configManager.getConfig();
      const authResult = await this.authManager.simulateAuthRequest(config.serialNumber);
      
      if (authResult.success) {
        this.statusManager.setStep(DrcWorkflowSteps.AUTH_PENDING);
        this.statusManager.setStatus(DrcStatus.PENDING);
        this.statusManager.logStep('等待', '等待手动确认授权...');
      }
      
      return { success: true, step: this.statusManager.currentStep };
      
    } catch (error) {
      this.statusManager.setError('授权请求失败', error.message);
      return { success: false, error: error.message };
    }
  }

  /**
   * 处理手动确认
   */
  handleManualConfirmation() {
    if (this.statusManager.currentStep !== DrcWorkflowSteps.AUTH_PENDING) {
      this.statusManager.logStep('警告', '当前状态不允许确认操作');
      return;
    }

    const confirmResult = this.authManager.confirmAuth();
    if (confirmResult.success) {
      this.statusManager.setStep(DrcWorkflowSteps.AUTH_CONFIRMED);
      this.statusManager.logStep('确认', '用户已确认授权');
      
      // 自动进入DRC模式
      setTimeout(() => {
        this.enterDrcMode();
      }, 1000);
    }
  }

  /**
   * 进入DRC模式
   */
  async enterDrcMode() {
    try {
      this.statusManager.setStep(DrcWorkflowSteps.ENTERING_DRC);
      this.statusManager.logStep('进入', '正在进入DRC模式...');
      
      // 模拟进入DRC模式
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      this.statusManager.setStep(DrcWorkflowSteps.DRC_ACTIVE);
      this.statusManager.setStatus(DrcStatus.ACTIVE);
      this.statusManager.logStep('成功', 'DRC模式已激活');
      
    } catch (error) {
      this.statusManager.setError('进入DRC失败', error.message);
    }
  }

  /**
   * 退出DRC模式
   */
  async exitDrcMode() {
    try {
      this.statusManager.setStep(DrcWorkflowSteps.EXITING_DRC);
      this.statusManager.logStep('退出', '正在退出DRC模式...');
      
      // 模拟退出DRC模式
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      this.statusManager.setStep(DrcWorkflowSteps.IDLE);
      this.statusManager.setStatus(DrcStatus.INACTIVE);
      this.statusManager.logStep('完成', 'DRC模式已退出');
      
      this.authManager.resetAuth();
      
    } catch (error) {
      this.statusManager.setError('退出DRC失败', error.message);
    }
  }

  /**
   * 取消操作
   */
  cancelOperation() {
    this.statusManager.logStep('取消', '用户取消操作');
    this.statusManager.setStep(DrcWorkflowSteps.IDLE);
    this.statusManager.setStatus(DrcStatus.INACTIVE);
    this.authManager.resetAuth();
  }

  /**
   * 获取状态信息
   * @returns {Object} 状态信息
   */
  getStatusInfo() {
    return this.statusManager.getStatusInfo();
  }
}

// 全局DRC控制器实例
export const defaultDrcController = new DrcController();