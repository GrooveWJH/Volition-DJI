/**
 * 简单验证工具（简化版）
 * 遵循Linus原则：删除过度抽象，只保留实际需要的验证功能
 */

/**
 * 验证设备序列号
 * @param {string} serialNumber - 设备序列号
 * @returns {Object} 验证结果
 */
function validateSerialNumber(serialNumber) {
  if (!serialNumber || serialNumber.trim().length === 0) {
    return {
      valid: false,
      message: '设备序列号不能为空'
    };
  }

  if (serialNumber.length < 10) {
    return {
      valid: false,
      message: '设备序列号至少需要10个字符'
    };
  }

  // 简单的字母数字检查
  if (!/^[A-Z0-9]+$/.test(serialNumber)) {
    return {
      valid: false,
      message: '设备序列号只能包含大写字母和数字'
    };
  }

  return { valid: true, message: '序列号验证通过' };
}

/**
 * 验证MQTT配置
 * @param {Object} config - MQTT配置对象
 * @returns {Object} 验证结果
 */
function validateMqttConfig(config) {
  const errors = [];

  // 验证主机地址
  if (!config.host || config.host.trim().length === 0) {
    errors.push('MQTT主机地址不能为空');
  }

  // 验证端口
  const port = parseInt(config.port);
  if (isNaN(port) || port < 1 || port > 65535) {
    errors.push('MQTT端口必须是1-65535之间的数字');
  }

  // 验证用户名（如果提供）
  if (config.username && config.username.length > 100) {
    errors.push('用户名长度不能超过100个字符');
  }

  // 验证密码（如果提供）
  if (config.password && config.password.length > 100) {
    errors.push('密码长度不能超过100个字符');
  }

  return {
    valid: errors.length === 0,
    errors: errors,
    message: errors.length === 0 ? 'MQTT配置验证通过' : errors[0]
  };
}

/**
 * 验证URL格式
 * @param {string} url - URL字符串
 * @returns {Object} 验证结果
 */
function validateUrl(url) {
  if (!url || url.trim().length === 0) {
    return { valid: false, message: 'URL不能为空' };
  }

  try {
    new URL(url);
    return { valid: true, message: 'URL格式正确' };
  } catch {
    return { valid: false, message: 'URL格式不正确' };
  }
}

/**
 * 验证端口号
 * @param {string|number} port - 端口号
 * @returns {Object} 验证结果
 */
function validatePort(port) {
  const portNum = parseInt(port);
  
  if (isNaN(portNum)) {
    return { valid: false, message: '端口必须是数字' };
  }

  if (portNum < 1 || portNum > 65535) {
    return { valid: false, message: '端口必须在1-65535之间' };
  }

  return { valid: true, message: '端口验证通过' };
}

// 简单验证函数导出（替换复杂的验证框架）
export const quickValidate = {
  serialNumber: validateSerialNumber,
  mqttConfig: validateMqttConfig,
  url: validateUrl,
  port: validatePort
};