/**
 * DRC状态管理器
 * 管理DRC工作流程状态和步骤转换
 */

import { DrcWorkflowSteps, DrcStatus } from '../workflow/drc-enums.js';
import { globalEventManager } from '@/shared/utils/event-manager.js';

export class DrcStatusManager {
  constructor() {
    this.currentStep = DrcWorkflowSteps.IDLE;
    this.status = DrcStatus.INACTIVE;
    this.stepHistory = [];
    this.errorInfo = null;
  }

  /**
   * 设置工作流步骤
   * @param {string} newStep - 新步骤
   */
  setStep(newStep) {
    const oldStep = this.currentStep;
    this.currentStep = newStep;
    this.stepHistory.push({
      step: newStep,
      timestamp: Date.now(),
      previous: oldStep
    });

    globalEventManager.emit('drc:step-changed', {
      oldStep,
      newStep,
      history: this.stepHistory
    });

    this.logStep('步骤', `${oldStep} → ${newStep}`);
  }

  /**
   * 设置状态
   * @param {string} newStatus - 新状态
   */
  setStatus(newStatus) {
    const oldStatus = this.status;
    this.status = newStatus;

    globalEventManager.emit('drc:status-changed', {
      oldStatus,
      newStatus
    });

    this.logStep('状态', `${oldStatus} → ${newStatus}`);
  }

  /**
   * 设置错误状态
   * @param {string} title - 错误标题
   * @param {string} message - 错误消息
   */
  setError(title, message) {
    this.errorInfo = { title, message, timestamp: Date.now() };
    this.setStep(DrcWorkflowSteps.ERROR);
    this.setStatus(DrcStatus.ERROR);

    globalEventManager.emit('drc:error', {
      title,
      message,
      timestamp: this.errorInfo.timestamp
    });

    this.logStep('错误', `${title}: ${message}`);
  }

  /**
   * 清除错误状态
   */
  clearError() {
    this.errorInfo = null;
    this.setStep(DrcWorkflowSteps.IDLE);
    this.setStatus(DrcStatus.INACTIVE);
  }

  /**
   * 记录步骤日志
   * @param {string} type - 日志类型
   * @param {string} message - 日志消息
   */
  logStep(type, message) {
    globalEventManager.emit('drc:log', { type, message });
  }

  /**
   * 获取状态信息
   * @returns {Object} 状态信息
   */
  getStatusInfo() {
    return {
      currentStep: this.currentStep,
      status: this.status,
      canCancel: this.canCancel(),
      canConfirm: this.canConfirm(),
      isActive: this.isActive(),
      hasError: !!this.errorInfo,
      errorInfo: this.errorInfo,
      stepHistory: this.stepHistory
    };
  }

  /**
   * 检查是否可以取消
   * @returns {boolean} 是否可以取消
   */
  canCancel() {
    return [
      DrcWorkflowSteps.AUTH_REQUEST,
      DrcWorkflowSteps.AUTH_PENDING,
      DrcWorkflowSteps.ENTERING_DRC
    ].includes(this.currentStep);
  }

  /**
   * 检查是否可以确认
   * @returns {boolean} 是否可以确认
   */
  canConfirm() {
    return this.currentStep === DrcWorkflowSteps.AUTH_PENDING;
  }

  /**
   * 检查DRC是否激活
   * @returns {boolean} DRC是否激活
   */
  isActive() {
    return this.currentStep === DrcWorkflowSteps.DRC_ACTIVE;
  }

  /**
   * 重置状态管理器
   */
  reset() {
    this.currentStep = DrcWorkflowSteps.IDLE;
    this.status = DrcStatus.INACTIVE;
    this.stepHistory = [];
    this.errorInfo = null;
  }
}

// 全局状态管理器实例
export const drcStatusManager = new DrcStatusManager();
