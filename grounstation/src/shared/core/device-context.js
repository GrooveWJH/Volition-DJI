/**
 * 全局设备上下文管理
 * 管理当前选中的设备SN，提供设备切换能力
 */

/**
 * 设备上下文状态
 */
class DeviceContext {
  constructor() {
    this.currentDeviceSN = null;
    this.listeners = new Set();

    // 从localStorage恢复上次选中的设备
    this.loadFromStorage();
  }

  /**
   * 获取当前设备SN
   * @returns {string|null}
   */
  getCurrentDevice() {
    return this.currentDeviceSN;
  }

  /**
   * 设置当前设备SN
   * @param {string} sn - 设备序列号
   */
  setCurrentDevice(sn) {
    if (this.currentDeviceSN === sn) return;

    const previousSN = this.currentDeviceSN;
    this.currentDeviceSN = sn;

    this.saveToStorage();
    this.notifyListeners(sn, previousSN);
  }

  /**
   * 清除当前设备
   */
  clearCurrentDevice() {
    this.setCurrentDevice(null);
  }

  /**
   * 添加设备切换监听器
   * @param {Function} callback - 回调函数 (currentSN, previousSN) => void
   * @returns {Function} 移除监听器的函数
   */
  addListener(callback) {
    this.listeners.add(callback);

    // 返回移除监听器的函数
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * 通知所有监听者
   * @private
   */
  notifyListeners(currentSN, previousSN) {
    this.listeners.forEach(listener => {
      try {
        listener(currentSN, previousSN);
      } catch (error) {
        console.error('[DeviceContext错误]', error);
      }
    });

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('device-changed', {
        detail: { currentSN, previousSN }
      }));
    }
  }

  /**
   * 从localStorage加载
   * @private
   */
  loadFromStorage() {
    if (typeof localStorage === 'undefined') return;

    try {
      const stored = localStorage.getItem('current_device_sn');
      if (stored) {
        this.currentDeviceSN = stored;
      }
    } catch (error) {
      console.error('[DeviceContext错误]', error);
    }
  }

  /**
   * 保存到localStorage
   * @private
   */
  saveToStorage() {
    if (typeof localStorage === 'undefined') return;

    try {
      if (this.currentDeviceSN) {
        localStorage.setItem('current_device_sn', this.currentDeviceSN);
      } else {
        localStorage.removeItem('current_device_sn');
      }
    } catch (error) {
      console.error('[DeviceContext错误]', error);
    }
  }

  /**
   * 获取当前设备信息摘要
   * @returns {Object}
   */
  getSummary() {
    return {
      currentDevice: this.currentDeviceSN,
      hasDevice: !!this.currentDeviceSN,
      listenerCount: this.listeners.size
    };
  }
}

// 创建全局单例
const deviceContext = new DeviceContext();

// 导出单例和类
export { deviceContext, DeviceContext };
export default deviceContext;
