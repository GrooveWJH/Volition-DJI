/**
 * 卡片状态管理器（统一入口）
 * 整合 DeviceStateManager 和 CardStateProxy，提供简单的API供卡片使用
 *
 * 使用方法：
 * 1. 在卡片构造函数中调用 register() 注册卡片
 * 2. 在卡片中添加 state-restored 事件监听器更新UI
 *
 * 示例：
 * ```javascript
 * export class MyCard {
 *   constructor() {
 *     this.status = 'idle';
 *     this.logs = [];
 *
 *     // 注册到状态管理器（返回代理对象）
 *     return CardStateManager.register(this, 'myCard');
 *   }
 * }
 * ```
 */

import { CardStateProxy } from './card-state-proxy.js';
import deviceStateManager from './device-state-manager.js';
import deviceContext from './device-context.js';

class CardStateManager {
  constructor() {
    // 注册的卡片代理实例 Map<CardID, CardStateProxy>
    this.registeredCards = new Map();

    // 初始化设备切换监听
    this.initDeviceSwitchListener();

    console.log('[CardStateManager] 已初始化');
  }

  /**
   * 注册卡片到状态管理系统
   * @param {Object} cardInstance - 卡片实例
   * @param {string} cardId - 卡片唯一ID
   * @param {Object} options - 配置选项
   * @returns {Proxy} 返回代理后的卡片实例
   */
  register(cardInstance, cardId, options = {}) {
    if (!cardInstance || !cardId) {
      console.error('[CardStateManager] 注册失败：cardInstance或cardId为空');
      return cardInstance;
    }

    if (this.registeredCards.has(cardId)) {
      console.warn(`[CardStateManager] 卡片 ${cardId} 已注册，将覆盖旧实例`);
    }

    // 创建状态代理
    const proxy = new CardStateProxy(cardInstance, cardId, options);

    // 保存代理引用
    this.registeredCards.set(cardId, proxy);

    console.log(`[CardStateManager] ✓ 卡片 ${cardId} 已注册`);

    // 返回代理对象
    return proxy.getProxy();
  }

  /**
   * 注销卡片
   * @param {string} cardId - 卡片ID
   */
  unregister(cardId) {
    if (this.registeredCards.has(cardId)) {
      this.registeredCards.delete(cardId);
      console.log(`[CardStateManager] 卡片 ${cardId} 已注销`);
    }
  }

  /**
   * 获取卡片代理实例
   * @param {string} cardId - 卡片ID
   * @returns {CardStateProxy|null}
   */
  getCardProxy(cardId) {
    return this.registeredCards.get(cardId) || null;
  }

  /**
   * 初始化设备切换监听器
   * @private
   */
  initDeviceSwitchListener() {
    deviceContext.addListener((currentSN, previousSN) => {
      this.onDeviceSwitched(currentSN, previousSN);
    });
  }

  /**
   * 设备切换时的处理
   * @private
   */
  onDeviceSwitched(currentSN, previousSN) {
    console.log(`[CardStateManager] 设备切换: ${previousSN || 'null'} → ${currentSN || 'null'}`);

    if (!currentSN) return;

    // 1. 通知所有注册的卡片代理切换设备
    for (const [cardId, proxy] of this.registeredCards) {
      proxy.switchDevice(currentSN);
    }

    // 2. 触发全局事件，供卡片更新UI
    this.emitStateRestored(currentSN, previousSN);
  }

  /**
   * 触发状态恢复事件
   * @private
   */
  emitStateRestored(currentSN, previousSN) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('card-state-restored', {
        detail: {
          currentSN,
          previousSN,
          timestamp: Date.now()
        }
      }));
    }
  }

  /**
   * 手动触发快照（保存当前所有卡片状态）
   * @param {string} sn - 设备序列号（可选，默认当前设备）
   */
  snapshotAll(sn = null) {
    const targetSN = sn || deviceContext.getCurrentDevice();
    if (!targetSN) {
      console.warn('[CardStateManager] 无法快照：没有当前设备');
      return;
    }

    for (const [cardId, proxy] of this.registeredCards) {
      proxy.snapshotState(targetSN);
    }

    console.log(`[CardStateManager] ✓ 已快照所有卡片状态 (SN: ${targetSN})`);
  }

  /**
   * 手动恢复所有卡片状态
   * @param {string} sn - 设备序列号（可选，默认当前设备）
   */
  restoreAll(sn = null) {
    const targetSN = sn || deviceContext.getCurrentDevice();
    if (!targetSN) {
      console.warn('[CardStateManager] 无法恢复：没有当前设备');
      return;
    }

    for (const [cardId, proxy] of this.registeredCards) {
      proxy.restoreState(targetSN);
    }

    console.log(`[CardStateManager] ✓ 已恢复所有卡片状态 (SN: ${targetSN})`);

    this.emitStateRestored(targetSN, null);
  }

  /**
   * 清除指定设备的所有卡片状态
   * @param {string} sn - 设备序列号
   */
  clearDeviceStates(sn) {
    if (!sn) {
      console.warn('[CardStateManager] 无法清除：SN为空');
      return;
    }

    deviceStateManager.clearDeviceStates(sn);
    console.log(`[CardStateManager] ✓ 已清除设备 ${sn} 的所有状态`);
  }

  /**
   * 清除指定卡片在所有设备上的状态
   * @param {string} cardId - 卡片ID
   */
  clearCardStates(cardId) {
    if (!cardId) {
      console.warn('[CardStateManager] 无法清除：cardId为空');
      return;
    }

    const allStates = deviceStateManager.getAllStates();
    for (const [sn] of allStates) {
      deviceStateManager.clearCardState(sn, cardId);
    }

    console.log(`[CardStateManager] ✓ 已清除卡片 ${cardId} 的所有状态`);
  }

  /**
   * 获取统计信息
   * @returns {Object}
   */
  getStats() {
    return {
      registeredCards: this.registeredCards.size,
      deviceStates: deviceStateManager.getStats()
    };
  }

  /**
   * 启用/禁用持久化
   * @param {boolean} enabled
   */
  setPersistence(enabled) {
    deviceStateManager.setPersistence(enabled);
  }

  /**
   * 调试：打印所有状态
   */
  debug() {
    console.group('[CardStateManager] 调试信息');
    console.log('注册的卡片:', Array.from(this.registeredCards.keys()));
    console.log('设备状态:', deviceStateManager.getAllStates());
    console.log('统计信息:', this.getStats());
    console.groupEnd();
  }
}

// 创建全局单例
const cardStateManager = new CardStateManager();

// 暴露到window对象供调试和外部访问
if (typeof window !== 'undefined') {
  window.cardStateManager = cardStateManager;
}

export { cardStateManager, CardStateManager };
export default cardStateManager;
