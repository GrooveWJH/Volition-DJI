/**
 * 云端控制授权状态管理器
 * 负责管理授权状态、超时、会话信息等
 */

import debugLogger from '#lib/debug.js';

export class AuthStateManager {
  constructor() {
    // 状态属性
    this.authStatus = 'unauthorized';  // unauthorized, requesting, authorized
    this.controlKeys = [];
    this.userId = 'cloud_user_001';
    this.userCallsign = 'CloudPilot';

    // 授权会话信息
    this.authStartTime = null;
    this.authTimeout = null;
    this.currentRequestTid = null;
    this.authorizedAt = null;
    this.authorizedUser = null;
  }

  /**
   * 设置授权超时定时器
   */
  setAuthTimeout(timeoutMs = 30000, onTimeout) {
    this.clearAuthTimeout();
    this.authTimeout = setTimeout(() => {
      if (this.authStatus === 'requesting') {
        this.authStatus = 'unauthorized';
        this.currentRequestTid = null;
        this.authStartTime = null;
        if (onTimeout) onTimeout();
      }
    }, timeoutMs);
  }

  /**
   * 清除授权超时定时器
   */
  clearAuthTimeout() {
    if (this.authTimeout) {
      clearTimeout(this.authTimeout);
      this.authTimeout = null;
    }
  }

  /**
   * 开始授权请求
   */
  startAuthRequest(tid) {
    this.authStatus = 'requesting';
    this.authStartTime = Date.now();
    this.currentRequestTid = tid;
  }

  /**
   * 授权成功
   */
  setAuthorized() {
    this.clearAuthTimeout();
    this.authStatus = 'authorized';
    this.controlKeys = ['flight'];
    this.authorizedAt = Date.now();
    this.authorizedUser = this.userCallsign;
  }

  /**
   * 重置授权状态
   */
  resetAuth() {
    this.clearAuthTimeout();
    this.authStatus = 'unauthorized';
    this.controlKeys = [];
    this.currentRequestTid = null;
    this.authorizedAt = null;
    this.authorizedUser = null;
    this.authStartTime = null;
  }

  /**
   * 获取授权持续时间（秒）
   */
  getAuthDuration() {
    if (!this.authStartTime) return 0;
    return Math.round((Date.now() - this.authStartTime) / 1000);
  }

  /**
   * 获取授权会话信息
   */
  getSessionInfo() {
    if (this.authStatus === 'authorized' && this.authorizedAt) {
      const duration = Math.round((Date.now() - this.authorizedAt) / 1000);
      return {
        user: this.authorizedUser,
        authorizedAt: this.authorizedAt,
        duration: duration,
        controlKeys: this.controlKeys
      };
    }
    return null;
  }

  /**
   * 验证TID是否匹配当前请求
   */
  isValidTid(tid) {
    return this.currentRequestTid === tid;
  }

  /**
   * 保存用户配置到localStorage
   */
  saveUserConfig() {
    if (typeof window !== 'undefined') {
      const config = {
        userId: this.userId,
        userCallsign: this.userCallsign,
        lastSaved: Date.now()
      };
      localStorage.setItem('cloud_control_user_config', JSON.stringify(config));
    }
  }

  /**
   * 加载用户配置从localStorage
   */
  loadUserConfig() {
    if (typeof window !== 'undefined') {
      try {
        const configStr = localStorage.getItem('cloud_control_user_config');
        if (configStr) {
          const config = JSON.parse(configStr);
          this.userId = config.userId || 'cloud_user_001';
          this.userCallsign = config.userCallsign || 'CloudPilot';
          return true;
        }
      } catch (error) {
        debugLogger.warn('加载用户配置失败', { error: error.message });
      }
    }
    return false;
  }

  /**
   * 更新用户配置
   */
  updateUserConfig(userId, userCallsign) {
    this.userId = userId;
    this.userCallsign = userCallsign;
    this.saveUserConfig();
  }

  /**
   * 获取当前状态摘要
   */
  getStatusSummary() {
    return {
      authStatus: this.authStatus,
      controlKeys: this.controlKeys,
      userId: this.userId,
      userCallsign: this.userCallsign,
      sessionInfo: this.getSessionInfo(),
      hasActiveRequest: !!this.currentRequestTid
    };
  }
}