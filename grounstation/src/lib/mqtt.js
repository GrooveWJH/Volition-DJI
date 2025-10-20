// DJI Ground Station - MQTT连接管理
// 极简版本 - 遵循 "stupid and simple" 原则
import debugLogger from './debug.js';

/**
 * MQTT连接管理器
 *
 * 设计原则:
 * 1. 直接使用 MQTT.js Client，不包装
 * 2. getConnection() 幂等：总是返回同一个对象
 * 3. 信任 MQTT.js 自动重连机制
 * 4. 单一真相源：client.connected
 * 5. 事件监听器只注册一次
 */
class MQTTConnectionManager {
  constructor() {
    this.clients = new Map(); // SN -> MQTT.js Client
    this.heartbeatClients = new Map(); // SN -> MQTT.js Client (心跳专用)
    this.connectionStates = new Map(); // SN -> Boolean (上次通知UI的连接状态)
    this.brokerConfig = this._getDefaultConfig();
    this.deviceContext = null;
    this._initDeviceContext();
  }

  async _initDeviceContext() {
    try {
      const module = await import('./state.js');
      this.deviceContext = module.deviceContext;
      this.deviceContext.addListener((eventType, data) => {
        if (eventType === 'device-changed' && data.currentSN) {
          debugLogger.info('[MQTTConnectionManager]', `设备切换到: ${data.currentSN}`);
          // 确保连接存在（幂等）
          this.getConnection(data.currentSN);
        }
      });
    } catch (error) {
      debugLogger.error('[MQTTConnectionManager]', '初始化设备上下文失败:', error);
    }
  }

  _getDefaultConfig() {
    if (typeof window !== 'undefined') {
      try {
        return {
          host: localStorage.getItem('mqtt_broker_host') || '127.0.0.1',
          port: parseInt(localStorage.getItem('mqtt_broker_port')) || 8083,
          username: localStorage.getItem('mqtt_broker_username') || '',
          password: localStorage.getItem('mqtt_broker_password') || ''
        };
      } catch (e) {
        debugLogger.warn('无法从localStorage加载MQTT配置:', e);
      }
    }

    return { host: '127.0.0.1', port: 8083, username: '', password: '' };
  }

  updateBrokerConfig(config) {
    this.brokerConfig = { ...this.brokerConfig, ...config };

    if (typeof window !== 'undefined') {
      try {
        Object.entries(config).forEach(([key, value]) => {
          localStorage.setItem(`mqtt_broker_${key}`, String(value));
        });
      } catch (e) {
        debugLogger.warn('无法保存MQTT配置到localStorage:', e);
      }
    }

    debugLogger.info('MQTT配置已更新:', this.brokerConfig);
  }

  /**
   * 获取或创建连接（幂等操作）
   * - 如果连接已存在，直接返回
   * - 如果不存在，创建新连接
   * - MQTT.js 会自动处理连接和重连
   */
  getConnection(sn) {
    if (!sn) return null;

    // 如果已存在，直接返回
    if (this.clients.has(sn)) {
      return this.clients.get(sn);
    }

    // 第一次创建连接
    const clientId = `station-${sn}`;
    const client = this._createConnection(sn, clientId, this.clients);

    debugLogger.mqtt(`[${clientId}] 连接已创建（MQTT.js将自动连接）`);
    return client;
  }

  /**
   * 获取或创建心跳专用连接（幂等操作）
   */
  getHeartbeatConnection(sn) {
    if (!sn) return null;

    // 如果已存在，直接返回
    if (this.heartbeatClients.has(sn)) {
      return this.heartbeatClients.get(sn);
    }

    // 第一次创建连接
    const clientId = `heart-${sn}`;
    const client = this._createConnection(sn, clientId, this.heartbeatClients);

    // 心跳连接订阅心跳回复topic
    client.on('connect', () => {
      client.subscribe(`thing/product/${sn}/drc/up`, { qos: 0 });
    });

    debugLogger.mqtt(`[${clientId}] 心跳连接已创建（MQTT.js将自动连接）`);
    return client;
  }

