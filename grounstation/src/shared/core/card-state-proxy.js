/**
 * 卡片状态代理
 * 使用JavaScript Proxy拦截卡片实例的属性读写，自动路由到DeviceStateManager
 *
 * 核心功能：
 * 1. 拦截属性读取：从当前设备的状态中读取
 * 2. 拦截属性写入：保存到当前设备的状态中
 * 3. 设备切换时自动更新状态源
 */

import deviceStateManager from './device-state-manager.js';
import deviceContext from './device-context.js';

class CardStateProxy {
  /**
   * @param {Object} cardInstance - 卡片实例
   * @param {string} cardId - 卡片ID（全局唯一）
   * @param {Object} options - 配置选项
   */
  constructor(cardInstance, cardId, options = {}) {
    this.cardInstance = cardInstance;
    this.cardId = cardId;
    this.options = {
      // 需要代理的属性列表（如果为空则代理所有）
      includedProps: options.includedProps || null,
      // 需要排除的属性列表
      excludedProps: options.excludedProps || ['constructor', 'init', 'bindElements', 'bindEvents'],
      // 是否自动同步DOM元素
      syncDOMElements: options.syncDOMElements !== false,
      // 调试模式
      debug: options.debug || false
    };

    // 原始状态备份（用于非代理属性）
    this.originalState = {};

    // 创建代理
    this.proxy = this.createProxy();

    // 初始化：从DeviceStateManager加载当前设备的状态
    this.restoreState();

    if (this.options.debug) {
      console.log(`[CardStateProxy] 已为 ${cardId} 创建代理`);
    }
  }

  /**
   * 创建Proxy对象
   * @private
   */
  createProxy() {
    const self = this;

    return new Proxy(this.cardInstance, {
      get(target, prop, receiver) {
        // 1. 检查是否应该被代理
        if (!self.shouldProxy(prop)) {
          return Reflect.get(target, prop, receiver);
        }

        // 2. 获取当前设备SN
        const currentSN = deviceContext.getCurrentDevice();
        if (!currentSN) {
          // 如果没有当前设备，返回原始值
          return Reflect.get(target, prop, receiver);
        }

        // 3. 从DeviceStateManager读取
        const value = deviceStateManager.getState(currentSN, self.cardId, prop);

        // 4. 如果状态中没有，返回原始值（首次访问）
        if (value === undefined) {
          return Reflect.get(target, prop, receiver);
        }

        if (self.options.debug) {
          console.log(`[CardStateProxy][${self.cardId}] GET ${String(prop)}:`, value);
        }

        return value;
      },

      set(target, prop, value, receiver) {
        // 1. 检查是否应该被代理
        if (!self.shouldProxy(prop)) {
          return Reflect.set(target, prop, value, receiver);
        }

        // 2. 获取当前设备SN
        const currentSN = deviceContext.getCurrentDevice();
        if (!currentSN) {
          // 如果没有当前设备，只设置原始属性
          return Reflect.set(target, prop, value, receiver);
        }

        // 3. 保存到DeviceStateManager
        deviceStateManager.setState(currentSN, self.cardId, prop, value);

        // 4. 同时更新原始对象（保持一致性）
        const result = Reflect.set(target, prop, value, receiver);

        if (self.options.debug) {
          console.log(`[CardStateProxy][${self.cardId}] SET ${String(prop)}:`, value);
        }

        return result;
      }
    });
  }

  /**
   * 判断属性是否应该被代理
   * @private
   */
  shouldProxy(prop) {
    // 排除Symbol和内部属性
    if (typeof prop === 'symbol' || String(prop).startsWith('_')) {
      return false;
    }

    // 排除函数方法
    const value = this.cardInstance[prop];
    if (typeof value === 'function') {
      return false;
    }

    // 检查排除列表
    if (this.options.excludedProps && this.options.excludedProps.includes(prop)) {
      return false;
    }

    // 检查包含列表
    if (this.options.includedProps && !this.options.includedProps.includes(prop)) {
      return false;
    }

    return true;
  }

  /**
   * 切换到新设备
   * @param {string} newSN - 新设备序列号
   */
  switchDevice(newSN) {
    if (!newSN) return;

    if (this.options.debug) {
      console.log(`[CardStateProxy][${this.cardId}] 切换设备: ${newSN}`);
    }

    // 恢复新设备的状态
    this.restoreState(newSN);
  }

  /**
   * 从DeviceStateManager恢复状态到卡片实例
   * @param {string} sn - 设备序列号（可选，默认当前设备）
   */
  restoreState(sn = null) {
    const targetSN = sn || deviceContext.getCurrentDevice();
    if (!targetSN) return;

    const cardState = deviceStateManager.getCardState(targetSN, this.cardId);

    // **关键修复**：直接修改原始对象，避免触发Proxy的set拦截器
    // 将状态应用到原始卡片实例（而不是通过Proxy）
    Object.keys(cardState).forEach(key => {
      if (this.shouldProxy(key)) {
        // 直接修改原始对象，不触发Proxy
        Reflect.set(this.cardInstance, key, cardState[key]);
      }
    });

    if (this.options.debug) {
      console.log(`[CardStateProxy][${this.cardId}] 恢复状态 (SN: ${targetSN}):`, cardState);
    }
  }

  /**
   * 保存当前卡片实例的状态到DeviceStateManager
   * @param {string} sn - 设备序列号（可选，默认当前设备）
   */
  snapshotState(sn = null) {
    const targetSN = sn || deviceContext.getCurrentDevice();
    if (!targetSN) return;

    const snapshot = {};

    // 遍历卡片实例的所有属性
    Object.keys(this.cardInstance).forEach(key => {
      if (this.shouldProxy(key)) {
        snapshot[key] = this.cardInstance[key];
      }
    });

    // 批量更新到DeviceStateManager
    deviceStateManager.updateCardState(targetSN, this.cardId, snapshot);

    if (this.options.debug) {
      console.log(`[CardStateProxy][${this.cardId}] 快照状态:`, snapshot);
    }
  }

  /**
   * 清除当前设备的卡片状态
   */
  clearState() {
    const currentSN = deviceContext.getCurrentDevice();
    if (!currentSN) return;

    deviceStateManager.clearCardState(currentSN, this.cardId);

    if (this.options.debug) {
      console.log(`[CardStateProxy][${this.cardId}] 清除状态`);
    }
  }

  /**
   * 获取Proxy对象
   * @returns {Proxy}
   */
  getProxy() {
    return this.proxy;
  }

  /**
   * 获取原始卡片实例（未代理）
   * @returns {Object}
   */
  getOriginalInstance() {
    return this.cardInstance;
  }
}

export { CardStateProxy };
export default CardStateProxy;
