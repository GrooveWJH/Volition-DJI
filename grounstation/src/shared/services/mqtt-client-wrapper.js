/**
 * MQTT客户端封装
 * 为单个设备SN封装MQTT连接，提供发布、订阅等功能
 */

import mqtt from 'mqtt';
import { MqttConnectionState, MQTT_CONNECTION_CONFIG, MQTT_CONFIG } from '@/shared/config/mqtt-config.js';
import { globalEventManager } from '@/shared/utils/event-manager.js';

/**
 * MQTT客户端封装类
 */
export class MqttClientWrapper {
  /**
   * @param {string} sn - 设备序列号
   * @param {Object} config - 连接配置
   */
  constructor(sn, config = {}) {
    this.sn = sn;
    this.config = config;
    this.client = null;
    this.state = MqttConnectionState.IDLE;
    this.reconnectAttempts = 0;
    this.subscriptions = new Map(); // topic -> handler
    this.messageHandlers = []; // 全局消息处理器
    this.errorHandlers = [];

    // 连接参数
    this.clientId = MQTT_CONFIG.buildStationClientId(sn);
    this.brokerUrl = MQTT_CONFIG.buildConnectionUrl(config);
  }

  /**
   * 连接到MQTT服务器
   * @returns {Promise<boolean>}
   */
  async connect() {
    if (this.client) {
      console.warn(`[MQTT-${this.sn}] 已存在连接`);
      return this.isConnected();
    }

    this.setState(MqttConnectionState.CONNECTING);
    console.log(`[MQTT-${this.sn}] 正在连接到 ${this.brokerUrl}...`);

    return new Promise((resolve) => {
      try {
        const options = {
          clientId: this.clientId,
          username: this.config.username || MQTT_CONFIG.defaultUsername,
          password: this.config.password || MQTT_CONFIG.defaultPassword,
          clean: MQTT_CONNECTION_CONFIG.clean,
          keepalive: MQTT_CONNECTION_CONFIG.keepalive,
          reconnectPeriod: MQTT_CONNECTION_CONFIG.reconnectPeriod,
          connectTimeout: MQTT_CONNECTION_CONFIG.connectTimeout,
        };

        this.client = mqtt.connect(this.brokerUrl, options);

        // 连接成功
        this.client.on('connect', () => {
          console.log(`[MQTT-${this.sn}] ✓ 连接成功`);
          this.setState(MqttConnectionState.CONNECTED);
          this.reconnectAttempts = 0;
          this.subscribeDefaultTopics();
          resolve(true);
        });

        // 重连中
        this.client.on('reconnect', () => {
          this.reconnectAttempts++;
          console.log(`[MQTT-${this.sn}] ⟳ 重连中 (${this.reconnectAttempts}/${MQTT_CONNECTION_CONFIG.maxReconnectAttempts})...`);

          if (this.reconnectAttempts >= MQTT_CONNECTION_CONFIG.maxReconnectAttempts) {
            console.error(`[MQTT-${this.sn}] ✗ 达到最大重连次数，停止重连`);
            this.disconnect();
            this.setState(MqttConnectionState.ERROR);
            return;
          }

          this.setState(MqttConnectionState.RECONNECTING);
        });

        // 连接关闭
        this.client.on('close', () => {
          console.log(`[MQTT-${this.sn}] 连接已关闭`);
          if (this.state !== MqttConnectionState.DISCONNECTING) {
            this.setState(MqttConnectionState.DISCONNECTED);
          }
        });

        // 错误处理
        this.client.on('error', (error) => {
          console.error(`[MQTT-${this.sn}] ✗ 连接错误:`, error.message);
          this.setState(MqttConnectionState.ERROR);
          this.errorHandlers.forEach(handler => handler(error));
          resolve(false);
        });

        // 消息接收
        this.client.on('message', (topic, payload) => {
          this.handleMessage(topic, payload);
        });

      } catch (error) {
        console.error(`[MQTT-${this.sn}] ✗ 连接失败:`, error);
        this.setState(MqttConnectionState.ERROR);
        resolve(false);
      }
    });
  }

  /**
   * 断开连接
   * @returns {Promise<void>}
   */
  async disconnect() {
    if (!this.client) {
      return;
    }

    this.setState(MqttConnectionState.DISCONNECTING);
    console.log(`[MQTT-${this.sn}] 正在断开连接...`);

    return new Promise((resolve) => {
      this.client.end(false, {}, () => {
        console.log(`[MQTT-${this.sn}] ✓ 已断开连接`);
        this.client = null;
        this.setState(MqttConnectionState.DISCONNECTED);
        this.subscriptions.clear();
        resolve();
      });
    });
  }

  /**
   * 订阅默认主题
   * @private
   */
  subscribeDefaultTopics() {
    const topics = MQTT_CONNECTION_CONFIG.defaultSubscriptions.map(
      topic => topic.replace('{sn}', this.sn)
    );

    topics.forEach(topic => {
      this.subscribe(topic, (message, topic) => {
        console.log(`[MQTT-${this.sn}] 📨 收到消息 [${topic}]:`, message);
      });
    });
  }

