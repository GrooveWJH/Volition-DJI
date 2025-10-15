/**
 * 设备状态管理器
 * 负责管理每个设备(SN)的每个卡片(CardID)的状态
 *
 * 核心数据结构：
 * Map<SN, Map<CardID, StateObject>>
 *
 * 示例：
 * {
 *   "SN001": {
 *     "drcControl": { status: "active", logs: [...] },
 *     "streaming": { isPlaying: true, url: "..." }
 *   },
 *   "SN002": {
 *     "drcControl": { status: "inactive", logs: [] }
 *   }
 * }
 */

class DeviceStateManager {
  constructor() {
    // 主状态存储：SN -> CardID -> State
    this.deviceStates = new Map();

    // 持久化配置
    this.persistenceEnabled = true;
    this.storagePrefix = 'device_state_';

    // 加载持久化状态
    this.loadFromStorage();

    console.log('[DeviceStateManager] 已初始化');
  }

  /**
   * 获取指定设备的指定卡片的完整状态对象
   * @param {string} sn - 设备序列号
   * @param {string} cardId - 卡片ID
   * @returns {Object} 状态对象（如果不存在则返回空对象）
   */
  getCardState(sn, cardId) {
    if (!sn || !cardId) {
      console.warn('[DeviceStateManager] SN或CardID为空');
      return {};
    }

    // 确保设备存在
    if (!this.deviceStates.has(sn)) {
      this.deviceStates.set(sn, new Map());
    }

    // 确保卡片状态存在
    const deviceState = this.deviceStates.get(sn);
    if (!deviceState.has(cardId)) {
      deviceState.set(cardId, {});
    }

    return deviceState.get(cardId);
  }

  /**
   * 获取指定设备的指定卡片的某个状态属性
   * @param {string} sn - 设备序列号
   * @param {string} cardId - 卡片ID
   * @param {string} key - 状态属性名
   * @returns {*} 属性值
   */
  getState(sn, cardId, key) {
    const cardState = this.getCardState(sn, cardId);
    return cardState[key];
  }

  /**
   * 设置指定设备的指定卡片的某个状态属性
   * @param {string} sn - 设备序列号
   * @param {string} cardId - 卡片ID
   * @param {string} key - 状态属性名
   * @param {*} value - 属性值
   */
  setState(sn, cardId, key, value) {
    if (!sn || !cardId) {
      console.warn('[DeviceStateManager] SN或CardID为空，无法设置状态');
      return;
    }

    const cardState = this.getCardState(sn, cardId);
    cardState[key] = value;

    // 触发状态变更事件
    this.emitStateChange(sn, cardId, key, value);

    // 持久化
    if (this.persistenceEnabled) {
      this.saveToStorage(sn, cardId);
    }
  }

  /**
   * 批量更新指定设备的指定卡片的状态
   * @param {string} sn - 设备序列号
   * @param {string} cardId - 卡片ID
   * @param {Object} updates - 要更新的状态对象
   */
  updateCardState(sn, cardId, updates) {
    if (!sn || !cardId || !updates) {
      console.warn('[DeviceStateManager] 参数不完整，无法更新状态');
      return;
    }

    const cardState = this.getCardState(sn, cardId);
    Object.assign(cardState, updates);

    // 触发批量状态变更事件
    this.emitBatchStateChange(sn, cardId, updates);

    // 持久化
    if (this.persistenceEnabled) {
      this.saveToStorage(sn, cardId);
    }
  }

  /**
   * 完全替换指定设备的指定卡片的状态
   * @param {string} sn - 设备序列号
   * @param {string} cardId - 卡片ID
   * @param {Object} newState - 新的状态对象
   */
  replaceCardState(sn, cardId, newState) {
    if (!sn || !cardId) {
      console.warn('[DeviceStateManager] SN或CardID为空，无法替换状态');
      return;
    }

    if (!this.deviceStates.has(sn)) {
      this.deviceStates.set(sn, new Map());
    }

    this.deviceStates.get(sn).set(cardId, { ...newState });

    // 持久化
    if (this.persistenceEnabled) {
      this.saveToStorage(sn, cardId);
    }
  }

