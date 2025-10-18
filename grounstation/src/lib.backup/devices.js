// DJI Ground Station - 设备管理
// 合并: device-manager.js + device-scanner.js

import debugLogger from './debug.js';

// 设备扫描器
class DeviceScanner {
  constructor() {
    this.isScanning = false;
    this.scanInterval = null;
    this.intervalMs = 3000;
    this.emqxConfig = this._getEmqxConfig();
    this.lastScanResult = [];
    this.onDevicesFound = null;
  }

  _getEmqxConfig() {
    if (typeof window !== 'undefined') {
      try {
        return {
          host: localStorage.getItem('emqx_host') || '127.0.0.1',
          port: localStorage.getItem('emqx_port') || '18083',
          apiKey: localStorage.getItem('emqx_api_key') || '',
          secretKey: localStorage.getItem('emqx_secret_key') || ''
        };
      } catch (e) {
        debugLogger.warn('无法从localStorage加载EMQX配置:', e);
      }
    }

    return {
      host: '127.0.0.1',
      port: '18083',
      apiKey: '',
      secretKey: ''
    };
  }

  updateConfig(config) {
    this.emqxConfig = { ...this.emqxConfig, ...config };

    if (typeof window !== 'undefined') {
      try {
        Object.entries(config).forEach(([key, value]) => {
          localStorage.setItem(`emqx_${key}`, String(value));
        });
      } catch (e) {
        debugLogger.warn('无法保存EMQX配置到localStorage:', e);
      }
    }

    debugLogger.info('EMQX配置已更新:', this.emqxConfig);
  }

