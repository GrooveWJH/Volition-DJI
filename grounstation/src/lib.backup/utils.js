// DJI Ground Station - 工具函数库
// 合并: event-manager.js + validation.js

import debugLogger from './debug.js';

// 事件管理器
class EventManager {
  constructor() {
    this.listeners = new Map();
    this.eventHistory = [];
    this.maxHistorySize = 1000;
    this.debug = false;
  }

  on(eventName, callback, options = {}) {
    if (typeof callback !== 'function') {
      throw new Error('回调函数必须是function类型');
    }

    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set());
    }

    const listenerInfo = {
      callback,
      once: options.once || false,
      priority: options.priority || 0,
      id: this._generateId()
    };

    this.listeners.get(eventName).add(listenerInfo);

    if (this.debug) {
      debugLogger.debug(`[EventManager] 监听器已注册: ${eventName}`, listenerInfo);
    }

    return listenerInfo.id;
  }

  once(eventName, callback, options = {}) {
    return this.on(eventName, callback, { ...options, once: true });
  }

  off(eventName, listenerId = null) {
    if (!this.listeners.has(eventName)) {
      return false;
    }

    const eventListeners = this.listeners.get(eventName);

    if (listenerId) {
      // 移除特定监听器
      for (const listener of eventListeners) {
        if (listener.id === listenerId) {
          eventListeners.delete(listener);
          if (this.debug) {
            debugLogger.debug(`[EventManager] 监听器已移除: ${eventName}#${listenerId}`);
          }
          return true;
        }
      }
      return false;
    } else {
      // 移除所有监听器
      const count = eventListeners.size;
      eventListeners.clear();
      if (this.debug) {
        debugLogger.debug(`[EventManager] 已移除 ${count} 个监听器: ${eventName}`);
      }
      return count > 0;
    }
  }

  emit(eventName, data = null) {
    const eventInfo = {
      name: eventName,
      data: data,
      timestamp: Date.now(),
      id: this._generateId()
    };

    // 添加到历史记录
    this._addToHistory(eventInfo);

    if (!this.listeners.has(eventName)) {
      if (this.debug) {
        debugLogger.debug(`[EventManager] 无监听器的事件: ${eventName}`, data);
      }
      return [];
    }

    const eventListeners = Array.from(this.listeners.get(eventName))
      .sort((a, b) => b.priority - a.priority);

    const results = [];
    const toRemove = [];

    for (const listener of eventListeners) {
      try {
        const result = listener.callback(data, eventInfo);
        results.push(result);

        if (listener.once) {
          toRemove.push(listener);
        }
      } catch (error) {
        debugLogger.error(`[EventManager] 监听器执行错误 [${eventName}]:`, error);
        results.push(null);
      }
    }

    // 移除一次性监听器
    if (toRemove.length > 0) {
      const eventListeners = this.listeners.get(eventName);
      toRemove.forEach(listener => eventListeners.delete(listener));
    }

    if (this.debug) {
      debugLogger.debug(`[EventManager] 事件已触发: ${eventName}`, {
        listenersCount: eventListeners.length,
        results: results.length
      });
    }

    return results;
  }

  getListeners(eventName = null) {
    if (eventName) {
      const listeners = this.listeners.get(eventName);
      return listeners ? Array.from(listeners) : [];
    }

    const allListeners = {};
    for (const [name, listeners] of this.listeners) {
      allListeners[name] = Array.from(listeners);
    }
    return allListeners;
  }

  getEventHistory(eventName = null, limit = 100) {
    let history = this.eventHistory;

    if (eventName) {
      history = history.filter(event => event.name === eventName);
    }

    return history.slice(-limit);
  }

  clearHistory() {
    this.eventHistory = [];
  }

  _addToHistory(eventInfo) {
    this.eventHistory.push(eventInfo);

    if (this.eventHistory.length > this.maxHistorySize) {
      this.eventHistory = this.eventHistory.slice(-this.maxHistorySize);
    }
  }

  _generateId() {
    return `${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
  }

  setDebug(enabled) {
    this.debug = enabled;
    debugLogger.info(`[EventManager] 调试模式: ${enabled ? '启用' : '禁用'}`);
  }

  getStats() {
    const stats = {
      totalEvents: Object.keys(this.listeners).length,
      totalListeners: 0,
      historySize: this.eventHistory.length,
      events: {}
    };

    for (const [eventName, listeners] of this.listeners) {
      const count = listeners.size;
      stats.totalListeners += count;
      stats.events[eventName] = count;
    }

    return stats;
  }

  cleanup() {
    this.listeners.clear();
    this.eventHistory = [];
    debugLogger.info('[EventManager] 已清理所有事件监听器');
  }
}

// 验证工具函数
class Validator {
  // 基础类型验证
  static isString(value) {
    return typeof value === 'string';
  }

  static isNumber(value) {
    return typeof value === 'number' && !isNaN(value);
  }

  static isBoolean(value) {
    return typeof value === 'boolean';
  }

  static isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  static isArray(value) {
    return Array.isArray(value);
  }

  static isFunction(value) {
    return typeof value === 'function';
  }

  // 特定格式验证
  static isEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return this.isString(email) && emailRegex.test(email);
  }

  static isUrl(url) {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }

  static isDJISerial(sn) {
    return this.isString(sn) && /^[A-Z0-9]{14}$/.test(sn);
  }

  static isIPAddress(ip) {
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return this.isString(ip) && ipRegex.test(ip);
  }

  static isPort(port) {
    const num = parseInt(port);
    return this.isNumber(num) && num >= 1 && num <= 65535;
  }

  // 值范围验证
  static inRange(value, min, max) {
    return this.isNumber(value) && value >= min && value <= max;
  }

  static minLength(value, min) {
    return (this.isString(value) || this.isArray(value)) && value.length >= min;
  }

  static maxLength(value, max) {
    return (this.isString(value) || this.isArray(value)) && value.length <= max;
  }

  // 复合验证
  static validateMQTTConfig(config) {
    const errors = [];

    if (!this.isObject(config)) {
      errors.push('配置必须是对象类型');
      return { valid: false, errors };
    }

    if (!this.isString(config.host) || config.host.trim() === '') {
      errors.push('主机地址不能为空');
    }

    if (!this.isPort(config.port)) {
      errors.push('端口必须是1-65535之间的数字');
    }

    if (config.username !== undefined && !this.isString(config.username)) {
      errors.push('用户名必须是字符串类型');
    }

    if (config.password !== undefined && !this.isString(config.password)) {
      errors.push('密码必须是字符串类型');
    }

    return { valid: errors.length === 0, errors };
  }

  static validateServiceParams(serviceName, params, requiredParams = []) {
    const errors = [];

    if (!this.isString(serviceName) || serviceName.trim() === '') {
      errors.push('服务名称不能为空');
    }

    if (!this.isObject(params)) {
      errors.push('参数必须是对象类型');
      return { valid: false, errors };
    }

    // 检查必需参数
    for (const param of requiredParams) {
      if (!(param in params)) {
        errors.push(`缺少必需参数: ${param}`);
      }
    }

    return { valid: errors.length === 0, errors };
  }

  // 数据清理
  static sanitizeString(str) {
    if (!this.isString(str)) return '';
    return str.trim().replace(/[<>]/g, '');
  }

  static sanitizeNumber(num, defaultValue = 0) {
    const parsed = parseFloat(num);
    return this.isNumber(parsed) ? parsed : defaultValue;
  }

  static sanitizeBoolean(value, defaultValue = false) {
    if (this.isBoolean(value)) return value;
    if (this.isString(value)) {
      const lower = value.toLowerCase();
      return lower === 'true' || lower === '1' || lower === 'yes';
    }
    return defaultValue;
  }
}

// 通用工具函数
class Utils {
  // 延时函数
  static sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // 防抖函数
  static debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // 节流函数
  static throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  }

  // 深拷贝
  static deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof Array) return obj.map(item => this.deepClone(item));
    if (typeof obj === 'object') {
      const cloned = {};
      Object.keys(obj).forEach(key => {
        cloned[key] = this.deepClone(obj[key]);
      });
      return cloned;
    }
  }

  // 生成ID
  static generateId(prefix = '') {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 11);
    return prefix ? `${prefix}_${timestamp}_${random}` : `${timestamp}_${random}`;
  }

  // 格式化字节大小
  static formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  // 格式化时间
  static formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }

  // 安全的JSON解析
  static safeJsonParse(str, defaultValue = null) {
    try {
      return JSON.parse(str);
    } catch (e) {
      debugLogger.warn('JSON解析失败:', e);
      return defaultValue;
    }
  }

  // 安全的JSON字符串化
  static safeJsonStringify(obj, defaultValue = '{}') {
    try {
      return JSON.stringify(obj);
    } catch (e) {
      debugLogger.warn('JSON字符串化失败:', e);
      return defaultValue;
    }
  }

  // 重试函数
  static async retry(fn, maxAttempts = 3, delay = 1000) {
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await fn();
      } catch (error) {
        if (attempt === maxAttempts) {
          throw error;
        }
        debugLogger.warn(`重试第 ${attempt} 次失败:`, error);
        await this.sleep(delay);
      }
    }
  }
}

// 全局实例
const eventManager = new EventManager();

// 浏览器全局变量
if (typeof window !== 'undefined') {
  window.eventManager = eventManager;
  window.Validator = Validator;
  window.Utils = Utils;
}

export { EventManager, Validator, Utils, eventManager };
export default { EventManager, Validator, Utils, eventManager };