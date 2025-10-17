// DJI Ground Station - 服务层管理
// 合并: topic-service-manager.js + topic-template-manager.js + message-router.js + topic-service-layer.js

import debugLogger from './debug.js';

// 加载主题模板配置
async function loadTopicTemplates() {
  try {
    const response = await fetch('/src/config/topic-templates.json');
    return await response.json();
  } catch (error) {
    debugLogger.error('加载主题模板失败:', error);
    return { dji_services: {} };
  }
}

// 主题模板管理器
class TopicTemplateManager {
  constructor() {
    this.templates = {};
    this.loaded = false;
    this._loadTemplates();
  }

  async _loadTemplates() {
    this.templates = await loadTopicTemplates();
    this.loaded = true;
    debugLogger.service('主题模板已加载');
  }

  async waitForLoad() {
    while (!this.loaded) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  hasService(serviceName) {
    return !!(this.templates.dji_services && this.templates.dji_services[serviceName]);
  }

  getServiceConfig(serviceName) {
    if (!this.templates.dji_services) return null;
    return this.templates.dji_services[serviceName] || null;
  }

  buildServiceTopic(sn, serviceName) {
    const config = this.getServiceConfig(serviceName);
    if (!config) {
      throw new Error(`未找到服务配置: ${serviceName}`);
    }

    return config.topic_template.replace('{sn}', sn);
  }

  buildResponseTopic(sn, serviceName) {
    const config = this.getServiceConfig(serviceName);
    if (!config || !config.response_topic) return null;

    return config.response_topic.replace('{sn}', sn);
  }

  buildServiceMessage(serviceName, params = {}, options = {}) {
    const config = this.getServiceConfig(serviceName);
    if (!config) {
      throw new Error(`未找到服务配置: ${serviceName}`);
    }

    const missing = (config.required_params || []).filter(param => !(param in params));
    if (missing.length > 0) {
      throw new Error(`服务 ${serviceName} 缺少必需参数: ${missing.join(', ')}`);
    }

    const data = { ...(config.default_values || {}), ...params };

    return {
      method: config.method,
      data: data,
      tid: options.tid || this.generateTid(),
      bid: options.bid || this.generateBid(),
      timestamp: options.timestamp || Date.now()
    };
  }

  getServiceTimeout(serviceName) {
    const config = this.getServiceConfig(serviceName);
    return config ? (config.timeout || 10000) : 10000;
  }

  generateTid() {
    return `tid_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
  }

  generateBid() {
    return `bid_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
  }

  getAllServices() {
    return this.templates.dji_services ? Object.keys(this.templates.dji_services) : [];
  }
}

// 消息路由器
export const MESSAGE_TYPES = {
  SERVICE_REPLY: 'service_reply',
  DRC_DATA: 'drc_data',
  DEVICE_STATUS: 'device_status',
  UNKNOWN: 'unknown'
};

export const ROUTE_TYPES = {
  EXACT: 'exact',
  PREFIX: 'prefix',
  PATTERN: 'pattern',
  SERVICE: 'service'
};

class MessageRouter {
  constructor() {
    this.routeRules = new Map();
    this.callbacks = new Map();
    this.stats = {
      totalReceived: 0,
      totalRouted: 0,
      totalErrors: 0,
      byMessageType: {},
      byServiceType: {}
    };
    this.debug = false;
    debugLogger.service('[MessageRouter] 已初始化');
  }

  registerRoute(ruleId, rule, callback) {
    if (!ruleId || !rule || !callback) {
      throw new Error('路由规则参数不完整');
    }

    this.routeRules.set(ruleId, rule);

    if (!this.callbacks.has(ruleId)) {
      this.callbacks.set(ruleId, new Set());
    }
    this.callbacks.get(ruleId).add(callback);

    debugLogger.service(`路由规则已注册: ${ruleId}`);
    return ruleId;
  }

  unregisterRoute(ruleId, callback = null) {
    if (callback) {
      const callbackSet = this.callbacks.get(ruleId);
      if (callbackSet) {
        callbackSet.delete(callback);
        if (callbackSet.size === 0) {
          this.callbacks.delete(ruleId);
          this.routeRules.delete(ruleId);
        }
      }
    } else {
      this.callbacks.delete(ruleId);
      this.routeRules.delete(ruleId);
    }

    debugLogger.service(`路由规则已注销: ${ruleId}`);
  }

  registerServiceRoute(serviceType, callback) {
    const ruleId = `service_${serviceType}`;
    const rule = { type: ROUTE_TYPES.SERVICE, serviceType: serviceType };
    return this.registerRoute(ruleId, rule, callback);
  }

