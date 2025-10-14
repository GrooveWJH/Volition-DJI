/**
 * MQTT相关配置
 * 包含MQTT连接、DJI网关、DRC模式等配置
 */

import deviceContext from '@/shared/core/device-context.js';

/**
 * MQTT配置对象
 */
export const MQTT_CONFIG = {
  // 默认MQTT Broker配置
  defaultHost: '127.0.0.1',
  defaultPort: 1883,
  defaultUsername: 'admin',
  defaultPassword: 'public',

  /**
   * 获取当前选中的设备SN（从设备切换器获取）
   * @returns {string|null}
   */
  getCurrentGatewaySN() {
    return deviceContext.getCurrentDevice();
  },

  // 控制权请求配置
  controlAuth: {
    defaultUserId: 'groundstation',
    defaultUserCallsign: '地面站'
  },

  // DRC模式配置
  drcMode: {
    relayAddress: 'localhost:1883',
    relayClientId: 'drc-client',
    relayUsername: 'admin',
    relayPassword: '302811055wjhhz',
    relayExpireTime: 1_700_000_000,
    relayEnableTLS: false,
    osdFrequency: 30,
    hsiFrequency: 10,
    heartbeatFrequencyHz: 5
  },

  // 构建MQTT连接URL
  buildConnectionUrl() {
    return `mqtt://${this.defaultHost}:${this.defaultPort}`;
  },

  // 构建主题名称
  buildTopics(gatewaySN) {
    // 如果未提供gatewaySN，使用当前选中的设备
    const sn = gatewaySN || this.getCurrentGatewaySN();

    if (!sn) {
      console.warn('[MQTT_CONFIG] 没有选中的设备SN，无法构建主题');
      return null;
    }

    return {
      services: `thing/product/${sn}/services`,
      servicesReply: `thing/product/${sn}/services_reply`,
      drcUp: `thing/product/${sn}/drc/up`,
      drcDown: `thing/product/${sn}/drc/down`
    };
  }
};

/**
 * DRC配置对象
 */
export const DRC_CONFIG = {
  // 默认超时时间(秒)
  timeoutSeconds: 30,

  // 最大重试次数
  maxRetries: 3,

  // 自动重连间隔(毫秒)
  autoReconnectInterval: 5000,

  // 构建DRC授权请求参数
  buildAuthRequest(serialNumber, userId, userCallsign) {
    return {
      tid: Date.now().toString(),
      bid: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      timestamp: Math.floor(Date.now() / 1000),
      method: "drc_mode_enter",
      data: {
        user_id: userId,
        user_callsign: userCallsign,
        target_sn: serialNumber,
        entrance: 1
      }
    };
  }
};

/**
 * MQTT连接状态枚举
 */
export const MqttConnectionState = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  ERROR: 'error'
};

/**
 * DRC状态枚举
 */
export const DrcState = {
  IDLE: 'idle',
  REQUESTING: 'requesting',
  PENDING: 'pending',
  ACTIVE: 'active',
  ERROR: 'error'
};
