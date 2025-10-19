/**
 * AuthStateManager 单元测试
 * 测试授权状态管理、超时处理和用户配置持久化功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[AuthStateManager单元测试]');
const runner = new TestRunner('AuthStateManager 单元测试');

// Setup/teardown
runner.beforeEach(() => {
  mockBrowserEnvironment();
  global.console = {
    log: () => {},
    warn: () => {},
    error: () => {},
    table: () => {}
  }; // Mock console

  // Mock debugLogger to handle import
  global.debugLogger = {
    warn: () => {},
    info: () => {},
    error: () => {},
    debug: () => {}
  };
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
  delete global.console;
});

// Tests
runner.test('应该正确初始化默认状态', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  Assert.equal(manager.authStatus, 'unauthorized', '初始状态应该是 unauthorized');
  Assert.deepEqual(manager.controlKeys, [], '初始控制权应该为空');
  Assert.equal(manager.userId, 'cloud_user_001', '默认用户ID应该正确');
  Assert.equal(manager.userCallsign, 'CloudPilot', '默认用户呼号应该正确');
  Assert.equal(manager.authStartTime, null, '初始授权开始时间应该为空');
  Assert.equal(manager.currentRequestTid, null, '初始TID应该为空');
});

runner.test('应该正确设置和清除授权超时', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  let timeoutCalled = false;
  manager.setAuthTimeout(100, () => {
    timeoutCalled = true;
  });

  Assert.notNull(manager.authTimeout, '超时定时器应该被设置');

  manager.clearAuthTimeout();
  Assert.equal(manager.authTimeout, null, '超时定时器应该被清除');

  // 等待确保超时不会被触发
  await new Promise(resolve => setTimeout(resolve, 150));
  Assert.false(timeoutCalled, '清除后超时回调不应该被调用');
});

runner.test('授权超时应该重置状态', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  manager.startAuthRequest('test-tid');

  let timeoutCalled = false;
  manager.setAuthTimeout(50, () => {
    timeoutCalled = true;
  });

  // 等待超时触发
  await new Promise(resolve => setTimeout(resolve, 100));

  Assert.true(timeoutCalled, '超时回调应该被调用');
  Assert.equal(manager.authStatus, 'unauthorized', '超时后状态应该重置为 unauthorized');
  Assert.equal(manager.currentRequestTid, null, '超时后TID应该被清除');
  Assert.equal(manager.authStartTime, null, '超时后开始时间应该被清除');
});

runner.test('应该正确启动授权请求', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  const testTid = 'test-tid-123';
  const startTime = Date.now();

  manager.startAuthRequest(testTid);

  Assert.equal(manager.authStatus, 'requesting', '状态应该变为 requesting');
  Assert.equal(manager.currentRequestTid, testTid, 'TID应该被正确设置');
  Assert.true(manager.authStartTime >= startTime, '开始时间应该被设置');
  Assert.true(manager.authStartTime <= Date.now(), '开始时间应该合理');
});

runner.test('应该正确设置授权成功状态', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  manager.startAuthRequest('test-tid');
  manager.userCallsign = 'TestPilot';

  const beforeAuth = Date.now();
  manager.setAuthorized();
  const afterAuth = Date.now();

  Assert.equal(manager.authStatus, 'authorized', '状态应该变为 authorized');
  Assert.deepEqual(manager.controlKeys, ['flight'], '控制权应该包含 flight');
  Assert.equal(manager.authorizedUser, 'TestPilot', '授权用户应该正确');
  Assert.true(manager.authorizedAt >= beforeAuth && manager.authorizedAt <= afterAuth, '授权时间应该合理');
  Assert.equal(manager.authTimeout, null, '超时定时器应该被清除');
});

runner.test('应该正确重置授权状态', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  // 设置一些状态
  manager.startAuthRequest('test-tid');
  manager.setAuthorized();

  manager.resetAuth();

  Assert.equal(manager.authStatus, 'unauthorized', '状态应该重置为 unauthorized');
  Assert.deepEqual(manager.controlKeys, [], '控制权应该被清空');
  Assert.equal(manager.currentRequestTid, null, 'TID应该被清空');
  Assert.equal(manager.authorizedAt, null, '授权时间应该被清空');
  Assert.equal(manager.authorizedUser, null, '授权用户应该被清空');
  Assert.equal(manager.authStartTime, null, '开始时间应该被清空');
  Assert.equal(manager.authTimeout, null, '超时定时器应该被清除');
});

runner.test('应该正确计算授权持续时间', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  // 测试未开始时
  Assert.equal(manager.getAuthDuration(), 0, '未开始时持续时间应该为0');

  // 模拟授权开始
  manager.authStartTime = Date.now() - 5000; // 5秒前
  const duration = manager.getAuthDuration();

  Assert.true(duration >= 4 && duration <= 6, '持续时间应该约为5秒');
});

runner.test('应该正确验证TID', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  const testTid = 'test-tid-123';
  manager.currentRequestTid = testTid;

  Assert.true(manager.isValidTid(testTid), '相同TID应该验证通过');
  Assert.false(manager.isValidTid('other-tid'), '不同TID应该验证失败');
  Assert.false(manager.isValidTid(null), 'null TID应该验证失败');
});

runner.test('应该正确获取会话信息', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  // 未授权时应该返回null
  Assert.equal(manager.getSessionInfo(), null, '未授权时应该返回null');

  // 授权后应该返回正确信息
  manager.userCallsign = 'TestPilot';
  manager.setAuthorized();

  const sessionInfo = manager.getSessionInfo();
  Assert.notNull(sessionInfo, '授权后应该返回会话信息');
  Assert.equal(sessionInfo.user, 'TestPilot', '用户名应该正确');
  Assert.deepEqual(sessionInfo.controlKeys, ['flight'], '控制权应该正确');
  Assert.notNull(sessionInfo.authorizedAt, '授权时间应该存在');
  Assert.true(sessionInfo.duration >= 0, '持续时间应该大于等于0');
});

runner.test('应该正确保存和加载用户配置', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  // 测试保存配置
  manager.userId = 'test_user_123';
  manager.userCallsign = 'TestStation';
  manager.saveUserConfig();

  // 创建新实例测试加载
  const manager2 = new AuthStateManager();
  const loaded = manager2.loadUserConfig();

  Assert.true(loaded, '应该成功加载配置');
  Assert.equal(manager2.userId, 'test_user_123', '用户ID应该正确加载');
  Assert.equal(manager2.userCallsign, 'TestStation', '用户呼号应该正确加载');
});

runner.test('应该正确更新用户配置', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  manager.updateUserConfig('new_user', 'NewStation');

  Assert.equal(manager.userId, 'new_user', '用户ID应该被更新');
  Assert.equal(manager.userCallsign, 'NewStation', '用户呼号应该被更新');

  // 验证配置已保存
  const manager2 = new AuthStateManager();
  manager2.loadUserConfig();
  Assert.equal(manager2.userId, 'new_user', '更新的用户ID应该被持久化');
  Assert.equal(manager2.userCallsign, 'NewStation', '更新的用户呼号应该被持久化');
});

runner.test('应该正确获取状态摘要', async () => {
  const { AuthStateManager } = await import('../helpers/auth-state-manager-mock.js');
  const manager = new AuthStateManager();

  manager.startAuthRequest('test-tid');
  manager.setAuthorized();

  const summary = manager.getStatusSummary();

  Assert.equal(summary.authStatus, 'authorized', '状态摘要应该包含正确的授权状态');
  Assert.deepEqual(summary.controlKeys, ['flight'], '状态摘要应该包含正确的控制权');
  Assert.equal(summary.userId, 'cloud_user_001', '状态摘要应该包含用户ID');
  Assert.equal(summary.userCallsign, 'CloudPilot', '状态摘要应该包含用户呼号');
  Assert.notNull(summary.sessionInfo, '状态摘要应该包含会话信息');
  Assert.false(summary.hasActiveRequest, '授权完成后不应该有活跃请求');

  // 测试请求中状态
  manager.resetAuth();
  manager.startAuthRequest('active-tid');
  const activeSummary = manager.getStatusSummary();
  Assert.true(activeSummary.hasActiveRequest, '请求中应该有活跃请求');
});

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();