  routeMessage(rawMessage, topic, sn = null) {
    this.stats.totalReceived++;

    try {
      const message = this._parseMessage(rawMessage);
      if (!message) {
        this.stats.totalErrors++;
        return;
      }

      const messageType = this._identifyMessageType(topic);
      if (!sn) {
        sn = this._extractSNFromTopic(topic);
      }

      this._updateStats(messageType, message);

      const context = {
        message: message,
        topic: topic,
        sn: sn,
        messageType: messageType,
        timestamp: Date.now()
      };

      debugLogger.mqtt(`消息路由: ${messageType} from ${sn}`);
      this._executeRouting(context);

    } catch (error) {
      this.stats.totalErrors++;
      debugLogger.error('[MessageRouter] 消息路由失败:', error);
    }
  }

  _executeRouting(context) {
    let routedCount = 0;

    for (const [ruleId, rule] of this.routeRules) {
      if (this._matchRule(rule, context)) {
        const callbacks = this.callbacks.get(ruleId);
        if (callbacks) {
          for (const callback of callbacks) {
            try {
              callback(context.message, context.topic, context);
              routedCount++;
            } catch (error) {
              debugLogger.error(`[MessageRouter] 回调执行失败 [${ruleId}]:`, error);
            }
          }
        }
      }
    }

    if (routedCount > 0) {
      this.stats.totalRouted++;
    }

    debugLogger.mqtt(`消息已路由到 ${routedCount} 个处理器`);
  }

  _matchRule(rule, context) {
    switch (rule.type) {
      case ROUTE_TYPES.EXACT:
        return this._matchExact(rule, context);
      case ROUTE_TYPES.PREFIX:
        return this._matchPrefix(rule, context);
      case ROUTE_TYPES.PATTERN:
        return this._matchPattern(rule, context);
      case ROUTE_TYPES.SERVICE:
        return this._matchService(rule, context);
      default:
        return false;
    }
  }

  _matchExact(rule, context) {
    return rule.topic === context.topic;
  }

  _matchPrefix(rule, context) {
    return context.topic.startsWith(rule.prefix);
  }

  _matchPattern(rule, context) {
    try {
      const regex = new RegExp(rule.pattern);
      return regex.test(context.topic);
    } catch (error) {
      debugLogger.error(`路由规则模式错误: ${rule.pattern}`, error);
      return false;
    }
  }

  _matchService(rule, context) {
    if (context.messageType !== MESSAGE_TYPES.SERVICE_REPLY) {
      return false;
    }

    const message = context.message;
    return message && message.method === rule.serviceType;
  }

  _parseMessage(rawMessage) {
    if (typeof rawMessage === 'object') {
      return rawMessage;
    }

    if (typeof rawMessage === 'string') {
      try {
        return JSON.parse(rawMessage);
      } catch (error) {
        debugLogger.warn('[MessageRouter] JSON解析失败:', error.message);
        return null;
      }
    }

    return null;
  }

  _identifyMessageType(topic) {
    if (topic.includes('/services_reply')) {
      return MESSAGE_TYPES.SERVICE_REPLY;
    }

    if (topic.includes('/drc/')) {
      return MESSAGE_TYPES.DRC_DATA;
    }

    if (topic.includes('/events')) {
      return MESSAGE_TYPES.DEVICE_STATUS;
    }

    return MESSAGE_TYPES.UNKNOWN;
  }

  _extractSNFromTopic(topic) {
    const match = topic.match(/\/([A-Z0-9]{14})\//);
    return match ? match[1] : null;
  }

  _updateStats(messageType, message) {
    if (!this.stats.byMessageType[messageType]) {
      this.stats.byMessageType[messageType] = 0;
    }
    this.stats.byMessageType[messageType]++;

    if (messageType === MESSAGE_TYPES.SERVICE_REPLY && message && message.method) {
      const serviceType = message.method;
      if (!this.stats.byServiceType[serviceType]) {
        this.stats.byServiceType[serviceType] = 0;
      }
      this.stats.byServiceType[serviceType]++;
    }
  }

  setDebug(enabled) {
    this.debug = enabled;
    debugLogger.info(`[MessageRouter] 调试模式: ${enabled ? '启用' : '禁用'}`);
  }

  getStats() {
    return {
      ...this.stats,
      registeredRules: this.routeRules.size,
      totalCallbacks: Array.from(this.callbacks.values())
        .reduce((sum, callbackSet) => sum + callbackSet.size, 0)
    };
  }

  resetStats() {
    this.stats = {
      totalReceived: 0,
      totalRouted: 0,
      totalErrors: 0,
      byMessageType: {},
      byServiceType: {}
    };
  }

  cleanup() {
    this.routeRules.clear();
    this.callbacks.clear();
    this.resetStats();
    debugLogger.info('[MessageRouter] 已清理所有路由规则');
  }
}

// 服务结果类型
export const SERVICE_RESULT = {
  SUCCESS: 'success',
  ERROR: 'error',
  TIMEOUT: 'timeout',
  NO_CONNECTION: 'no_connection',
  INVALID_PARAMS: 'invalid_params'
};

// 主题服务管理器
class TopicServiceManager {
  constructor() {
    this.mqttManager = null;
    this.templateManager = new TopicTemplateManager();
    this.pendingCallbacks = new Map();
    this.callTimeouts = new Map();
    this.defaultTimeout = 10000;
    this.debug = false;
    this._initMqttManager();
  }

