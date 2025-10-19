/**
 * MqttBrokerManager 单元测试
 * 测试MQTT中继配置验证、管理和连接测试功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[MqttBrokerManager单元测试]');
const runner = new TestRunner('MqttBrokerManager 单元测试');

// Mock debugLogger to avoid import issues
global.debugLogger = {
  state: () => {},
  error: () => {},
  info: () => {},
  debug: () => {}
};

// Setup/teardown
runner.beforeEach(() => {
  mockBrowserEnvironment();
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
});

// Tests
runner.test('应该正确验证MQTT配置字段', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  // 测试地址验证
  let result = manager.validateField('address', 'mqtt.dji.com:8883');
  Assert.true(result.isValid, '有效地址应该验证通过');

  result = manager.validateField('address', 'invalid-address');
  Assert.false(result.isValid, '无效地址应该验证失败');

  result = manager.validateField('address', '');
  Assert.false(result.isValid, '空地址应该验证失败');

  // 测试客户端ID验证
  result = manager.validateField('client_id', 'valid-client-id');
  Assert.true(result.isValid, '有效客户端ID应该验证通过');

  result = manager.validateField('client_id', '');
  Assert.false(result.isValid, '空客户端ID应该验证失败');

  // 测试用户名验证
  result = manager.validateField('username', 'testuser');
  Assert.true(result.isValid, '有效用户名应该验证通过');

  result = manager.validateField('username', '');
  Assert.false(result.isValid, '空用户名应该验证失败');
});

runner.test('应该正确验证完整配置', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  // 测试有效配置
  const validConfig = {
    address: 'mqtt.dji.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass'
  };

  let result = manager.validateConfig(validConfig);
  Assert.true(result.isValid, '有效配置应该验证通过');
  Assert.deepEqual(result.errors, {}, '有效配置不应该有错误');

  // 测试无效配置
  const invalidConfig = {
    address: 'invalid-address',
    client_id: '',
    username: 'testuser',
    password: ''
  };

  result = manager.validateConfig(invalidConfig);
  Assert.false(result.isValid, '无效配置应该验证失败');
  Assert.true(result.messages.length > 0, '应该有错误消息');
});

runner.test('应该正确生成客户端ID', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  // 测试有设备SN的情况
  const clientId = manager.generateClientId('1234567890ABCD', 'drc-');
  Assert.true(clientId.startsWith('drc-'), '客户端ID应该有正确的前缀');
  Assert.true(clientId.includes('1234567890ABCD'), '客户端ID应该包含设备SN');

  // 测试无设备SN的情况
  const randomClientId = manager.generateClientId(null, 'test-');
  Assert.true(randomClientId.startsWith('test-'), '随机客户端ID应该有正确的前缀');
  Assert.true(randomClientId.length > 5, '随机客户端ID应该有合理长度');
});

runner.test('应该正确解析服务器地址', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  // 测试有效地址
  let parsed = manager.parseServerAddress('mqtt.dji.com:8883');
  Assert.equal(parsed.host, 'mqtt.dji.com', '主机名应该正确');
  Assert.equal(parsed.port, 8883, '端口应该正确');
  Assert.true(parsed.isSecure, '8883端口应该被识别为安全');

  parsed = manager.parseServerAddress('localhost:1883');
  Assert.equal(parsed.host, 'localhost', '本地主机应该正确');
  Assert.equal(parsed.port, 1883, '标准端口应该正确');
  Assert.false(parsed.isSecure, '1883端口不应该被识别为安全');

  // 测试无效地址
  parsed = manager.parseServerAddress('invalid-address');
  Assert.equal(parsed, null, '无效地址应该返回null');

  parsed = manager.parseServerAddress('');
  Assert.equal(parsed, null, '空地址应该返回null');
});

runner.test('应该正确生成过期时间', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  const now = Math.floor(Date.now() / 1000);

  // 测试默认过期时间（1小时）
  const defaultExpire = manager.generateExpireTime();
  Assert.true(defaultExpire > now, '过期时间应该在未来');
  Assert.true(defaultExpire <= now + 3600, '默认过期时间应该不超过1小时');

  // 测试自定义过期时间（2小时）
  const customExpire = manager.generateExpireTime(2);
  Assert.true(customExpire > now + 3600, '自定义过期时间应该更长');
  Assert.true(customExpire <= now + 7200, '自定义过期时间应该不超过2小时');
});

runner.test('应该正确构建MQTT配置', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  const formData = {
    address: 'test.mqtt.com:8883',
    username: 'testuser',
    password: 'testpass',
    enable_tls: true
  };

  const config = manager.buildMqttConfig(formData, '1234567890ABCD');

  Assert.equal(config.address, 'test.mqtt.com:8883', '地址应该正确');
  Assert.equal(config.username, 'testuser', '用户名应该正确');
  Assert.equal(config.password, 'testpass', '密码应该正确');
  Assert.true(config.enable_tls, 'TLS应该启用');
  Assert.true(config.client_id.includes('1234567890ABCD'), '客户端ID应该包含设备SN');
  Assert.true(config.expire_time > Date.now() / 1000, '过期时间应该在未来');
});

runner.test('应该正确模拟连接测试', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  // 测试有效配置的连接测试
  const validConfig = {
    address: 'mqtt.dji.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass',
    enable_tls: true
  };

  let result = await manager.testConnection(validConfig);
  Assert.true(result.success, '有效配置应该连接成功');
  Assert.true(result.latency > 0, '应该返回延迟信息');

  // 测试无效配置
  const invalidConfig = {
    address: 'invalid-address',
    client_id: '',
    username: '',
    password: ''
  };

  result = await manager.testConnection(invalidConfig);
  Assert.false(result.success, '无效配置应该连接失败');
  Assert.equal(result.error, 'config_invalid', '应该返回配置错误');

  // 测试模拟的网络错误
  const networkErrorConfig = {
    address: 'invalid.host.com:8883',
    client_id: 'test-client',
    username: 'invalid',
    password: 'invalid'
  };

  result = await manager.testConnection(networkErrorConfig);
  Assert.false(result.success, '认证错误应该连接失败');
});

runner.test('应该提供正确的配置建议', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  const suggestions = manager.getConfigSuggestions('1234567890ABCD');

  Assert.true(Array.isArray(suggestions.address.suggestions), '地址建议应该是数组');
  Assert.true(suggestions.address.suggestions.length > 0, '应该有地址建议');
  Assert.true(Array.isArray(suggestions.client_id.suggestions), '客户端ID建议应该是数组');
  Assert.true(suggestions.client_id.suggestions.every(id => id.includes('1234567890ABCD')), '客户端ID建议应该包含设备SN');
  Assert.true(suggestions.tls.default, 'TLS应该默认启用');
});

runner.test('应该提供配置模板', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  const templates = manager.getConfigTemplates();

  Assert.true(typeof templates === 'object', '模板应该是对象');
  Assert.true('dji_official' in templates, '应该有DJI官方模板');
  Assert.true('local_emqx' in templates, '应该有本地EMQX模板');
  Assert.true('public_broker' in templates, '应该有公共服务器模板');

  // 验证模板结构
  const djiTemplate = templates.dji_official;
  Assert.true('name' in djiTemplate, '模板应该有名称');
  Assert.true('address' in djiTemplate, '模板应该有地址');
  Assert.true('description' in djiTemplate, '模板应该有描述');
});

runner.test('应该正确应用配置模板', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  const config = manager.applyTemplate('dji_official', '1234567890ABCD');

  Assert.true(config.address.includes('mqtt.dji.com'), '应该应用DJI官方地址');
  Assert.true(config.client_id.includes('1234567890ABCD'), '客户端ID应该包含设备SN');
  Assert.true(config.enable_tls, 'DJI官方模板应该启用TLS');
  Assert.equal(config.username, '', '用户名应该为空待填写');
  Assert.equal(config.password, '', '密码应该为空待填写');

  // 测试不存在的模板
  try {
    manager.applyTemplate('nonexistent', '1234567890ABCD');
    Assert.fail('应该抛出错误');
  } catch (error) {
    Assert.true(error.message.includes('未找到配置模板'), '应该有正确的错误消息');
  }
});

runner.test('应该正确获取字段显示名称', async () => {
  const { MqttBrokerManager } = await import('../helpers/mqtt-broker-manager-mock.js');
  const manager = new MqttBrokerManager();

  Assert.equal(manager.getFieldDisplayName('address'), '服务器地址', '地址字段应该有正确的显示名称');
  Assert.equal(manager.getFieldDisplayName('client_id'), '客户端ID', '客户端ID字段应该有正确的显示名称');
  Assert.equal(manager.getFieldDisplayName('username'), '用户名', '用户名字段应该有正确的显示名称');
  Assert.equal(manager.getFieldDisplayName('password'), '密码', '密码字段应该有正确的显示名称');
  Assert.equal(manager.getFieldDisplayName('unknown'), 'unknown', '未知字段应该返回原始名称');
});

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();