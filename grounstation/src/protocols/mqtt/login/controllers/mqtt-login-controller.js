/**
 * MQTT登录控制器
 * 处理MQTT登录相关的业务逻辑
 */

import { generateDjiLoginPage, createBlobUrl, revokeBlobUrl } from '../../shared/utils/html-generator.js';
import { globalEventManager } from '../../shared/utils/event-manager.js';
import { quickValidate } from '../../shared/utils/validation.js';

/**
 * MQTT登录控制器类
 */
export class MqttLoginController {
  constructor() {
    this.currentBlobUrl = null;
    this.config = {
      host: '',
      port: '',
      username: '',
      password: ''
    };
  }

  /**
   * 初始化控制器
   * @param {Object} initialConfig - 初始配置
   */
  init(initialConfig = {}) {
    this.config = { ...this.config, ...initialConfig };
    this.setupEventListeners();
  }

  /**
   * 设置事件监听器
   */
  setupEventListeners() {
    globalEventManager.on('config:updated', (newConfig) => {
      this.updateConfig(newConfig);
    });

    globalEventManager.on('login:generate', () => {
      this.generateLoginPage();
    });
  }

  /**
   * 更新配置
   * @param {Object} newConfig - 新配置
   */
  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
    globalEventManager.emit('controller:config-updated', this.config);
  }

  /**
   * 验证当前配置
   * @returns {Object} 验证结果
   */
  validateConfig() {
    const results = quickValidate.mqttConfig(this.config);
    const isValid = results.every(result => result.valid);
    const errors = results.filter(result => !result.valid);
    
    return {
      isValid,
      errors,
      results
    };
  }

  /**
   * 生成登录页面
   * @returns {Object} 生成结果
   */
  generateLoginPage() {
    try {
      // 验证配置
      const validation = this.validateConfig();
      if (!validation.isValid) {
        globalEventManager.emit('login:error', {
          type: 'validation',
          errors: validation.errors
        });
        return { success: false, errors: validation.errors };
      }

      // 清理旧的Blob URL
      if (this.currentBlobUrl) {
        revokeBlobUrl(this.currentBlobUrl);
      }

      // 生成新的登录页面
      const mqttUrl = `tcp://${this.config.host}:${this.config.port}`;
      const currentTime = new Date().toLocaleString();
      
      const htmlContent = generateDjiLoginPage({
        mqttUrl,
        mqttUsername: this.config.username,
        mqttPassword: this.config.password,
        currentTime
      });

      // 创建新的Blob URL
      this.currentBlobUrl = createBlobUrl(htmlContent);

      globalEventManager.emit('login:generated', {
        url: this.currentBlobUrl,
        config: this.config
      });

      return { 
        success: true, 
        url: this.currentBlobUrl,
        config: this.config
      };
      
    } catch (error) {
      globalEventManager.emit('login:error', {
        type: 'generation',
        message: error.message
      });
      return { success: false, error: error.message };
    }
  }

  /**
   * 测试MQTT连接配置
   * @returns {Promise<Object>} 测试结果
   */
  async testConnection() {
    try {
      // 这里可以添加实际的MQTT连接测试逻辑
      globalEventManager.emit('connection:testing', this.config);
      
      // 模拟连接测试
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const success = Math.random() > 0.3; // 模拟70%成功率
      
      if (success) {
        globalEventManager.emit('connection:success', this.config);
        return { success: true, message: '连接测试成功' };
      } else {
        globalEventManager.emit('connection:failed', this.config);
        return { success: false, message: '连接测试失败' };
      }
      
    } catch (error) {
      globalEventManager.emit('connection:error', {
        config: this.config,
        error: error.message
      });
      return { success: false, error: error.message };
    }
  }

  /**
   * 获取当前状态
   * @returns {Object} 当前状态
   */
  getStatus() {
    const validation = this.validateConfig();
    
    return {
      config: this.config,
      isConfigValid: validation.isValid,
      hasActivePage: !!this.currentBlobUrl,
      blobUrl: this.currentBlobUrl
    };
  }

  /**
   * 重置控制器
   */
  reset() {
    if (this.currentBlobUrl) {
      revokeBlobUrl(this.currentBlobUrl);
      this.currentBlobUrl = null;
    }
    
    this.config = {
      host: '',
      port: '',
      username: '',
      password: ''
    };

    globalEventManager.emit('controller:reset');
  }

  /**
   * 销毁控制器
   */
  destroy() {
    this.reset();
    globalEventManager.off('config:updated');
    globalEventManager.off('login:generate');
  }
}

/**
 * 默认MQTT登录控制器实例
 */
export const defaultMqttLoginController = new MqttLoginController();