// DJI Ground Station - MQTT连接管理
import debugLogger from './debug.js';

class MQTTClientWrapper {
  constructor(clientId, brokerConfig) {
    this.clientId = clientId;
    this.brokerConfig = brokerConfig;
    this.client = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 3000;
    this.subscriptions = new Map();
    this.messageQueue = [];
    this.isReconnecting = false;
    this.messageRouter = null;
  }

  async connect() {
    if (this.isConnected || this.isReconnecting) return true;

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

      this.client = mqtt.connect(brokerUrl, {
        clientId: this.clientId,
        username: this.brokerConfig.username,
        password: this.brokerConfig.password,
        keepalive: 60,
        connectTimeout: 30000,
        reconnectPeriod: 0,
        clean: true
      });

      this.client.on('connect', () => {
        this.isConnected = true;
        this.isReconnecting = false;
        this.reconnectAttempts = 0;
        debugLogger.mqtt(`[MQTTClient-${this.clientId}]`, 'MQTT连接成功');
        this._restoreSubscriptions();
        this._processMessageQueue();
      });

      this.client.on('message', (topic, message) => this._handleMessage(topic, message));
      this.client.on('error', (error) => {
        debugLogger.error(`[MQTTClient-${this.clientId}]`, 'MQTT连接错误:', error);
        this.isConnected = false;
        this.isReconnecting = false;
      });

      this.client.on('close', () => {
        this.isConnected = false;
        debugLogger.warn(`[MQTTClient-${this.clientId}]`, 'MQTT连接关闭');
        this._scheduleReconnect();
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
      if (!this.messageRouter) {
        const module = await import('./services.js');
        this.messageRouter = module.getMessageRouter();
      }

      const parsedMessage = JSON.parse(message.toString());
      const sn = this._extractSNFromTopic(topic);

      if (this.messageRouter?.routeMessage) {
        this.messageRouter.routeMessage(parsedMessage, topic, sn);
      }
    } catch (error) {
      debugLogger.error(`[${this.clientId}] 消息处理失败:`, error);
    }
  }

  _extractSNFromTopic(topic) {
    const match = topic.match(/\/([A-Z0-9]{14})\//);
    return match ? match[1] : null;
  }

  subscribe(topic, callback = null) {
    if (!this.isConnected) {
      debugLogger.warn(`[${this.clientId}] 连接未建立，订阅请求已排队: ${topic}`);
      this.subscriptions.set(topic, callback);
      return false;
    }

    this.client.subscribe(topic, (err) => {
      if (err) {
        debugLogger.error(`[MQTTClient-${this.clientId}]`, '订阅失败:', topic, err);
      } else {
        debugLogger.mqtt(`[MQTTClient-${this.clientId}]`, '订阅成功:', topic);
        this.subscriptions.set(topic, callback);
      }
    });
    return true;
  }

  async publish(topic, message) {
    const messageStr = typeof message === 'string' ? message : JSON.stringify(message);

    if (!this.isConnected) {
      this.messageQueue.push({ topic, message: messageStr });
      debugLogger.warn(`[${this.clientId}] 连接未建立，消息已排队: ${topic}`);
      return false;
    }

    return new Promise((resolve) => {
      this.client.publish(topic, messageStr, (err) => {
        if (err) {
          debugLogger.error(`[${this.clientId}] 发布失败: ${topic}`, err);
          resolve(false);
        } else {
          debugLogger.mqtt(`[${this.clientId}] 发布成功: ${topic}`);
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
      const { topic, message } = this.messageQueue.shift();
      this.publish(topic, message);
    }
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      debugLogger.error(`[${this.clientId}] 重连次数超限，停止重连`);
      return;
    }

    setTimeout(() => {
      this.reconnectAttempts++;
      debugLogger.info(`[${this.clientId}] 尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      this.connect();
    }, this.reconnectInterval);
  }

  disconnect() {
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

    if (this.connections.has(sn)) {
      const connection = this.connections.get(sn);
      if (connection.isConnected) return connection;
    }

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

  async publish(sn, topic, message) {
    const connection = await this.ensureConnection(sn);
    return connection ? connection.publish(topic, message) : false;
  }

  subscribe(sn, topic, callback) {
    const connection = this.connections.get(sn);
    return connection ? connection.subscribe(topic, callback) : false;
  }

  disconnectDevice(sn) {
    const connection = this.connections.get(sn);
    if (connection) {
      connection.disconnect();
      this.connections.delete(sn);
      debugLogger.mqtt(`设备 ${sn} MQTT连接已断开`);
    }
  }

  disconnectAll() {
    for (const [, connection] of this.connections) {
      connection.disconnect();
    }
    this.connections.clear();
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