  async scanDevices() {
    if (!this.emqxConfig.host || !this.emqxConfig.apiKey || !this.emqxConfig.secretKey) {
      debugLogger.warn('EMQX配置不完整，无法扫描设备');
      return [];
    }

    try {
      const queryParams = new URLSearchParams({
        host: this.emqxConfig.host,
        port: this.emqxConfig.port,
        apiKey: this.emqxConfig.apiKey,
        secretKey: this.emqxConfig.secretKey
      });

      const response = await fetch(`/api/emqx-clients?${queryParams}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      const deviceList = data.clientIds || [];
      this.lastScanResult = deviceList;

      debugLogger.info('[DeviceScanner]', `设备扫描完成，发现 ${deviceList.length} 个设备:`, deviceList);

      if (this.onDevicesFound) {
        this.onDevicesFound(deviceList);
      }

      return deviceList;

    } catch (error) {
      debugLogger.error('设备扫描失败:', error);
      return [];
    }
  }

  startScanning(callback = null) {
    if (this.isScanning) {
      debugLogger.warn('设备扫描已在进行中');
      return;
    }

    if (callback) {
      this.onDevicesFound = callback;
    }

    this.isScanning = true;

    // 立即执行一次扫描
    this.scanDevices();

    // 设置定时扫描
    this.scanInterval = setInterval(() => {
      this.scanDevices();
    }, this.intervalMs);

    debugLogger.info(`设备扫描已启动，间隔: ${this.intervalMs}ms`);
  }

  stopScanning() {
    if (!this.isScanning) {
      return;
    }

    this.isScanning = false;

    if (this.scanInterval) {
      clearInterval(this.scanInterval);
      this.scanInterval = null;
    }

    debugLogger.info('设备扫描已停止');
  }

  getLastScanResult() {
    return [...this.lastScanResult];
  }

  setInterval(ms) {
    this.intervalMs = ms;
    if (this.isScanning) {
      this.stopScanning();
      this.startScanning();
    }
  }

  getConfig() {
    return { ...this.emqxConfig };
  }
}

// 设备管理器
class DeviceManager {
  constructor() {
    this.devices = new Map();
    this.deviceAliases = new Map();
    this.scanner = new DeviceScanner();
    this.eventListeners = new Set();

    this._loadAliases();
    this._initScanner();
  }

  _initScanner() {
    this.scanner.onDevicesFound = (deviceList) => {
      this._updateDeviceList(deviceList);
    };
  }

  _updateDeviceList(deviceList) {
    const currentTime = Date.now();
    const newDevices = new Set(deviceList);
    const oldDevices = new Set(this.devices.keys());

    // 添加新设备
    for (const sn of newDevices) {
      if (!this.devices.has(sn)) {
        this.devices.set(sn, {
          sn: sn,
          alias: this.deviceAliases.get(sn) || '',
          lastSeen: currentTime,
          status: 'online',
          firstSeen: currentTime
        });
        this._notifyListeners('device-added', { sn });
        debugLogger.info('[DeviceManager]', `新设备发现: ${sn}`);
      } else {
        // 更新已存在设备的最后见时间
        const device = this.devices.get(sn);
        device.lastSeen = currentTime;
        device.status = 'online';
      }
    }

    // 标记离线设备并断开MQTT连接
    for (const sn of oldDevices) {
      if (!newDevices.has(sn)) {
        const device = this.devices.get(sn);
        if (device && device.status !== 'offline') {
          device.status = 'offline';
          this._notifyListeners('device-offline', { sn });
          debugLogger.info('[DeviceManager]', `设备离线: ${sn}`);

          // 自动断开MQTT连接
          this._disconnectMqttForOfflineDevice(sn);
        }
      }
    }

    this._notifyListeners('devices-updated', {
      devices: this.getDeviceList(),
      online: deviceList.length
    });
  }

  async _disconnectMqttForOfflineDevice(sn) {
    try {
      // 延迟加载避免循环依赖
      if (typeof window !== 'undefined' && window.mqttManager) {
        window.mqttManager.disconnectDevice(sn);
        debugLogger.info('[DeviceManager]', `设备 ${sn} MQTT连接已自动断开`);
      }
    } catch (error) {
      debugLogger.error('[DeviceManager]', `断开设备 ${sn} MQTT连接失败:`, error);
    }
  }

  startScanning() {
    this.scanner.startScanning();
  }

  stopScanning() {
    this.scanner.stopScanning();
  }

  // 用于测试的单次扫描方法
  async scan() {
    const deviceList = await this.scanner.scanDevices();
    this._updateDeviceList(deviceList);
    return deviceList;
  }

  getDeviceList() {
    return Array.from(this.devices.values()).map(device => ({
      ...device,
      alias: this.deviceAliases.get(device.sn) || ''
    }));
  }

  getOnlineDevices() {
    return this.getDeviceList().filter(device => device.status === 'online');
  }

  getDevice(sn) {
    const device = this.devices.get(sn);
    return device ? {
      ...device,
      alias: this.deviceAliases.get(sn) || ''
    } : null;
  }

  removeDevice(sn) {
    if (this.devices.has(sn)) {
      this.devices.delete(sn);
      this._notifyListeners('device-removed', { sn });
      debugLogger.info(`设备已移除: ${sn}`);
      return true;
    }
    return false;
  }

  setDeviceAlias(sn, alias) {
    this.deviceAliases.set(sn, alias);
    this._saveAliases();
    this._notifyListeners('device-alias-changed', { sn, alias });
    debugLogger.info('[DeviceManager]', `设备别名已更新: ${sn} -> ${alias}`);
  }

  getDeviceAlias(sn) {
    return this.deviceAliases.get(sn) || '';
  }

  _loadAliases() {
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('device_aliases');
        if (stored) {
          const aliases = JSON.parse(stored);
          this.deviceAliases = new Map(Object.entries(aliases));
          debugLogger.debug('[DeviceManager]', '设备别名已加载');
        }
      } catch (e) {
        debugLogger.warn('[DeviceManager]', '无法加载设备别名:', e);
      }
    }
  }

  _saveAliases() {
    if (typeof window !== 'undefined') {
      try {
        const aliases = Object.fromEntries(this.deviceAliases);
        localStorage.setItem('device_aliases', JSON.stringify(aliases));
      } catch (e) {
        debugLogger.warn('[DeviceManager]', '无法保存设备别名:', e);
      }
    }
  }

  addListener(callback) {
    this.eventListeners.add(callback);
    return () => this.eventListeners.delete(callback);
  }

  _notifyListeners(eventType, data) {
    this.eventListeners.forEach((listener, index) => {
      try {
        listener(eventType, data);
      } catch (error) {
        debugLogger.error('[DeviceManager]', '设备管理器事件监听器错误:', {
          listenerIndex: index,
          eventType,
          error: error.message || error.toString(),
          stack: error.stack
        });
      }
    });
  }

  updateEmqxConfig(config) {
    this.scanner.updateConfig(config);
  }

  getEmqxConfig() {
    return this.scanner.getConfig();
  }

  getScannerStats() {
    return {
      isScanning: this.scanner.isScanning,
      intervalMs: this.scanner.intervalMs,
      lastScanResult: this.scanner.getLastScanResult(),
      totalDevices: this.devices.size,
      onlineDevices: this.getOnlineDevices().length
    };
  }

  cleanup() {
    this.stopScanning();
    this.devices.clear();
    this.eventListeners.clear();
  }
}

// 全局实例
const deviceManager = new DeviceManager();

// 浏览器全局变量
if (typeof window !== 'undefined') {
  window.deviceManager = deviceManager;
}

export { DeviceScanner, DeviceManager, deviceManager };
export default deviceManager;