/**
 * MQTT连接池管理器
 * 全局管理所有设备的MQTT连接
 */

import { MqttClientWrapper } from './mqtt-client-wrapper.js';
import { MQTT_CONFIG, MqttConnectionState } from '@/shared/config/mqtt-config.js';
import deviceContext from '@/shared/core/device-context.js';
import deviceManager from './device-manager.js';

/**
 * MQTT连接池管理器类
 */
class MqttConnectionManager {
  constructor() {
    this.connections = new Map(); // SN -> MqttClientWrapper
    this.config = null;
    this.autoConnectEnabled = true;
    this.initialized = false;
    this.cleanupTimer = null; // 清理延迟定时器

    console.log('[MQTT连接管理器] 已创建');
  }

  /**
   * 初始化管理器
   */
  init() {
    if (this.initialized) {
      console.warn('[MQTT连接管理器] 已初始化，跳过');
      return;
    }

    // 加载配置
    this.loadConfig();

    // 监听设备切换事件
    deviceContext.addListener((currentSN, previousSN) => {
      this.onDeviceChanged(currentSN, previousSN);
    });

    // 监听设备上下线
    deviceManager.addListener(() => {
      this.onDevicesUpdated();
    });

    this.initialized = true;
    console.log('[MQTT连接管理器] ✓ 初始化完成');
  }

  /**
   * 加载配置
   * @private
   */
  loadConfig() {
    this.config = MQTT_CONFIG.getConnectionConfig();
    console.log('[MQTT连接管理器] 配置已加载:', this.config);
  }

  /**
   * 更新配置
   * @param {Object} newConfig - 新配置
   */
  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
    MQTT_CONFIG.saveConnectionConfig(this.config);
    console.log('[MQTT连接管理器] 配置已更新:', this.config);

