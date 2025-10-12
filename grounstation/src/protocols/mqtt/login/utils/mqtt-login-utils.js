/**
 * MQTT登录工具函数
 * 提供MQTT相关的实用工具函数
 */

/**
 * MQTT连接状态枚举
 */
export const MqttConnectionState = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  ERROR: 'error'
};

/**
 * DJI API常量配置
 */
export const DJI_CONFIG = {
  APP_ID: 171440,
  LICENSE: "krC5HsEFLzVC8xkKM38JCcSxNEQvsQ/7IoiHEJRaulGiPQildia+n/+bF+SO21pk1JTS8CfaNS+fn8qt+17i3Y7uoqtBOOsdtLUQhqPMb0DVea0dmZ7oZhdP2CuQrQSn1bobS3pQ+MW2eEOq0XCcCkpo+HxAC1r5/33yEDxc6NE=",
  APP_KEY: "b57ab1ee70f0a78e1797c592742e7d4"
};

/**
 * 默认MQTT配置
 */
export const DEFAULT_MQTT_CONFIG = {
  host: 'localhost',
  port: '1883',
  username: 'admin',
  password: 'password',
  keepalive: 60,
  cleanSession: true
};

/**
 * 格式化MQTT URL
 * @param {string} host - MQTT主机地址
 * @param {string|number} port - MQTT端口
 * @param {boolean} useSSL - 是否使用SSL
 * @returns {string} 格式化的MQTT URL
 */
export function formatMqttUrl(host, port, useSSL = false) {
  const protocol = useSSL ? 'ssl' : 'tcp';
  return `${protocol}://${host}:${port}`;
}

/**
 * 解析MQTT URL
 * @param {string} url - MQTT URL
 * @returns {Object} 解析结果
 */
export function parseMqttUrl(url) {
  try {
    const urlObj = new URL(url);
    return {
      protocol: urlObj.protocol.replace(':', ''),
      host: urlObj.hostname,
      port: urlObj.port || (urlObj.protocol === 'ssl:' ? '8883' : '1883'),
      useSSL: urlObj.protocol === 'ssl:'
    };
  } catch (error) {
    throw new Error(`无效的MQTT URL: ${url}`);
  }
}

/**
 * 验证MQTT主机地址格式
 * @param {string} host - 主机地址
 * @returns {boolean} 是否有效
 */
export function isValidMqttHost(host) {
  if (!host || typeof host !== 'string') return false;
  
  // IP地址正则
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
  // 域名正则
  const domainRegex = /^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$/;
  
  return ipRegex.test(host) || domainRegex.test(host) || host === 'localhost';
}

/**
 * 验证MQTT端口范围
 * @param {string|number} port - 端口号
 * @returns {boolean} 是否有效
 */
export function isValidMqttPort(port) {
  const portNum = parseInt(port);
  return !isNaN(portNum) && portNum >= 1 && portNum <= 65535;
}

/**
 * 生成MQTT客户端ID
 * @param {string} prefix - 前缀
 * @returns {string} 客户端ID
 */
export function generateMqttClientId(prefix = 'groundstation') {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 11);
  return `${prefix}_${timestamp}_${random}`;
}

/**
 * 格式化时间戳为可读格式
 * @param {number} timestamp - 时间戳
 * @returns {string} 格式化的时间字符串
 */
export function formatTimestamp(timestamp = Date.now()) {
  return new Date(timestamp).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

/**
 * 创建日志条目
 * @param {string} level - 日志级别 (info, warn, error)
 * @param {string} message - 日志消息
 * @param {Object} meta - 附加元数据
 * @returns {Object} 日志条目
 */
export function createLogEntry(level, message, meta = {}) {
  return {
    timestamp: Date.now(),
    level,
    message,
    meta,
    formattedTime: formatTimestamp()
  };
}

/**
 * MQTT主题工具
 */
export const MqttTopicUtils = {
  /**
   * 验证主题格式
   * @param {string} topic - MQTT主题
   * @returns {boolean} 是否有效
   */
  isValid(topic) {
    if (!topic || typeof topic !== 'string') return false;
    // MQTT主题不能包含空字符和某些特殊字符
    return !/[\u0000+#]/.test(topic) && topic.length > 0;
  },

  /**
   * 构建DJI设备主题
   * @param {string} deviceSn - 设备序列号
   * @param {string} action - 操作类型
   * @returns {string} 主题字符串
   */
  buildDeviceTopic(deviceSn) {
    return `thing/product/${deviceSn}/services`;
  },

  /**
   * 构建DJI事件主题
   * @param {string} deviceSn - 设备序列号
   * @returns {string} 主题字符串
   */
  buildEventTopic(deviceSn) {
    return `thing/product/${deviceSn}/events`;
  },

  /**
   * 解析主题层级
   * @param {string} topic - MQTT主题
   * @returns {string[]} 主题层级数组
   */
  parseTopicLevels(topic) {
    return topic.split('/').filter(level => level.length > 0);
  }
};

/**
 * 连接状态管理器
 */
export class ConnectionStatusManager {
  constructor() {
    this.status = MqttConnectionState.DISCONNECTED;
    this.lastError = null;
    this.connectTime = null;
    this.disconnectTime = null;
    this.listeners = new Set();
  }

  /**
   * 添加状态监听器
   * @param {Function} listener - 监听器函数
   */
  addListener(listener) {
    this.listeners.add(listener);
  }

  /**
   * 移除状态监听器
   * @param {Function} listener - 监听器函数
   */
  removeListener(listener) {
    this.listeners.delete(listener);
  }

  /**
   * 更新连接状态
   * @param {string} newStatus - 新状态
   * @param {Object} meta - 附加信息
   */
  updateStatus(newStatus, meta = {}) {
    const oldStatus = this.status;
    this.status = newStatus;
    
    if (newStatus === MqttConnectionState.CONNECTED) {
      this.connectTime = Date.now();
      this.lastError = null;
    } else if (newStatus === MqttConnectionState.DISCONNECTED) {
      this.disconnectTime = Date.now();
    } else if (newStatus === MqttConnectionState.ERROR) {
      this.lastError = meta.error || 'Unknown error';
    }

    // 通知所有监听器
    for (const listener of this.listeners) {
      try {
        listener(newStatus, oldStatus, meta);
      } catch (error) {
        console.error('Error in connection status listener:', error);
      }
    }
  }

  /**
   * 获取当前状态信息
   * @returns {Object} 状态信息
   */
  getStatusInfo() {
    return {
      status: this.status,
      lastError: this.lastError,
      connectTime: this.connectTime,
      disconnectTime: this.disconnectTime,
      isConnected: this.status === MqttConnectionState.CONNECTED,
      uptime: this.connectTime ? Date.now() - this.connectTime : 0
    };
  }
}