  async _initMqttManager() {
    try {
      const module = await import('./mqtt.js');
      this.mqttManager = module.mqttManager;
    } catch (error) {
      debugLogger.error('初始化MQTT管理器失败:', error);
    }
  }

  async callService(sn, serviceName, params = {}, options = {}) {
    if (!sn) return this._error(SERVICE_RESULT.INVALID_PARAMS, '设备SN不能为空');
    if (!serviceName) return this._error(SERVICE_RESULT.INVALID_PARAMS, '服务名称不能为空');

    await this.templateManager.waitForLoad();

    if (!this.templateManager.hasService(serviceName)) {
      return this._error(SERVICE_RESULT.INVALID_PARAMS, `未知服务: ${serviceName}`);
    }

    const connection = this._getConnection(sn);
    if (!connection) {
      return this._error(SERVICE_RESULT.NO_CONNECTION, `设备 ${sn} 未连接`);
    }

    try {
      const message = this.templateManager.buildServiceMessage(serviceName, params, options);
      const topic = this.templateManager.buildServiceTopic(sn, serviceName);
      const timeout = options.timeout || this.templateManager.getServiceTimeout(serviceName);

      const responsePromise = this._setupResponseHandler(serviceName, message.tid, timeout);

      const success = await connection.publish(topic, JSON.stringify(message));
      if (!success) {
        this._cleanupResponseHandler(message.tid);
        return this._error(SERVICE_RESULT.ERROR, '消息发送失败');
      }

      debugLogger.service(`[${sn}] 服务调用成功: ${serviceName}`, message);

      if (options.noWait) {
        this._cleanupResponseHandler(message.tid);
        return this._success({ sent: true });
      }

      return await responsePromise;

    } catch (error) {
      return this._error(SERVICE_RESULT.ERROR, error.message);
    }
  }

  _getConnection(sn) {
    return this.mqttManager ? this.mqttManager.getConnection(sn) : null;
  }

  _setupResponseHandler(serviceName, tid, timeout) {
    return new Promise((resolve) => {
      const timeoutId = setTimeout(() => {
        this._cleanupResponseHandler(tid);
        resolve(this._error(SERVICE_RESULT.TIMEOUT, `服务调用超时: ${serviceName}`));
      }, timeout);

      this.pendingCallbacks.set(tid, resolve);
      this.callTimeouts.set(tid, timeoutId);
    });
  }

  _handleServiceResponse(message, topic, sn) {
    debugLogger.service(`处理设备 ${sn} 服务回复: ${topic}`, message);

    if (!message || !message.tid) {
      debugLogger.warn('[TopicServiceManager] 响应消息缺少tid');
      return;
    }

    const callback = this.pendingCallbacks.get(message.tid);
    if (callback) {
      this._cleanupResponseHandler(message.tid);

      if (message.data && message.data.result === 0) {
        callback(this._success(message.data));
      } else {
        const errorMsg = message.data?.output || message.data?.reason || '服务调用失败';
        callback(this._error(SERVICE_RESULT.ERROR, errorMsg));
      }
    }
  }

  _cleanupResponseHandler(tid) {
    this.pendingCallbacks.delete(tid);

    const timeoutId = this.callTimeouts.get(tid);
    if (timeoutId) {
      clearTimeout(timeoutId);
      this.callTimeouts.delete(tid);
    }
  }

  _success(data = null) {
    return {
      success: true,
      data: data,
      error: null,
      timestamp: Date.now()
    };
  }

  _error(type, message) {
    return {
      success: false,
      data: null,
      error: { type, message },
      timestamp: Date.now()
    };
  }

  getStats() {
    return {
      pendingCallbacks: this.pendingCallbacks.size,
      activeTimeouts: this.callTimeouts.size,
      templateManager: {
        loaded: this.templateManager.loaded,
        services: this.templateManager.getAllServices()
      }
    };
  }

  cleanup() {
    for (const timeoutId of this.callTimeouts.values()) {
      clearTimeout(timeoutId);
    }
    this.pendingCallbacks.clear();
    this.callTimeouts.clear();
  }
}

// 全局实例
const templateManager = new TopicTemplateManager();
const messageRouter = new MessageRouter();
const topicServiceManager = new TopicServiceManager();

// 设置消息路由器处理服务回复
messageRouter.registerServiceRoute('*', (message, topic, context) => {
  topicServiceManager._handleServiceResponse(message, topic, context.sn);
});

// 浏览器全局变量
if (typeof window !== 'undefined') {
  window.templateManager = templateManager;
  window.messageRouter = messageRouter;
  window.topicServiceManager = topicServiceManager;
}

// 导出函数供其他模块使用
export function getMessageRouter() {
  return messageRouter;
}

export function getTopicServiceManager() {
  return topicServiceManager;
}

export function getTemplateManager() {
  return templateManager;
}

export { TopicTemplateManager, MessageRouter, TopicServiceManager, templateManager, messageRouter, topicServiceManager };
export default topicServiceManager;