  /**
   * 创建MQTT连接（内部方法）
   * - 只在第一次调用时创建
   * - 事件监听器只注册一次
   * - 信任MQTT.js的自动重连
   */
  async _createConnection(sn, clientId, storage) {
    let mqtt;

    // 加载MQTT库
    if (typeof window !== 'undefined') {
      if (window.mqtt) {
        mqtt = window.mqtt;
      } else {
        mqtt = (await import('mqtt')).default;
      }
    } else {
      mqtt = (await import('mqtt')).default;
    }

    const brokerUrl = `ws://${this.brokerConfig.host}:${this.brokerConfig.port}/mqtt`;
    debugLogger.mqtt(`[${clientId}] 创建连接`, { brokerUrl });

    const client = mqtt.connect(brokerUrl, {
      clientId,
      username: this.brokerConfig.username,
      password: this.brokerConfig.password,
      keepalive: 60,
      connectTimeout: 30000,
      reconnectPeriod: 5000, // 信任MQTT.js自动重连
      clean: true
    });

    // ========== 事件监听器只注册一次 ==========

    client.on('connect', () => {
      debugLogger.mqtt(`[${clientId}] ✓ 已连接`);

      // 订阅默认topic（仅主连接）
      if (storage === this.clients) {
        this._subscribeDefaultTopics(client, sn);
      }

      // ✅ 只在状态真正改变时通知 UI
      const lastState = this.connectionStates.get(sn);
      if (lastState !== true) {
        this.connectionStates.set(sn, true);
        this._notifyUI(sn, true);
        debugLogger.mqtt(`[${clientId}] 状态变化: 断开 → 连接，通知UI`);
      } else {
        debugLogger.mqtt(`[${clientId}] 内部重连，状态未变化，不通知UI`);
      }
    });

    client.on('close', () => {
      debugLogger.mqtt(`[${clientId}] ✗ 连接关闭，MQTT.js将在5秒后自动重连`);

      // ✅ 只在状态真正改变时通知 UI
      const lastState = this.connectionStates.get(sn);
      if (lastState !== false) {
        this.connectionStates.set(sn, false);
        this._notifyUI(sn, false);
        debugLogger.mqtt(`[${clientId}] 状态变化: 连接 → 断开，通知UI`);
      } else {
        debugLogger.mqtt(`[${clientId}] 内部重连中，状态未变化，不通知UI`);
      }
    });

    client.on('error', (error) => {
      debugLogger.error(`[${clientId}] 连接错误:`, error);
    });

    client.on('message', (topic, message) => {
      debugLogger.mqtt(`[${clientId}] ✓ 收到消息: ${topic}`);
      this._handleMessage(topic, message, sn);
    });

    // 保存到存储
    storage.set(sn, client);
    return client;
  }

  _subscribeDefaultTopics(client, sn) {
    const topics = [
      `thing/product/${sn}/services_reply`,
      `thing/product/${sn}/events`,
      `thing/product/${sn}/drc/up`
    ];

    topics.forEach(topic => {
      client.subscribe(topic, { qos: 0 }, (err) => {
        if (err) {
          debugLogger.error(`订阅失败: ${topic}`, err);
        } else {
          debugLogger.mqtt(`✓ 订阅成功: ${topic}`);
        }
      });
    });
  }

  async _handleMessage(topic, message, sn) {
    try {
      // 1. 调用 messageRouter
      if (!this.messageRouter) {
        const module = await import('./services.js');
        this.messageRouter = module.getMessageRouter();
      }

      const parsedMessage = JSON.parse(message.toString());

      if (this.messageRouter?.routeMessage) {
        this.messageRouter.routeMessage(parsedMessage, topic, sn);
      }

      debugLogger.mqtt(`消息已路由: ${topic}`);
    } catch (error) {
      debugLogger.error('消息处理失败:', error);
    }
  }

  _notifyUI(sn, isConnected) {
    if (typeof window === 'undefined') return;

    window.dispatchEvent(new CustomEvent('mqtt-connection-changed', {
      detail: { sn, isConnected }
    }));
  }

  /**
   * 检查连接状态（单一真相源）
   * 直接读取 MQTT.js Client 的 connected 属性
   */
  isConnected(sn) {
    const client = this.clients.get(sn);
    return client && client.connected;
  }

