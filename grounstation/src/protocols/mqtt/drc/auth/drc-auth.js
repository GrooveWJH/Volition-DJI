/**
 * DRC认证管理器
 * 处理DRC授权请求和认证流程
 */

import { DrcTimeouts } from '../workflow/drc-enums.js';
import { globalEventManager } from '../../../shared/utils/event-manager.js';

export class DrcAuthManager {
  constructor() {
    this.authToken = null;
    this.authStartTime = null;
    this.isAuthInProgress = false;
  }

  /**
   * 模拟授权请求
   * @param {string} serialNumber - 设备序列号
   * @returns {Promise<Object>} 授权结果
   */
  async simulateAuthRequest(serialNumber) {
    this.isAuthInProgress = true;
    this.authStartTime = Date.now();
    
    // 模拟网络请求延迟
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // 模拟授权成功
    this.authToken = `auth_${serialNumber}_${Date.now()}`;
    
    globalEventManager.emit('drc:log', {
      type: '信息',
      message: `设备 ${serialNumber} 授权请求已发送`
    });
    
    return {
      success: true,
      token: this.authToken,
      requiresManualConfirm: true
    };
  }

  /**
   * 确认授权
   * @returns {Object} 确认结果
   */
  confirmAuth() {
    if (!this.authToken) {
      return { success: false, error: '没有待确认的授权' };
    }

    globalEventManager.emit('drc:log', {
      type: '成功',
      message: '授权已确认，准备进入DRC模式'
    });

    return { success: true, token: this.authToken };
  }

  /**
   * 检查授权是否超时
   * @returns {boolean} 是否超时
   */
  isAuthTimeout() {
    if (!this.authStartTime) return false;
    return Date.now() - this.authStartTime > DrcTimeouts.MANUAL_CONFIRM;
  }

  /**
   * 重置授权状态
   */
  resetAuth() {
    this.authToken = null;
    this.authStartTime = null;
    this.isAuthInProgress = false;
  }

  /**
   * 获取授权状态
   * @returns {Object} 授权状态信息
   */
  getAuthStatus() {
    return {
      hasToken: !!this.authToken,
      inProgress: this.isAuthInProgress,
      isTimeout: this.isAuthTimeout(),
      startTime: this.authStartTime
    };
  }
}

// 全局认证管理器实例
export const drcAuthManager = new DrcAuthManager();