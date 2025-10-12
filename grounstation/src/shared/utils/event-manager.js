/**
 * 事件管理工具
 * 提供事件监听、触发和管理功能
 */

/**
 * 简单的事件管理器类
 */
export class EventManager {
  constructor() {
    this.events = new Map();
  }

  /**
   * 注册事件监听器
   * @param {string} eventName - 事件名称
   * @param {Function} callback - 回调函数
   * @param {Object} options - 选项
   */
  on(eventName, callback, options = {}) {
    if (!this.events.has(eventName)) {
      this.events.set(eventName, []);
    }
    
    const listener = {
      callback,
      once: options.once || false,
      context: options.context || null
    };
    
    this.events.get(eventName).push(listener);
  }

  /**
   * 注册一次性事件监听器
   * @param {string} eventName - 事件名称
   * @param {Function} callback - 回调函数
   * @param {Object} context - 上下文
   */
  once(eventName, callback, context = null) {
    this.on(eventName, callback, { once: true, context });
  }

  /**
   * 移除事件监听器
   * @param {string} eventName - 事件名称
   * @param {Function} callback - 要移除的回调函数
   */
  off(eventName, callback) {
    if (!this.events.has(eventName)) return;
    
    const listeners = this.events.get(eventName);
    const index = listeners.findIndex(listener => listener.callback === callback);
    
    if (index > -1) {
      listeners.splice(index, 1);
    }
    
    if (listeners.length === 0) {
      this.events.delete(eventName);
    }
  }

  /**
   * 触发事件
   * @param {string} eventName - 事件名称
   * @param {...any} args - 传递给监听器的参数
   */
  emit(eventName, ...args) {
    if (!this.events.has(eventName)) return;
    
    const listeners = this.events.get(eventName).slice();
    
    for (const listener of listeners) {
      try {
        if (listener.context) {
          listener.callback.call(listener.context, ...args);
        } else {
          listener.callback(...args);
        }
        
        if (listener.once) {
          this.off(eventName, listener.callback);
        }
      } catch (error) {
        console.error(`Error in event listener for "${eventName}":`, error);
      }
    }
  }

  /**
   * 清除所有事件监听器
   */
  clear() {
    this.events.clear();
  }

  /**
   * 获取指定事件的监听器数量
   * @param {string} eventName - 事件名称
   * @returns {number} 监听器数量
   */
  listenerCount(eventName) {
    return this.events.has(eventName) ? this.events.get(eventName).length : 0;
  }
}

/**
 * 全局事件管理器实例
 */
export const globalEventManager = new EventManager();

/**
 * 防抖函数
 * @param {Function} func - 要防抖的函数
 * @param {number} delay - 延迟时间(ms)
 * @returns {Function} 防抖后的函数
 */
export function debounce(func, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

/**
 * 节流函数
 * @param {Function} func - 要节流的函数
 * @param {number} limit - 限制时间(ms)
 * @returns {Function} 节流后的函数
 */
export function throttle(func, limit) {
  let inThrottle;
  return function (...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * DOM元素事件处理助手
 */
export class DOMEventHelper {
  constructor() {
    this.listeners = new Map();
  }

  /**
   * 添加DOM事件监听器
   * @param {Element} element - DOM元素
   * @param {string} event - 事件类型
   * @param {Function} handler - 事件处理函数
   * @param {Object} options - 事件选项
   */
  addListener(element, event, handler, options = {}) {
    const key = this.getKey(element, event, handler);
    
    if (this.listeners.has(key)) {
      return; // 避免重复添加
    }
    
    const wrappedHandler = options.once 
      ? (...args) => {
          handler(...args);
          this.removeListener(element, event, handler);
        }
      : handler;
    
    element.addEventListener(event, wrappedHandler, options);
    this.listeners.set(key, { element, event, handler: wrappedHandler, options });
  }

  /**
   * 移除DOM事件监听器
   * @param {Element} element - DOM元素
   * @param {string} event - 事件类型
   * @param {Function} handler - 事件处理函数
   */
  removeListener(element, event, handler) {
    const key = this.getKey(element, event, handler);
    const listener = this.listeners.get(key);
    
    if (listener) {
      element.removeEventListener(event, listener.handler, listener.options);
      this.listeners.delete(key);
    }
  }

  /**
   * 清除所有监听器
   */
  clearAll() {
    for (const listener of this.listeners.values()) {
      listener.element.removeEventListener(listener.event, listener.handler, listener.options);
    }
    this.listeners.clear();
  }

  /**
   * 生成监听器唯一键
   * @private
   */
  getKey(element, event, handler) {
    return `${element.toString()}_${event}_${handler.toString()}`;
  }
}

/**
 * 全局DOM事件助手实例
 */
export const globalDOMEventHelper = new DOMEventHelper();