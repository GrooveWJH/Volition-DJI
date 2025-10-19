/**
 * MqttBrokerManager Mock版本 - 用于单元测试
 * 移除了对外部依赖的引用，专门用于测试环境
 */

export class MqttBrokerManager {
  constructor() {
    // 默认配置
    this.defaultConfig = {
      address: 'mqtt.dji.com:8883',
      enable_tls: true,
      expire_time_hours: 1  // 默认1小时过期
    };

    // 配置验证规则
    this.validationRules = {
      address: {
        required: true,
        pattern: /^[\w\-\.]+:\d{1,5}$/,  // host:port格式
        message: '地址格式应为 host:port (例: mqtt.dji.com:8883)'
      },
      client_id: {
        required: true,
        minLength: 1,
        maxLength: 64,
        message: '客户端ID长度应在1-64字符之间'
      },
      username: {
        required: true,
        minLength: 1,
        message: '用户名不能为空'
      },
      password: {
        required: true,
        minLength: 1,
        message: '密码不能为空'
      }
    };

    // 字段显示名称映射
    this.fieldDisplayNames = {
      address: '服务器地址',
      client_id: '客户端ID',
      username: '用户名',
      password: '密码'
    };
  }

  /**
   * 验证单个配置字段
   */
  validateField(fieldName, value) {
    const rule = this.validationRules[fieldName];
    if (!rule) return { isValid: true };

    const errors = [];

    // 检查必需字段
    if (rule.required && (!value || value.trim() === '')) {
      errors.push(`${this.getFieldDisplayName(fieldName)}是必需的`);
    }

    if (value) {
      // 检查长度
      if (rule.minLength && value.length < rule.minLength) {
        errors.push(`${this.getFieldDisplayName(fieldName)}长度至少为${rule.minLength}字符`);
      }
      if (rule.maxLength && value.length > rule.maxLength) {
        errors.push(`${this.getFieldDisplayName(fieldName)}长度不能超过${rule.maxLength}字符`);
      }

      // 检查格式
      if (rule.pattern && !rule.pattern.test(value)) {
        errors.push(rule.message || `${this.getFieldDisplayName(fieldName)}格式不正确`);
      }
    }

    return {
      isValid: errors.length === 0,
      errors: errors
    };
  }

  /**
   * 验证完整配置
   */
  validateConfig(config) {
    const result = { isValid: true, errors: {}, messages: [] };

    Object.keys(this.validationRules).forEach(fieldName => {
      const validation = this.validateField(fieldName, config[fieldName]);
      if (!validation.isValid) {
        result.isValid = false;
        result.errors[fieldName] = validation.errors;
        result.messages.push(...validation.errors);
      }
    });

    return result;
  }

  /**
   * 生成客户端ID
   */
  generateClientId(deviceSn = null, prefix = 'drc-') {
    if (deviceSn) {
      return `${prefix}${deviceSn}`;
    }
    // 生成随机ID
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 8);
    return `${prefix}${timestamp}-${random}`;
  }

  /**
   * 解析服务器地址
   */
  parseServerAddress(address) {
    if (!address || typeof address !== 'string') {
      return null;
    }

    const match = address.match(/^([\w\-\.]+):(\d{1,5})$/);
    if (!match) {
      return null;
    }

    const host = match[1];
    const port = parseInt(match[2]);
    const isSecure = port === 8883 || port === 443;

    return {
      host,
      port,
      isSecure
    };
  }

  /**
   * 生成过期时间
   */
  generateExpireTime(hours = 1) {
    return Math.floor(Date.now() / 1000) + (hours * 3600);
  }

  /**
   * 构建MQTT配置
   */
  buildMqttConfig(formData, deviceSn = null) {
    return {
      address: formData.address,
      client_id: this.generateClientId(deviceSn),
      username: formData.username,
      password: formData.password,
      expire_time: this.generateExpireTime(),
      enable_tls: formData.enable_tls !== false
    };
  }

  /**
   * 测试连接（模拟）
   */
  async testConnection(config) {
    // 模拟异步连接测试
    await new Promise(resolve => setTimeout(resolve, 100));

    // 验证配置
    const validation = this.validateConfig(config);
    if (!validation.isValid) {
      return {
        success: false,
        error: 'config_invalid',
        message: '配置验证失败'
      };
    }

    // 模拟网络连接测试
    if (config.username === 'invalid' || config.address.includes('invalid')) {
      return {
        success: false,
        error: 'connection_failed',
        message: '连接失败'
      };
    }

    return {
      success: true,
      latency: Math.floor(Math.random() * 100) + 50, // 50-150ms
      message: '连接测试成功'
    };
  }

  /**
   * 获取配置建议
   */
  getConfigSuggestions(deviceSn = null) {
    return {
      address: {
        label: '服务器地址',
        suggestions: [
          'mqtt.dji.com:8883',
          'localhost:1883',
          'test.mosquitto.org:1883'
        ]
      },
      client_id: {
        label: '客户端ID',
        suggestions: deviceSn ? [
          this.generateClientId(deviceSn, 'drc-'),
          this.generateClientId(deviceSn, 'station-'),
          this.generateClientId(deviceSn, 'pilot-')
        ] : [
          this.generateClientId(null, 'drc-'),
          this.generateClientId(null, 'station-'),
          this.generateClientId(null, 'pilot-')
        ]
      },
      tls: {
        label: 'TLS加密',
        default: true,
        note: '推荐在生产环境中启用TLS'
      }
    };
  }

  /**
   * 获取配置模板
   */
  getConfigTemplates() {
    return {
      dji_official: {
        name: 'DJI官方服务器',
        address: 'mqtt.dji.com:8883',
        enable_tls: true,
        description: 'DJI官方MQTT服务器，需要有效的认证凭据'
      },
      local_emqx: {
        name: '本地EMQX',
        address: 'localhost:1883',
        enable_tls: false,
        description: '本地部署的EMQX服务器'
      },
      public_broker: {
        name: '公共测试服务器',
        address: 'test.mosquitto.org:1883',
        enable_tls: false,
        description: '仅用于测试，不要在生产环境使用'
      }
    };
  }

  /**
   * 应用配置模板
   */
  applyTemplate(templateName, deviceSn = null) {
    const templates = this.getConfigTemplates();
    const template = templates[templateName];

    if (!template) {
      throw new Error(`未找到配置模板: ${templateName}`);
    }

    return {
      address: template.address,
      client_id: this.generateClientId(deviceSn),
      username: '', // 需要用户填写
      password: '', // 需要用户填写
      enable_tls: template.enable_tls,
      expire_time: this.generateExpireTime()
    };
  }

  /**
   * 获取字段显示名称
   */
  getFieldDisplayName(fieldName) {
    return this.fieldDisplayNames[fieldName] || fieldName;
  }
}