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
  defaultWsPort: 8083, // WebSocket端口
  defaultUsername: 'admin',
  defaultPassword: 'public',

  // 从localStorage获取配置
  getConnectionConfig() {
    return {
      host: localStorage.getItem('mqtt_broker_host') || this.defaultHost,
      port: localStorage.getItem('mqtt_broker_port') || this.defaultWsPort,
      username: localStorage.getItem('mqtt_broker_username') || this.defaultUsername,
      password: localStorage.getItem('mqtt_broker_password') || this.defaultPassword
    };
  },

  // 保存配置到localStorage
  saveConnectionConfig(config) {
    if (config.host) localStorage.setItem('mqtt_broker_host', config.host);
    if (config.port) localStorage.setItem('mqtt_broker_port', config.port);
    if (config.username) localStorage.setItem('mqtt_broker_username', config.username);
    if (config.password) localStorage.setItem('mqtt_broker_password', config.password);
  },

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
  buildConnectionUrl(config) {
    const { host, port } = config || this.getConnectionConfig();
    return `ws://${host}:${port}/mqtt`;
  },

  // 生成station的ClientID
  buildStationClientId(sn) {
    return `station-${sn}`;
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
  IDLE: 'idle',               // 未连接（初始状态）
  CONNECTING: 'connecting',   // 连接中
  CONNECTED: 'connected',     // 已连接
  RECONNECTING: 'reconnecting', // 重连中
  DISCONNECTING: 'disconnecting', // 断开连接中
  DISCONNECTED: 'disconnected',   // 已断开
  ERROR: 'error'             // 错误
};

/**
 * MQTT连接配置常量
 */
export const MQTT_CONNECTION_CONFIG = {
  // 重连配置
  reconnectPeriod: 5000,     // 重连间隔(ms)
  connectTimeout: 10000,     // 连接超时(ms)
  maxReconnectAttempts: 3,   // 最大重连次数

  // 心跳配置
  keepalive: 60,             // 心跳间隔(s)

  // 其他配置
  clean: true,               // 清除会话
  qos: 1,                    // 消息质量等级

  // 默认订阅主题（相对于设备SN）
  defaultSubscriptions: [
    'thing/product/{sn}/services_reply',
    'thing/product/{sn}/drc/down',
    'thing/product/{sn}/state'
  ]
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