  /**
   * 发布消息（简单粗暴）
   */
  async publish(sn, topic, message) {
    const client = this.getConnection(sn);
    if (!client) return false;

    const messageStr = typeof message === 'string' ? message : JSON.stringify(message);

    return new Promise((resolve) => {
      client.publish(topic, messageStr, { qos: 1 }, (err) => {
        if (err) {
          debugLogger.error(`[${sn}] 发布失败: ${topic}`, err);
          resolve(false);
        } else {
          debugLogger.mqtt(`[${sn}] ✓ 发布成功: ${topic}`);
          resolve(true);
        }
      });
    });
  }

  /**
   * 订阅topic
   */
  subscribe(sn, topic, callback) {
    const client = this.getConnection(sn);
    if (!client) return false;

    client.subscribe(topic, { qos: 0 }, (err) => {
      if (err) {
        debugLogger.error(`[${sn}] 订阅失败: ${topic}`, err);
      } else {
        debugLogger.mqtt(`[${sn}] ✓ 订阅成功: ${topic}`);
      }
    });

    // 如果有回调，注册消息监听
    if (callback) {
      client.on('message', (receivedTopic, message) => {
        if (receivedTopic === topic || this._topicMatch(receivedTopic, topic)) {
          callback(receivedTopic, message);
        }
      });
    }

    return true;
  }

  _topicMatch(received, pattern) {
    const regex = new RegExp(
      '^' + pattern.replace('+', '[^/]+').replace('#', '.*') + '$'
    );
    return regex.test(received);
  }

  /**
   * 断开单个设备连接
   */
  disconnectDevice(sn) {
    // 断开主连接
    const client = this.clients.get(sn);
    if (client) {
      client.end(true); // 强制关闭，不重连
      this.clients.delete(sn);
      debugLogger.mqtt(`设备 ${sn} MQTT连接已断开`);
    }

    // 断开心跳连接
    const heartbeatClient = this.heartbeatClients.get(sn);
    if (heartbeatClient) {
      heartbeatClient.end(true);
      this.heartbeatClients.delete(sn);
      debugLogger.mqtt(`设备 ${sn} 心跳连接已断开`);
    }
  }

  /**
   * 断开心跳连接（保留主连接）
   */
  disconnectHeartbeat(sn) {
    const heartbeatClient = this.heartbeatClients.get(sn);
    if (heartbeatClient) {
      heartbeatClient.end(true);
      this.heartbeatClients.delete(sn);
      debugLogger.mqtt(`设备 ${sn} 心跳连接已断开`);
    }
  }

  /**
   * 断开所有连接
   */
  disconnectAll() {
    for (const [sn, client] of this.clients) {
      client.end(true);
    }
    this.clients.clear();

    for (const [sn, client] of this.heartbeatClients) {
      client.end(true);
    }
    this.heartbeatClients.clear();

    debugLogger.mqtt('所有MQTT连接已断开');
  }

  /**
   * 清理资源
   */
  cleanup() {
    this.disconnectAll();
  }

  /**
   * 获取连接统计
   */
  getStats() {
    const stats = {
      totalConnections: this.clients.size,
      activeConnections: 0,
      connections: {}
    };

    for (const [sn, client] of this.clients) {
      stats.connections[sn] = {
        clientId: client.options.clientId,
        connected: client.connected,
        reconnecting: client.reconnecting
      };
      if (client.connected) stats.activeConnections++;
    }

    return stats;
  }

  /**
   * 获取连接信息
   */
  getConnectionsInfo() {
    const info = {};
    for (const [sn, client] of this.clients) {
      info[sn] = {
        clientId: client.options.clientId,
        connected: client.connected,
        reconnecting: client.reconnecting
      };
    }
    return info;
  }

  /**
   * 获取Broker配置
   */
  getBrokerConfig() {
    return { ...this.brokerConfig };
  }

  /**
   * 获取当前连接（便捷方法）
   */
  getCurrentConnection() {
    if (!this.deviceContext) return null;
    const currentSN = this.deviceContext.getCurrentDevice();
    return currentSN ? this.getConnection(currentSN) : null;
  }
}

const mqttManager = new MQTTConnectionManager();

if (typeof window !== 'undefined') {
  window.mqttManager = mqttManager;
}

export { MQTTConnectionManager, mqttManager };
export default mqttManager;
