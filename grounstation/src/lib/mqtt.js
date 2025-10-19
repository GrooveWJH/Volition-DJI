// DJI Ground Station - MQTT连接管理
import debugLogger from './debug.js';

class MQTTClientWrapper {
  constructor(clientId, brokerConfig) {
    this.clientId = clientId;
    this.brokerConfig = brokerConfig;
    this.client = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = Infinity; // 无限重连
    this.reconnectInterval = 3000;
    this.subscriptions = new Map();
    this.messageQueue = [];
    this.isReconnecting = false;
    this.messageRouter = null;
    this.manualDisconnect = false; // 标记是否为手动断开
  }

  async connect() {
    if (this.isConnected || this.isReconnecting) return true;

    // ✅ 如果 MQTT.js 客户端已存在，说明正在自动重连，不要重复创建
    if (this.client) {
      debugLogger.mqtt(`[${this.clientId}] MQTT客户端已存在，等待自动重连...`);
      // 等待现有客户端重连成功
      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          resolve(false);
        }, 10000);

        this.client.once('connect', () => {
          clearTimeout(timeout);
          resolve(true);
        });

        this.client.once('error', () => {
          clearTimeout(timeout);
          resolve(false);
        });
      });
    }

    this.isReconnecting = true;

    try {
      // 确保在浏览器环境中加载MQTT库
      let mqtt;

      if (typeof window !== 'undefined') {
        // 浏览器环境：直接从全局对象获取或动态加载
        if (window.mqtt) {
          mqtt = window.mqtt;
        } else {
          // 动态加载MQTT库
          mqtt = (await import('mqtt')).default;
        }
      } else {
        // Node.js环境
        mqtt = (await import('mqtt')).default;
      }
      const brokerUrl = `ws://${this.brokerConfig.host}:${this.brokerConfig.port}/mqtt`;
      debugLogger.mqtt(`[${this.clientId}] 正在连接`, { brokerUrl });

      this.client = mqtt.connect(brokerUrl, {
        clientId: this.clientId,
        username: this.brokerConfig.username,
        password: this.brokerConfig.password,
        keepalive: 60,
        connectTimeout: 30000,
        reconnectPeriod: 5000, // 启用MQTT.js自动重连，每5秒尝试一次
        clean: true
      });

      this.client.on('connect', () => {
        this.isConnected = true;
        this.isReconnecting = false;
        this.reconnectAttempts = 0;
        debugLogger.mqtt(`[MQTTClient-${this.clientId}]`, 'MQTT连接成功');
        console.log(`[MQTT] ✓ ${this.clientId} 已连接到 ${brokerUrl}`);
        this._restoreSubscriptions();
        this._processMessageQueue();

        // 触发全局事件通知UI更新
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('mqtt-connection-changed', {
            detail: {
              clientId: this.clientId,
              isConnected: true,
              event: 'connected'
            }
          }));
        }
      });

      this.client.on('message', (topic, message) => {
        console.log(`[MQTT] ✓ ${this.clientId} 收到消息: topic=${topic}, length=${message.length}`);
        this._handleMessage(topic, message);
      });

      this.client.on('error', (error) => {
        debugLogger.error(`[MQTTClient-${this.clientId}]`, 'MQTT连接错误:', error);
        this.isConnected = false;
        this.isReconnecting = false;
      });

      this.client.on('close', () => {
        this.isConnected = false;
        if (this.manualDisconnect) {
          debugLogger.info(`[MQTTClient-${this.clientId}]`, 'MQTT手动断开连接');
        } else {
          debugLogger.warn(`[MQTTClient-${this.clientId}]`, 'MQTT连接意外关闭，MQTT.js将自动重连');
        }

        // 触发全局事件通知UI更新
        if (typeof window !== 'undefined' && !this.manualDisconnect) {
          window.dispatchEvent(new CustomEvent('mqtt-connection-changed', {
            detail: {
              clientId: this.clientId,
              isConnected: false,
              event: 'disconnected'
            }
          }));
        }
      });

      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          this.isReconnecting = false;
          resolve(false);
        }, 10000);

        this.client.once('connect', () => {
          clearTimeout(timeout);
          resolve(true);
        });

        this.client.once('error', () => {
          clearTimeout(timeout);
          this.isReconnecting = false;
          resolve(false);
        });
      });

    } catch (error) {
      debugLogger.error(`[${this.clientId}] MQTT初始化失败:`, error);
      this.isReconnecting = false;
      return false;
    }
  }

  async _handleMessage(topic, message) {
    try {
      debugLogger.mqtt(`[${this.clientId}] _handleMessage 收到消息`, { topic, length: message.length });

      // 1. 先调用订阅回调（如果有的话）
      for (const [subscribedTopic, callback] of this.subscriptions) {
        if (topic === subscribedTopic || topic.match(new RegExp(subscribedTopic.replace('+', '[^/]+').replace('#', '.*')))) {
          if (callback && typeof callback === 'function') {
            debugLogger.mqtt(`[${this.clientId}] 触发订阅回调`, { topic: subscribedTopic });
            try {
              callback(topic, message);
            } catch (err) {
              debugLogger.error(`[${this.clientId}] 订阅回调执行失败:`, err);
            }
          }
        }
      }

      // 2. 然后调用 messageRouter
      if (!this.messageRouter) {
        const module = await import('./services.js');
        this.messageRouter = module.getMessageRouter();
      }

      const parsedMessage = JSON.parse(message.toString());
      const sn = this._extractSNFromTopic(topic);

      if (this.messageRouter?.routeMessage) {
        this.messageRouter.routeMessage(parsedMessage, topic, sn);
      }

      // 消息继续传播到其他监听器（不阻止）
      debugLogger.mqtt(`[${this.clientId}] _handleMessage 处理完成，消息已路由`);
    } catch (error) {
      debugLogger.error(`[${this.clientId}] 消息处理失败:`, error);
    }
  }

  _extractSNFromTopic(topic) {
    const match = topic.match(/\/([A-Z0-9]{14})\//);
    return match ? match[1] : null;
  }

  subscribe(topic, callback = null) {
    debugLogger.mqtt(`[${this.clientId}] subscribe 被调用`, { topic, isConnected: this.isConnected });

    if (!this.isConnected) {
      debugLogger.warn(`[${this.clientId}] 连接未建立，订阅请求已排队: ${topic}`);
      this.subscriptions.set(topic, callback);
      return false;
    }

    this.client.subscribe(topic, { qos: 0 }, (err) => {
      if (err) {
        debugLogger.error(`[MQTTClient-${this.clientId}]`, '订阅失败:', topic, err);
        console.error(`[MQTT] ✗ 订阅失败: ${topic}`, err);
      } else {
        debugLogger.mqtt(`[MQTTClient-${this.clientId}]`, '✓ 订阅成功:', topic);
        console.log(`[MQTT] ✓ ${this.clientId} 订阅成功: ${topic}`);
        this.subscriptions.set(topic, callback);
      }
    });
    return true;
  }

  async publish(topic, message, options = {}) {
    const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
    const qos = options.qos !== undefined ? options.qos : 1;  // 默认QoS=1（与Python一致）

    if (!this.isConnected) {
      this.messageQueue.push({ topic, message: messageStr, qos });
      debugLogger.warn(`[${this.clientId}] 连接未建立，消息已排队: ${topic}`);
      return false;
    }

    return new Promise((resolve) => {
      this.client.publish(topic, messageStr, { qos }, (err) => {
        if (err) {
          debugLogger.error(`[${this.clientId}] 发布失败: ${topic}`, err);
          resolve(false);
        } else {
          debugLogger.mqtt(`[${this.clientId}] 发布成功: ${topic} (QoS=${qos})`);
          resolve(true);
        }
      });
    });
  }

  _restoreSubscriptions() {
    for (const [topic, callback] of this.subscriptions) {
      this.subscribe(topic, callback);
    }
  }

  _processMessageQueue() {
    while (this.messageQueue.length > 0) {
      const { topic, message, qos } = this.messageQueue.shift();
      this.publish(topic, message, { qos: qos || 1 });
    }
  }

  // 已移除手动重连逻辑，使用MQTT.js内置的自动重连
  // MQTT.js会在连接断开时自动重连，无需手动管理

  disconnect() {
    this.manualDisconnect = true; // 标记为手动断开
    if (this.client) {
      this.client.end();
      this.client = null;
    }
    this.isConnected = false;
    this.subscriptions.clear();
    this.messageQueue = [];
  }

  getConnectionInfo() {
    return {
      clientId: this.clientId,
      isConnected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
      subscriptions: Array.from(this.subscriptions.keys()),
      queuedMessages: this.messageQueue.length
    };
  }
}