    // 重连所有现有连接（使用新配置）
    // 暂不实现，避免频繁重连
  }

  /**
   * 设备切换时的处理
   * @private
   */
  async onDeviceChanged(currentSN, previousSN) {
    console.log(`[MQTT连接管理器] 设备切换: ${previousSN || 'null'} → ${currentSN || 'null'}`);

    if (!currentSN) {
      return;
    }

    // 自动为新选中的设备创建连接
    if (this.autoConnectEnabled) {
      await this.ensureConnection(currentSN);
    }
  }

  /**
   * 设备列表更新时的处理
   * @private
   */
  async onDevicesUpdated() {
    const devices = deviceManager.getDevices();
    const onlineDevices = devices.filter(d => d.online).map(d => d.sn);

    // 检查离线设备，断开其连接
    for (const [sn, connection] of this.connections) {
      if (!onlineDevices.includes(sn)) {
        console.log(`[MQTT连接管理器] 设备 ${sn} 已离线，断开连接`);
        this.disconnect(sn);
      }
    }

    // 检查当前focus的设备是否有连接，如果没有则建立
    const currentSN = deviceContext.getCurrentDevice();
    if (currentSN && onlineDevices.includes(currentSN)) {
      const connection = this.connections.get(currentSN);
      if (!connection || !connection.isConnected()) {
        console.log(`[MQTT连接管理器] 当前设备 ${currentSN} 无连接，尝试建立...`);
        await this.ensureConnection(currentSN);
      }
    }
  }

  /**
   * 确保设备有连接（如果没有则创建）
   * @param {string} sn - 设备SN
   * @returns {Promise<MqttClientWrapper|null>}
   */
  async ensureConnection(sn) {
    if (!sn) {
      console.error('[MQTT连接管理器] SN为空，无法创建连接');
      return null;
    }

    // 如果已有连接且已连接，直接返回
    if (this.connections.has(sn)) {
      const connection = this.connections.get(sn);
      if (connection.isConnected()) {
        console.log(`[MQTT连接管理器] 设备 ${sn} 已有活动连接`);
        return connection;
      }
    }

    // 创建新连接
    return await this.connect(sn);
  }

  /**
   * 为设备创建MQTT连接
   * @param {string} sn - 设备SN
   * @returns {Promise<MqttClientWrapper|null>}
   */
  async connect(sn) {
    if (!sn) {
      console.error('[MQTT连接管理器] SN为空，无法连接');
      return null;
    }

    // 如果已有连接，先断开
    if (this.connections.has(sn)) {
      const existing = this.connections.get(sn);
      if (existing.isConnected() || existing.isConnecting()) {
        console.log(`[MQTT连接管理器] 设备 ${sn} 已有连接，跳过`);
        return existing;
      }
      await existing.disconnect();
    }

    console.log(`[MQTT连接管理器] 正在为设备 ${sn} 创建连接...`);

    try {
      // 创建客户端封装
      const client = new MqttClientWrapper(sn, this.config);
      this.connections.set(sn, client);

      // 连接
      const success = await client.connect();

      if (success) {
        console.log(`[MQTT连接管理器] ✓ 设备 ${sn} 连接成功`);
        return client;
      } else {
        console.error(`[MQTT连接管理器] ✗ 设备 ${sn} 连接失败`);
        this.connections.delete(sn);
        return null;
      }

    } catch (error) {
      console.error(`[MQTT连接管理器] ✗ 设备 ${sn} 连接异常:`, error);
      this.connections.delete(sn);
      return null;
    }
  }

  /**
   * 断开设备的MQTT连接
   * @param {string} sn - 设备SN
   * @returns {Promise<void>}
   */
  async disconnect(sn) {
    if (!this.connections.has(sn)) {
      console.log(`[MQTT连接管理器] 设备 ${sn} 无连接`);
      return;
    }

    console.log(`[MQTT连接管理器] 正在断开设备 ${sn} 的连接...`);

    const connection = this.connections.get(sn);
    await connection.disconnect();
    this.connections.delete(sn);

    console.log(`[MQTT连接管理器] ✓ 设备 ${sn} 连接已断开`);
  }

  /**
   * 断开所有连接
   * @returns {Promise<void>}
   */
  async disconnectAll() {
    console.log(`[MQTT连接管理器] 正在断开所有连接...`);

    const promises = Array.from(this.connections.keys()).map(sn =>
      this.disconnect(sn)
    );

    await Promise.all(promises);
    console.log(`[MQTT连接管理器] ✓ 所有连接已断开`);
  }

  /**
   * 获取设备的连接
   * @param {string} sn - 设备SN（可选，默认当前设备）
   * @returns {MqttClientWrapper|null}
   */
  getConnection(sn = null) {
    const targetSN = sn || deviceContext.getCurrentDevice();

    if (!targetSN) {
      console.warn('[MQTT连接管理器] 没有指定SN且无当前设备');
      return null;
    }

    return this.connections.get(targetSN) || null;
  }

  /**
   * 获取当前设备的连接
   * @returns {MqttClientWrapper|null}
   */
  getCurrentConnection() {
    return this.getConnection();
  }

  /**
   * 获取所有连接
   * @returns {Map<string, MqttClientWrapper>}
   */
  getAllConnections() {
    return new Map(this.connections);
  }

  /**
   * 获取连接统计
   * @returns {Object}
   */
  getStats() {
    const stats = {
      total: this.connections.size,
      connected: 0,
      connecting: 0,
      disconnected: 0,
      error: 0
    };

    for (const connection of this.connections.values()) {
      const state = connection.getState();

      switch (state) {
        case MqttConnectionState.CONNECTED:
          stats.connected++;
          break;
        case MqttConnectionState.CONNECTING:
        case MqttConnectionState.RECONNECTING:
          stats.connecting++;
          break;
        case MqttConnectionState.ERROR:
          stats.error++;
          break;
        default:
          stats.disconnected++;
      }
    }

    return stats;
  }

  /**
   * 获取所有连接信息
   * @returns {Array}
   */
  getConnectionsInfo() {
    return Array.from(this.connections.values()).map(conn => conn.getInfo());
  }

  /**
   * 设置是否自动连接
   * @param {boolean} enabled
   */
  setAutoConnect(enabled) {
    this.autoConnectEnabled = enabled;
    console.log(`[MQTT连接管理器] 自动连接: ${enabled ? '启用' : '禁用'}`);
  }

  /**
   * 发布消息到指定设备
   * @param {string} sn - 设备SN
   * @param {string} topic - 主题
   * @param {string|Object} payload - 消息内容
   * @param {Object} options - 发布选项
   * @returns {Promise<boolean>}
   */
  async publish(sn, topic, payload, options = {}) {
    const connection = this.getConnection(sn);

    if (!connection) {
      console.error(`[MQTT连接管理器] 设备 ${sn} 无连接`);
      return false;
    }

    return await connection.publish(topic, payload, options);
  }

  /**
   * 订阅指定设备的主题
   * @param {string} sn - 设备SN
   * @param {string} topic - 主题
   * @param {Function} handler - 消息处理器
   * @param {Object} options - 订阅选项
   */
  subscribe(sn, topic, handler, options = {}) {
    const connection = this.getConnection(sn);

    if (!connection) {
      console.error(`[MQTT连接管理器] 设备 ${sn} 无连接`);
      return;
    }

    connection.subscribe(topic, handler, options);
  }

  /**
   * 清理（页面卸载时调用）
   * 延迟1秒断开连接，以应对用户误刷新的情况
   */
  async cleanup() {
    console.log('[MQTT连接管理器] 页面即将卸载，延迟1秒后断开连接...');

    // 取消之前的清理定时器（如果有）
    if (this.cleanupTimer) {
      clearTimeout(this.cleanupTimer);
    }

    // 设置1秒延迟
    this.cleanupTimer = setTimeout(async () => {
      console.log('[MQTT连接管理器] 开始清理连接...');
      await this.disconnectAll();
      this.connections.clear();
      this.initialized = false;
      console.log('[MQTT连接管理器] ✓ 清理完成');
    }, 1000);
  }

  /**
   * 取消清理（页面恢复时调用）
   * 如果页面在1秒内重新加载，取消清理操作
   */
  cancelCleanup() {
    if (this.cleanupTimer) {
      clearTimeout(this.cleanupTimer);
      this.cleanupTimer = null;
      console.log('[MQTT连接管理器] 清理已取消，保持现有连接');
    }
  }
}

// 创建全局单例
const mqttConnectionManager = new MqttConnectionManager();

// 暴露到window对象供Cards使用
if (typeof window !== 'undefined') {
  window.mqttManager = mqttConnectionManager;
}

export default mqttConnectionManager;