  /**
   * 清除指定设备的指定卡片的状态
   * @param {string} sn - 设备序列号
   * @param {string} cardId - 卡片ID
   */
  clearCardState(sn, cardId) {
    if (!sn || !cardId) return;

    const deviceState = this.deviceStates.get(sn);
    if (deviceState) {
      deviceState.delete(cardId);
    }

    // 清除持久化
    if (this.persistenceEnabled) {
      this.removeFromStorage(sn, cardId);
    }
  }

  /**
   * 清除指定设备的所有卡片状态
   * @param {string} sn - 设备序列号
   */
  clearDeviceStates(sn) {
    if (!sn) return;

    this.deviceStates.delete(sn);

    // 清除持久化
    if (this.persistenceEnabled && typeof localStorage !== 'undefined') {
      const key = `${this.storagePrefix}${sn}`;
      localStorage.removeItem(key);
    }
  }

  /**
   * 获取指定设备的所有卡片状态
   * @param {string} sn - 设备序列号
   * @returns {Map<string, Object>} 所有卡片状态
   */
  getDeviceStates(sn) {
    return this.deviceStates.get(sn) || new Map();
  }

  /**
   * 获取所有设备的所有状态（调试用）
   * @returns {Map} 完整状态树
   */
  getAllStates() {
    return this.deviceStates;
  }

  /**
   * 触发单个状态变更事件
   * @private
   */
  emitStateChange(sn, cardId, key, value) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('device-state-changed', {
        detail: { sn, cardId, key, value }
      }));
    }
  }

  /**
   * 触发批量状态变更事件
   * @private
   */
  emitBatchStateChange(sn, cardId, updates) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('device-state-batch-changed', {
        detail: { sn, cardId, updates }
      }));
    }
  }

  /**
   * 保存状态到localStorage
   * @private
   */
  saveToStorage(sn, cardId) {
    if (typeof localStorage === 'undefined') return;

    try {
      const key = `${this.storagePrefix}${sn}_${cardId}`;
      const state = this.getCardState(sn, cardId);
      localStorage.setItem(key, JSON.stringify(state));
    } catch (error) {
      console.error('[DeviceStateManager] 保存状态失败:', error);
    }
  }

  /**
   * 从localStorage加载所有状态
   * @private
   */
  loadFromStorage() {
    if (typeof localStorage === 'undefined') return;

    try {
      // 遍历localStorage查找所有设备状态
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith(this.storagePrefix)) {
          const value = localStorage.getItem(key);
          if (value) {
            const state = JSON.parse(value);
            const parts = key.replace(this.storagePrefix, '').split('_');

            if (parts.length >= 2) {
              const sn = parts[0];
              const cardId = parts.slice(1).join('_');
              this.replaceCardState(sn, cardId, state);
            }
          }
        }
      }
      console.log('[DeviceStateManager] 已从localStorage加载状态');
    } catch (error) {
      console.error('[DeviceStateManager] 加载状态失败:', error);
    }
  }

  /**
   * 从localStorage移除指定状态
   * @private
   */
  removeFromStorage(sn, cardId) {
    if (typeof localStorage === 'undefined') return;

    try {
      const key = `${this.storagePrefix}${sn}_${cardId}`;
      localStorage.removeItem(key);
    } catch (error) {
      console.error('[DeviceStateManager] 移除状态失败:', error);
    }
  }

  /**
   * 启用/禁用持久化
   * @param {boolean} enabled
   */
  setPersistence(enabled) {
    this.persistenceEnabled = enabled;
    console.log(`[DeviceStateManager] 持久化${enabled ? '启用' : '禁用'}`);
  }

  /**
   * 获取统计信息
   * @returns {Object}
   */
  getStats() {
    const stats = {
      deviceCount: this.deviceStates.size,
      cards: {}
    };

    for (const [sn, cardStates] of this.deviceStates) {
      stats.cards[sn] = cardStates.size;
    }

    return stats;
  }
}

// 创建全局单例
const deviceStateManager = new DeviceStateManager();

// 暴露到window对象供调试
if (typeof window !== 'undefined') {
  window.deviceStateManager = deviceStateManager;
}

export { deviceStateManager, DeviceStateManager };
export default deviceStateManager;
