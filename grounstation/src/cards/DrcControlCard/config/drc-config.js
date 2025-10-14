/**
 * DRC配置管理器
 * 处理DRC相关配置的验证和管理
 */

import { quickValidate } from '@/shared/utils/validation.js';
import { globalEventManager } from '@/shared/utils/event-manager.js';

export class DrcConfigManager {
  constructor() {
    this.config = {
      serialNumber: '',
      timeoutMs: 30000,
      retryCount: 3
    };
  }

  /**
   * 更新配置
   * @param {Object} newConfig - 新配置
   */
  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
    globalEventManager.emit('drc:config-updated', this.config);
  }

  /**
   * 获取当前配置
   * @returns {Object} 当前配置
   */
  getConfig() {
    return { ...this.config };
  }

  /**
   * 验证配置
   * @returns {Object} 验证结果
   */
  validateConfig() {
    const serialResult = quickValidate.serialNumber(this.config.serialNumber);
    return {
      isValid: serialResult.valid,
      errors: serialResult.valid ? [] : [serialResult]
    };
  }

  /**
   * 获取验证错误
   * @returns {Array} 验证错误列表
   */
  getValidationErrors() {
    const validation = this.validateConfig();
    return validation.errors;
  }

  /**
   * 检查配置是否完整
   * @returns {boolean} 配置是否完整
   */
  isConfigComplete() {
    return this.config.serialNumber && 
           this.config.serialNumber.length > 0 &&
           this.config.timeoutMs > 0 &&
           this.config.retryCount > 0;
  }
}

// 全局配置管理器实例
export const drcConfigManager = new DrcConfigManager();
