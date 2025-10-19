// DJI Ground Station - 统一状态管理
import debugLogger from './debug.js';

class DeviceContext {
  constructor() {
    this.currentDevice = null;
    this.eventListeners = new Set();
    this._loadFromStorage();
  }

  setCurrentDevice(sn) {
    if (this.currentDevice !== sn) {
      const previousSN = this.currentDevice;
      this.currentDevice = sn;
      this._saveToStorage();
      this._notifyListeners('device-changed', { currentSN: sn, previousSN });
      debugLogger.state(`设备切换: ${previousSN} -> ${sn}`);
    }
  }

  getCurrentDevice() {
    return this.currentDevice;
  }

  addListener(callback) {
    this.eventListeners.add(callback);
    return () => this.eventListeners.delete(callback);
  }

  _notifyListeners(eventType, data) {
    this.eventListeners.forEach(listener => {
      try {
        listener(eventType, data);
      } catch (error) {
        debugLogger.error('设备上下文事件监听器错误:', error);
      }
    });

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('device-changed', { detail: data }));
    }
  }

  _loadFromStorage() {
    if (typeof window !== 'undefined') {
      try {
        this.currentDevice = localStorage.getItem('current_device_sn');
        if (this.currentDevice) {
          debugLogger.state(`已从localStorage恢复设备: ${this.currentDevice}`);
        }
      } catch (e) {
        debugLogger.warn('设备上下文初始化错误:', e);
      }
    }
  }

  _saveToStorage() {
    if (typeof window !== 'undefined') {
      try {
        if (this.currentDevice) {
          localStorage.setItem('current_device_sn', this.currentDevice);
        } else {
          localStorage.removeItem('current_device_sn');
        }
      } catch (e) {
        debugLogger.warn('无法保存设备SN到localStorage:', e);
      }
    }
  }

  getSummary() {
    return {
      currentDevice: this.currentDevice,
      listeners: this.eventListeners.size
    };
  }
}

class DeviceStateManager {
  constructor() {
    this.states = new Map();
    this._loadAllStates();
  }

  setState(sn, cardId, key, value) {
    if (!sn || !cardId || key === undefined) return;

    if (!this.states.has(sn)) {
      this.states.set(sn, new Map());
    }
    if (!this.states.get(sn).has(cardId)) {
      this.states.get(sn).set(cardId, {});
    }

    this.states.get(sn).get(cardId)[key] = value;
    this._saveState(sn, cardId);
  }

  getState(sn, cardId, key = null) {
    if (!sn || !cardId) return key === null ? {} : undefined;

    const deviceStates = this.states.get(sn);
    if (!deviceStates) return key === null ? {} : undefined;

    const cardState = deviceStates.get(cardId);
    if (!cardState) return key === null ? {} : undefined;

    return key === null ? { ...cardState } : cardState[key];
  }

  getAllStates() {
    const result = {};
    for (const [sn, deviceStates] of this.states) {
      result[sn] = {};
      for (const [cardId, cardState] of deviceStates) {
        result[sn][cardId] = { ...cardState };
      }
    }
    return result;
  }

  clearState(sn, cardId = null) {
    if (!sn) return;

    if (cardId) {
      const deviceStates = this.states.get(sn);
      if (deviceStates) {
        deviceStates.delete(cardId);
        this._removeStorageState(sn, cardId);
      }
    } else {
      this.states.delete(sn);
      this._removeAllStorageStates(sn);
    }
  }

  _saveState(sn, cardId) {
    if (typeof window !== 'undefined') {
      try {
        const key = `device_state_${sn}_${cardId}`;
        localStorage.setItem(key, JSON.stringify(this.getState(sn, cardId)));
      } catch (e) {
        debugLogger.warn(`保存状态失败: ${sn}.${cardId}`, e);
      }
    }
  }

  _loadAllStates() {
    if (typeof window === 'undefined') return;

    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key?.startsWith('device_state_')) {
          const parts = key.split('_');
          if (parts.length >= 4) {
            const sn = parts[2];
            const cardId = parts.slice(3).join('_');
            const stateData = JSON.parse(localStorage.getItem(key) || '{}');

            if (!this.states.has(sn)) {
              this.states.set(sn, new Map());
            }
            this.states.get(sn).set(cardId, stateData);
          }
        }
      }
      debugLogger.debug('状态数据已从localStorage加载');
    } catch (e) {
      debugLogger.error('加载状态数据失败:', e);
    }
  }

  _removeStorageState(sn, cardId) {
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem(`device_state_${sn}_${cardId}`);
      } catch (e) {
        debugLogger.warn(`删除状态失败: ${sn}.${cardId}`, e);
      }
    }
  }

  _removeAllStorageStates(sn) {
    if (typeof window !== 'undefined') {
      try {
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key?.startsWith(`device_state_${sn}_`)) {
            keysToRemove.push(key);
          }
        }
        keysToRemove.forEach(key => localStorage.removeItem(key));
      } catch (e) {
        debugLogger.warn(`删除设备状态失败: ${sn}`, e);
      }
    }
  }
}