class MQTTConnectionManager {
  constructor() {
    this.connections = new Map();
    this.heartbeatConnections = new Map(); // 心跳专用连接
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
          debugLogger.info('[MQTTConnectionManager]', `设备切换到: ${data.currentSN}，准备建立MQTT连接`);
          this.ensureConnection(data.currentSN);
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

  async ensureConnection(sn) {
    if (!sn) return null;

    // Check if connection object already exists in Map
    if (this.connections.has(sn)) {
      const connection = this.connections.get(sn);

      // If connected, return directly
      if (connection.isConnected) return connection;

      // ✅ KEY FIX: If disconnected, REUSE the same object and reconnect
      // This prevents creating duplicate client_id and causing broker conflicts
      debugLogger.mqtt(`[MQTTConnectionManager]`, `设备 ${sn} 连接已断开，复用现有Wrapper重连...`);
      const success = await connection.connect();
      if (success) {
        debugLogger.mqtt(`[MQTTConnectionManager]`, `设备 ${sn} MQTT连接已重建立`);
        this._subscribeDefaultTopics(connection, sn);
        return connection;
      } else {
        debugLogger.error(`设备 ${sn} MQTT重连失败`);
        return null;
      }
    }

    // Create new connection object only on first connection
    const clientId = `station-${sn}`;
    const connection = new MQTTClientWrapper(clientId, this.brokerConfig);

    const success = await connection.connect();
    if (success) {
      this.connections.set(sn, connection);
      debugLogger.mqtt(`[MQTTConnectionManager]`, `设备 ${sn} MQTT连接已建立`);
      this._subscribeDefaultTopics(connection, sn);
      return connection;
    } else {
      debugLogger.error(`设备 ${sn} MQTT连接失败`);
      return null;
    }
  }

  _subscribeDefaultTopics(connection, sn) {
    const defaultTopics = [
      `thing/product/${sn}/services_reply`,
      `thing/product/${sn}/events`,
      `thing/product/${sn}/drc/up`
    ];
    defaultTopics.forEach(topic => connection.subscribe(topic));
  }

  getCurrentConnection() {
    if (!this.deviceContext) return null;
    const currentSN = this.deviceContext.getCurrentDevice();
    return currentSN ? this.connections.get(currentSN) : null;
  }

  getConnection(sn) {
    return this.connections.get(sn);
  }

  /**
   * 获取或创建心跳专用连接
   * 使用 heart-{sn} 作为 client_id，与长连接分离
   */
  async ensureHeartbeatConnection(sn) {
    if (!sn) return null;

    // Check if heartbeat connection object already exists in Map
    if (this.heartbeatConnections.has(sn)) {
      const connection = this.heartbeatConnections.get(sn);

      // If connected, return directly
      if (connection.isConnected) return connection;

      // ✅ REUSE existing object and reconnect
      debugLogger.mqtt(`[MQTTConnectionManager]`, `设备 ${sn} 心跳连接已断开，复用现有Wrapper重连...`);
      const success = await connection.connect();
      if (success) {
        debugLogger.mqtt(`[MQTTConnectionManager]`, `设备 ${sn} 心跳连接已重建立 (${connection.clientId})`);
        connection.subscribe(`thing/product/${sn}/drc/up`);
        return connection;
      } else {
        debugLogger.error(`设备 ${sn} 心跳连接重连失败`);
        return null;
      }
    }

    // Create new connection object only on first connection
    const clientId = `heart-${sn}`;
    const connection = new MQTTClientWrapper(clientId, this.brokerConfig);

    const success = await connection.connect();
    if (success) {
      this.heartbeatConnections.set(sn, connection);
      debugLogger.mqtt(`[MQTTConnectionManager]`, `设备 ${sn} 心跳连接已建立 (${clientId})`);

      // 心跳连接订阅心跳回复topic
      connection.subscribe(`thing/product/${sn}/drc/up`);
      return connection;
    } else {
      debugLogger.error(`设备 ${sn} 心跳连接失败`);
      return null;
    }
  }

  /**
   * 获取心跳连接（不自动创建）
   */
  getHeartbeatConnection(sn) {
    return this.heartbeatConnections.get(sn);
  }

  async publish(sn, topic, message) {
    const connection = await this.ensureConnection(sn);
    return connection ? connection.publish(topic, message) : false;
  }

  subscribe(sn, topic, callback) {
    const connection = this.connections.get(sn);
    return connection ? connection.subscribe(topic, callback) : false;
  }

  disconnectDevice(sn) {
    // 断开主连接
    const connection = this.connections.get(sn);
    if (connection) {
      connection.disconnect();
      this.connections.delete(sn);
      debugLogger.mqtt(`设备 ${sn} MQTT连接已断开`);
    }

    // 断开心跳连接
    const heartbeatConnection = this.heartbeatConnections.get(sn);
    if (heartbeatConnection) {
      heartbeatConnection.disconnect();
      this.heartbeatConnections.delete(sn);
      debugLogger.mqtt(`设备 ${sn} 心跳连接已断开`);
    }
  }

  /**
   * 仅断开心跳连接，保留主连接
   */
  disconnectHeartbeat(sn) {
    const heartbeatConnection = this.heartbeatConnections.get(sn);
    if (heartbeatConnection) {
      heartbeatConnection.disconnect();
      this.heartbeatConnections.delete(sn);
      debugLogger.mqtt(`设备 ${sn} 心跳连接已断开`);
    }
  }

  disconnectAll() {
    // 断开所有主连接
    for (const [, connection] of this.connections) {
      connection.disconnect();
    }
    this.connections.clear();

    // 断开所有心跳连接
    for (const [, connection] of this.heartbeatConnections) {
      connection.disconnect();
    }
    this.heartbeatConnections.clear();

    debugLogger.mqtt('所有MQTT连接已断开');
  }

  getStats() {
    const stats = {
      totalConnections: this.connections.size,
      activeConnections: 0,
      connections: {}
    };

    for (const [sn, connection] of this.connections) {
      const info = connection.getConnectionInfo();
      stats.connections[sn] = info;
      if (info.isConnected) stats.activeConnections++;
    }

    return stats;
  }

  getConnectionsInfo() {
    const info = {};
    for (const [sn, connection] of this.connections) {
      info[sn] = connection.getConnectionInfo();
    }
    return info;
  }

  getBrokerConfig() {
    return { ...this.brokerConfig };
  }
}

const mqttManager = new MQTTConnectionManager();

if (typeof window !== 'undefined') {
  window.mqttManager = mqttManager;
}

export { MQTTClientWrapper, MQTTConnectionManager, mqttManager };
export default mqttManager;