  /**
   * 订阅主题
   * @param {string} topic - 主题
   * @param {Function} handler - 消息处理器 (message, topic) => void
   * @param {Object} options - 订阅选项
   */
  subscribe(topic, handler, options = {}) {
    if (!this.client) {
      console.error(`[MQTT-${this.sn}] 无法订阅：客户端未连接`);
      return;
    }

    const qos = options.qos || MQTT_CONNECTION_CONFIG.qos;

    this.client.subscribe(topic, { qos }, (err) => {
      if (err) {
        console.error(`[MQTT-${this.sn}] ✗ 订阅失败 [${topic}]:`, err);
        return;
      }

      console.log(`[MQTT-${this.sn}] ✓ 已订阅主题: ${topic}`);
      this.subscriptions.set(topic, handler);
    });
  }

  /**
   * 取消订阅
   * @param {string} topic - 主题
   */
  unsubscribe(topic) {
    if (!this.client) {
      return;
    }

    this.client.unsubscribe(topic, (err) => {
      if (err) {
        console.error(`[MQTT-${this.sn}] ✗ 取消订阅失败 [${topic}]:`, err);
        return;
      }

      console.log(`[MQTT-${this.sn}] ✓ 已取消订阅: ${topic}`);
      this.subscriptions.delete(topic);
    });
  }

  /**
   * 发布消息
   * @param {string} topic - 主题
   * @param {string|Object} payload - 消息内容
   * @param {Object} options - 发布选项
   * @returns {Promise<boolean>}
   */
  async publish(topic, payload, options = {}) {
    if (!this.client || !this.isConnected()) {
      console.error(`[MQTT-${this.sn}] 无法发布：客户端未连接`);
      return false;
    }

    const qos = options.qos || MQTT_CONNECTION_CONFIG.qos;
    const message = typeof payload === 'object' ? JSON.stringify(payload) : payload;

    return new Promise((resolve) => {
      this.client.publish(topic, message, { qos }, (err) => {
        if (err) {
          console.error(`[MQTT-${this.sn}] ✗ 发布失败 [${topic}]:`, err);
          resolve(false);
          return;
        }

        console.log(`[MQTT-${this.sn}] ✓ 已发布消息 [${topic}]:`, message);
        resolve(true);
      });
    });
  }

  /**
   * 处理接收到的消息
   * @private
   */
  handleMessage(topic, payload) {
    const message = payload.toString();

    // 尝试解析JSON
    let parsedMessage;
    try {
      parsedMessage = JSON.parse(message);
    } catch {
      parsedMessage = message;
    }

    // 调用主题特定的处理器
    const handler = this.subscriptions.get(topic);
    if (handler) {
      try {
        handler(parsedMessage, topic);
      } catch (error) {
        console.error(`[MQTT-${this.sn}] 消息处理器错误:`, error);
      }
    }

    // 调用全局消息处理器
    this.messageHandlers.forEach(handler => {
      try {
        handler(parsedMessage, topic);
      } catch (error) {
        console.error(`[MQTT-${this.sn}] 全局消息处理器错误:`, error);
      }
    });
  }

  /**
   * 添加全局消息处理器
   * @param {Function} handler - (message, topic) => void
   */
  onMessage(handler) {
    this.messageHandlers.push(handler);
  }

  /**
   * 添加错误处理器
   * @param {Function} handler - (error) => void
   */
  onError(handler) {
    this.errorHandlers.push(handler);
  }

  /**
   * 设置连接状态
   * @private
   */
  setState(newState) {
    if (this.state === newState) {
      return;
    }

    const oldState = this.state;
    this.state = newState;

    console.log(`[MQTT-${this.sn}] 状态变更: ${oldState} → ${newState}`);

    // 触发全局事件
    globalEventManager.emit('mqtt-connection-state-changed', {
      sn: this.sn,
      state: newState,
      oldState
    });

    // 触发window事件供UI监听
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('mqtt-connection-changed', {
        detail: {
          sn: this.sn,
          state: newState,
          oldState
        }
      }));
    }
  }

  /**
   * 获取当前连接状态
   * @returns {string}
   */
  getState() {
    return this.state;
  }

  /**
   * 是否已连接
   * @returns {boolean}
   */
  isConnected() {
    return this.state === MqttConnectionState.CONNECTED;
  }

  /**
   * 是否正在连接
   * @returns {boolean}
   */
  isConnecting() {
    return this.state === MqttConnectionState.CONNECTING ||
           this.state === MqttConnectionState.RECONNECTING;
  }

  /**
   * 获取连接信息
   * @returns {Object}
   */
  getInfo() {
    return {
      sn: this.sn,
      clientId: this.clientId,
      brokerUrl: this.brokerUrl,
      state: this.state,
      connected: this.isConnected(),
      reconnectAttempts: this.reconnectAttempts,
      subscriptions: Array.from(this.subscriptions.keys())
    };
  }
}