class CardStateProxy {
  constructor(target, cardId, options = {}) {
    this.target = target;
    this.cardId = cardId;
    this.debug = options.debug || false;
    this.deviceStateManager = deviceStateManager;
    this.deviceContext = deviceContext;

    return new Proxy(target, {
      set: (obj, prop, value) => this._handleSet(obj, prop, value),
      get: (obj, prop) => {
        // 如果访问的是proxy的方法，返回绑定的方法
        if (prop === 'restoreState') {
          return this.restoreState.bind(this);
        }
        return obj[prop];
      }
    });
  }

  _handleSet(obj, prop, value) {
    if (this._isSerializable(value)) {
      const currentSN = this.deviceContext.getCurrentDevice();
      if (currentSN) {
        this.deviceStateManager.setState(currentSN, this.cardId, prop, value);
        if (this.debug) {
          debugLogger.debug(`[${this.cardId}] 状态保存: ${prop}`, value);
        }
      }
    }
    obj[prop] = value;
    return true;
  }

  _isSerializable(value) {
    if (value === null || value === undefined) return true;
    if (typeof value === 'function') return false;

    // 只在浏览器环境且DOM API可用时检查DOM元素
    if (typeof Element !== 'undefined' && value instanceof Element) return false;
    if (typeof Node !== 'undefined' && value instanceof Node) return false;

    try {
      JSON.stringify(value);
      return true;
    } catch {
      return false;
    }
  }

  restoreState() {
    const currentSN = this.deviceContext.getCurrentDevice();
    if (!currentSN) return;

    const savedState = this.deviceStateManager.getState(currentSN, this.cardId);
    if (savedState) {
      Object.assign(this.target, savedState);
      if (this.debug) {
        debugLogger.debug(`[${this.cardId}] 状态恢复: ${currentSN}`, savedState);
      }
    }
  }
}

class CardStateManager {
  constructor() {
    this.registeredCards = new Map();
    this.deviceContext = deviceContext;
    this._initEventListeners();
  }

  register(cardInstance, cardId, options = {}) {
    const proxy = new CardStateProxy(cardInstance, cardId, options);
    this.registeredCards.set(cardId, { proxy, instance: cardInstance, options });
    proxy.restoreState();
    debugLogger.state(`卡片已注册: ${cardId}`);
    return proxy;
  }

  unregister(cardId) {
    this.registeredCards.delete(cardId);
    debugLogger.state(`卡片已注销: ${cardId}`);
  }

  _initEventListeners() {
    this.deviceContext.addListener((eventType, data) => {
      if (eventType === 'device-changed') {
        this._handleDeviceChanged(data);
      }
    });
  }

  _handleDeviceChanged(data) {
    this.registeredCards.forEach((cardInfo, cardId) => {
      try {
        cardInfo.proxy.restoreState();
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('card-state-restored', {
            detail: { cardId, sn: data.currentSN }
          }));
        }
      } catch (error) {
        debugLogger.error(`恢复卡片状态失败: ${cardId}`, error);
      }
    });
  }

  debug() {
    const summary = {};
    this.registeredCards.forEach((cardInfo, cardId) => {
      const currentSN = this.deviceContext.getCurrentDevice();
      const state = currentSN ? deviceStateManager.getState(currentSN, cardId) : {};
      summary[cardId] = {
        hasProxy: !!cardInfo.proxy,
        options: cardInfo.options,
        currentState: state
      };
    });

    debugLogger.debug('卡片状态管理器调试信息:', {
      registeredCards: summary,
      currentDevice: this.deviceContext.getCurrentDevice(),
      totalDeviceStates: deviceStateManager.getAllStates()
    });

    return summary;
  }
}

const deviceContext = new DeviceContext();
const deviceStateManager = new DeviceStateManager();
const cardStateManager = new CardStateManager();

if (typeof window !== 'undefined') {
  window.deviceContext = deviceContext;
  window.deviceStateManager = deviceStateManager;
  window.cardStateManager = cardStateManager;
}

export { deviceContext, deviceStateManager, cardStateManager };
export default cardStateManager;
