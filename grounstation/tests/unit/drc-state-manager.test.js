/**
 * DrcStateManager 单元测试
 * 测试DRC状态管理、前置条件检查和配置管理功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[DrcStateManager单元测试]');
const runner = new TestRunner('DrcStateManager 单元测试');

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
runner.test('应该正确初始化默认状态', async () => {
  // Import DrcStateManager mock for testing
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  Assert.equal(manager.drcStatus, manager.DRC_STATES.IDLE, '初始DRC状态应该是 IDLE');
  Assert.false(manager.prerequisites.cloudControlAuthorized, '初始云端控制授权状态应该是 false');
  Assert.false(manager.prerequisites.mqttConnected, '初始MQTT连接状态应该是 false');
  Assert.false(manager.prerequisites.configValid, '初始配置状态应该是 false');
  Assert.equal(manager.osdFrequency, 10, '默认OSD频率应该是 10Hz');
  Assert.equal(manager.hsiFrequency, 1, '默认HSI频率应该是 1Hz');
  Assert.false(manager.canEnterDrcMode(), '初始状态不能进入DRC模式');
});

runner.test('应该正确验证MQTT配置', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  // 测试空配置
  Assert.false(manager.validateMqttConfig(), '空配置应该验证失败');

  // 测试完整配置
  manager.setMqttBrokerConfig({
    address: 'mqtt.test.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass'
  });

  Assert.true(manager.validateMqttConfig(), '完整配置应该验证成功');
  Assert.true(manager.prerequisites.configValid, '配置状态应该更新为有效');
});

runner.test('应该正确检查前置条件', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  // 初始状态不能进入DRC
  Assert.false(manager.canEnterDrcMode(), '初始状态不能进入DRC模式');

  // 设置云端控制授权
  manager.checkCloudControlStatus('authorized');
  Assert.false(manager.canEnterDrcMode(), '仅有授权还不能进入DRC模式');

  // 设置MQTT连接
  manager.updateMqttConnectionStatus(true);
  Assert.false(manager.canEnterDrcMode(), '仅有授权和连接还不能进入DRC模式');

  // 设置有效配置
  manager.setMqttBrokerConfig({
    address: 'mqtt.test.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass'
  });

  Assert.true(manager.canEnterDrcMode(), '所有前置条件满足后应该可以进入DRC模式');
});

runner.test('应该正确管理DRC状态转换', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  // 设置所有前置条件
  manager.checkCloudControlStatus('authorized');
  manager.updateMqttConnectionStatus(true);
  manager.setMqttBrokerConfig({
    address: 'mqtt.test.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass'
  });

  // 开始进入DRC模式
  manager.startEnteringDrc('test-tid-123');
  Assert.equal(manager.drcStatus, manager.DRC_STATES.ENTERING, 'DRC状态应该变为 ENTERING');
  Assert.equal(manager.currentRequestTid, 'test-tid-123', 'TID应该被正确设置');

  // 设置DRC激活
  manager.setDrcActive();
  Assert.equal(manager.drcStatus, manager.DRC_STATES.ACTIVE, 'DRC状态应该变为 ACTIVE');
  Assert.notNull(manager.enteredAt, '进入时间应该被设置');
  Assert.equal(manager.currentRequestTid, null, 'TID应该被清除');

  // 开始退出DRC模式
  manager.startExitingDrc();
  Assert.equal(manager.drcStatus, manager.DRC_STATES.EXITING, 'DRC状态应该变为 EXITING');

  // 重置DRC状态
  manager.resetDrcState();
  Assert.equal(manager.drcStatus, manager.DRC_STATES.IDLE, 'DRC状态应该重置为 IDLE');
  Assert.equal(manager.enteredAt, null, '进入时间应该被清除');
});

runner.test('应该正确处理频率配置', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  // 测试有效频率
  manager.setFrequencyConfig(15, 5);
  Assert.equal(manager.osdFrequency, 15, 'OSD频率应该被正确设置');
  Assert.equal(manager.hsiFrequency, 5, 'HSI频率应该被正确设置');

  // 测试边界值
  manager.setFrequencyConfig(1, 30);
  Assert.equal(manager.osdFrequency, 1, '最小OSD频率应该被接受');
  Assert.equal(manager.hsiFrequency, 30, '最大HSI频率应该被接受');

  // 测试无效频率（应该被忽略）
  manager.setFrequencyConfig(0, 31);
  Assert.equal(manager.osdFrequency, 1, '无效OSD频率应该被忽略');
  Assert.equal(manager.hsiFrequency, 30, '无效HSI频率应该被忽略');
});

runner.test('应该正确验证TID', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  Assert.false(manager.isValidTid('any-tid'), '无当前请求时应该返回 false');

  manager.currentRequestTid = 'test-tid-123';
  Assert.true(manager.isValidTid('test-tid-123'), '匹配的TID应该返回 true');
  Assert.false(manager.isValidTid('other-tid'), '不匹配的TID应该返回 false');
});

runner.test('应该正确构建MQTT消息', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  // 设置配置
  manager.setMqttBrokerConfig({
    address: 'mqtt.test.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass',
    enable_tls: true
  });
  manager.setFrequencyConfig(20, 3);

  const message = manager.buildMqttBrokerMessage();

  Assert.equal(message.mqtt_broker.address, 'mqtt.test.com:8883', '地址应该正确');
  Assert.equal(message.mqtt_broker.client_id, 'test-client', '客户端ID应该正确');
  Assert.equal(message.mqtt_broker.username, 'testuser', '用户名应该正确');
  Assert.equal(message.mqtt_broker.password, 'testpass', '密码应该正确');
  Assert.true(message.mqtt_broker.enable_tls, 'TLS应该启用');
  Assert.equal(message.osd_frequency, 20, 'OSD频率应该正确');
  Assert.equal(message.hsi_frequency, 3, 'HSI频率应该正确');
  Assert.true(message.mqtt_broker.expire_time > Date.now() / 1000, '过期时间应该在未来');
});

runner.test('应该正确处理错误状态', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  manager.setError('测试错误');

  Assert.equal(manager.drcStatus, manager.DRC_STATES.ERROR, 'DRC状态应该变为 ERROR');
  Assert.equal(manager.lastError, '测试错误', '错误信息应该被保存');
  Assert.equal(manager.currentRequestTid, null, 'TID应该被清除');
});

runner.test('应该正确获取状态摘要', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  // 设置一些状态
  manager.checkCloudControlStatus('authorized');
  manager.updateMqttConnectionStatus(true);
  manager.setMqttBrokerConfig({
    address: 'mqtt.test.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass'
  });

  const summary = manager.getStatusSummary();

  Assert.equal(summary.drcStatus, manager.DRC_STATES.IDLE, '状态摘要应该包含正确的DRC状态');
  Assert.true(summary.canEnterDrc, '状态摘要应该显示可以进入DRC');
  Assert.true(summary.prerequisites.cloudControlAuthorized, '状态摘要应该显示授权状态');
  Assert.true(summary.prerequisites.mqttConnected, '状态摘要应该显示连接状态');
  Assert.true(summary.prerequisites.configValid, '状态摘要应该显示配置状态');
  Assert.equal(summary.config.osdFrequency, 10, '状态摘要应该包含OSD频率');
  Assert.equal(summary.config.hsiFrequency, 1, '状态摘要应该包含HSI频率');
});

runner.test('应该正确处理CloudControl授权丢失', async () => {
  const { DrcStateManager } = await import('../helpers/drc-state-manager-mock.js');
  const manager = new DrcStateManager();

  // 设置初始授权状态
  manager.checkCloudControlStatus('authorized');
  Assert.true(manager.prerequisites.cloudControlAuthorized, '初始应该有授权');

  // 模拟进入DRC模式
  manager.updateMqttConnectionStatus(true);
  manager.setMqttBrokerConfig({
    address: 'mqtt.test.com:8883',
    client_id: 'test-client',
    username: 'testuser',
    password: 'testpass'
  });
  manager.startEnteringDrc('test-tid');
  manager.setDrcActive();

  Assert.equal(manager.drcStatus, manager.DRC_STATES.ACTIVE, 'DRC应该处于激活状态');

  // 授权丢失
  manager.checkCloudControlStatus('unauthorized');
  Assert.false(manager.prerequisites.cloudControlAuthorized, '授权状态应该更新');
  Assert.equal(manager.drcStatus, manager.DRC_STATES.IDLE, 'DRC状态应该被重置');
});

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();