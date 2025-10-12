/**
 * MQTT相关配置
 * 包含MQTT连接、DJI网关、DRC模式等配置
 */

/**
 * MQTT配置对象
 */
export const MQTT_CONFIG = {
  // 默认MQTT Broker配置
  defaultHost: '127.0.0.1',
  defaultPort: 1883,
  defaultUsername: 'admin',
  defaultPassword: '302811055wjhhz',
  
  // DJI Gateway配置
  defaultGatewaySN: '9N9CN8400164WH',
  
  // 控制权请求配置
  controlAuth: {
    defaultUserId: 'groove',
    defaultUserCallsign: '吴建豪'
  },
  
  // DRC模式配置
  drcMode: {
    relayAddress: '192.168.31.240:1883',
    relayClientId: 'drc-9N9CN8400164WH',
    relayUsername: 'admin',
    relayPassword: '302811055wjhhz',
    relayExpireTime: 1_700_000_000,
    relayEnableTLS: false,
    osdFrequency: 30,
    hsiFrequency: 10,
    heartbeatFrequencyHz: 5
  },
  
  // DJI登录页面HTTP服务配置
  httpServer: {
    defaultPort: 5000,
    loginPath: '/login'
  },
  
  // 构建MQTT连接URL
  buildConnectionUrl() {
    return `mqtt://${this.defaultHost}:${this.defaultPort}`;
  },
  
  // 构建主题名称
  buildTopics(gatewaySN) {
    return {
      services: `thing/product/${gatewaySN}/services`,
      servicesReply: `thing/product/${gatewaySN}/services_reply`,
      drcUp: `thing/product/${gatewaySN}/drc/up`,
      drcDown: `thing/product/${gatewaySN}/drc/down`
    };
  },
  
  // 构建登录页面URL
  buildLoginUrl(host, port = this.httpServer.defaultPort) {
    return `http://${host}:${port}${this.httpServer.loginPath}`;
  }
};

/**
 * DRC配置对象
 */
export const DRC_CONFIG = {
  // 默认设备序列号
  defaultSerialNumber: '1ZNDH7C0010001',
  
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
 * 验证MQTT配置
 * @param {Object} config - 配置对象
 * @returns {Object} 验证结果
 */
export function validateMqttConfig(config = MQTT_CONFIG) {
  const errors = [];
  
  // 验证主机地址
  if (!config.defaultHost) {
    errors.push('MQTT主机地址未配置');
  }
  
  // 验证端口范围
  if (config.defaultPort < 1 || config.defaultPort > 65535) {
    errors.push('MQTT端口范围无效(1-65535)');
  }
  
  // 验证用户名和密码
  if (!config.defaultUsername) {
    errors.push('MQTT用户名未配置');
  }
  
  if (!config.defaultPassword) {
    errors.push('MQTT密码未配置');
  }
  
  // 验证网关序列号
  if (!config.defaultGatewaySN) {
    errors.push('DJI网关序列号未配置');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * 验证DRC配置
 * @param {Object} config - 配置对象
 * @returns {Object} 验证结果
 */
export function validateDrcConfig(config = DRC_CONFIG) {
  const errors = [];
  
  // 验证设备序列号
  if (!config.defaultSerialNumber) {
    errors.push('设备序列号未配置');
  } else if (!/^[A-Z0-9]{10,20}$/.test(config.defaultSerialNumber)) {
    errors.push('设备序列号格式不正确');
  }
  
  // 验证超时时间
  if (config.timeoutSeconds < 5 || config.timeoutSeconds > 300) {
    errors.push('超时时间范围无效(5-300秒)');
  }
  
  // 验证重试次数
  if (config.maxRetries < 0 || config.maxRetries > 10) {
    errors.push('重试次数范围无效(0-10次)');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

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

/**
 * 获取MQTT配置的环境变量覆盖
 */
export function getMqttEnvironmentOverrides() {
  const overrides = {};
  
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    
    if (params.has('mqtt_host')) {
      overrides.defaultHost = params.get('mqtt_host');
    }
    
    if (params.has('mqtt_port')) {
      overrides.defaultPort = parseInt(params.get('mqtt_port'), 10);
    }
    
    if (params.has('mqtt_user')) {
      overrides.defaultUsername = params.get('mqtt_user');
    }
    
    if (params.has('mqtt_pass')) {
      overrides.defaultPassword = params.get('mqtt_pass');
    }
    
    if (params.has('gateway_sn')) {
      overrides.defaultGatewaySN = params.get('gateway_sn');
    }
  }
  
  return overrides;
}