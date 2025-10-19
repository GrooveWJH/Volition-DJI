/**
 * ErrorHandler 单元测试
 * 测试错误检测、验证、恢复建议和消息处理功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment, MockLocalStorage } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[ErrorHandler单元测试]');
const runner = new TestRunner('ErrorHandler 单元测试');

// Mock dependencies
class MockLogManager {
  constructor() {
    this.logs = [];
  }

  addLog(type, message) {
    this.logs.push({ type, message, timestamp: Date.now() });
  }

  getLastLog() {
    return this.logs[this.logs.length - 1];
  }

  getLogs() {
    return [...this.logs];
  }

  clear() {
    this.logs = [];
  }
}

class MockAuthStateManager {
  constructor() {
    this.authStatus = 'unauthorized';
    this.authStartTime = null;
    this.currentRequestTid = null;
  }

  resetAuth() {
    this.authStatus = 'unauthorized';
    this.authStartTime = null;
    this.currentRequestTid = null;
  }

  isValidTid(tid) {
    return this.currentRequestTid === tid;
  }

  setAuthorized() {
    this.authStatus = 'authorized';
  }

  getAuthDuration() {
    if (!this.authStartTime) return 0;
    return Math.round((Date.now() - this.authStartTime) / 1000);
  }
}

// Setup/teardown
runner.beforeEach(() => {
  mockBrowserEnvironment();
  global.window.mqttManager = {
    getConnection: (sn) => ({
      isConnected: sn === 'CONNECTED_DEVICE'
    })
  };
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
});

// Tests
runner.test('应该正确检测设备在线状态', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const handler = new ErrorHandler(mockLogManager);

  Assert.true(handler.isDeviceOnline('CONNECTED_DEVICE'), '连接的设备应该显示在线');
  Assert.false(handler.isDeviceOnline('OFFLINE_DEVICE'), '未连接的设备应该显示离线');
  Assert.false(handler.isDeviceOnline(null), 'null设备应该显示离线');
});

runner.test('应该正确验证授权请求参数', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const handler = new ErrorHandler(mockLogManager);

  // 测试有效参数
  const validResult = handler.validateAuthRequest('user123', 'Pilot', 'CONNECTED_DEVICE');
  Assert.true(validResult.isValid, '有效参数应该验证通过');
  Assert.equal(validResult.errors.length, 0, '有效参数不应该有错误');

  // 测试缺少设备
  const noDeviceResult = handler.validateAuthRequest('user123', 'Pilot', null);
  Assert.false(noDeviceResult.isValid, '缺少设备应该验证失败');
  Assert.true(noDeviceResult.errors.some(e => e.type === 'device_offline'), '应该包含设备离线错误');

  // 测试缺少用户信息
  const noUserResult = handler.validateAuthRequest('', '', 'CONNECTED_DEVICE');
  Assert.false(noUserResult.isValid, '缺少用户信息应该验证失败');
  Assert.true(noUserResult.errors.some(e => e.type === 'invalid_params'), '应该包含参数无效错误');

  // 测试设备离线
  const offlineResult = handler.validateAuthRequest('user123', 'Pilot', 'OFFLINE_DEVICE');
  Assert.false(offlineResult.isValid, '设备离线应该验证失败');
  Assert.true(offlineResult.errors.some(e => e.type === 'device_offline'), '应该包含设备离线错误');
});

runner.test('应该正确处理MQTT连接变化', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const mockAuthStateManager = new MockAuthStateManager();
  const handler = new ErrorHandler(mockLogManager);

  // Mock deviceContext
  global.deviceContext = {
    getCurrentDevice: () => 'TEST_DEVICE'
  };

  // 测试连接建立
  const connectInfo = { sn: 'TEST_DEVICE', connected: true };
  let result = handler.handleMqttConnectionChange(connectInfo, mockAuthStateManager);

  Assert.false(result.shouldUpdateUI, '连接建立不需要更新UI');
  const connectLog = mockLogManager.getLastLog();
  Assert.equal(connectLog.type, '信息', '连接建立应该记录信息日志');
  Assert.true(connectLog.message.includes('MQTT连接已建立'), '日志应该包含连接建立信息');

  // 测试请求中断开连接
  mockLogManager.clear();
  mockAuthStateManager.authStatus = 'requesting';
  const disconnectInfo = { sn: 'TEST_DEVICE', connected: false };
  result = handler.handleMqttConnectionChange(disconnectInfo, mockAuthStateManager);

  Assert.true(result.shouldUpdateUI, '请求中断开连接应该更新UI');
  Assert.equal(mockAuthStateManager.authStatus, 'unauthorized', '授权状态应该被重置');
  const logs = mockLogManager.getLogs();
  Assert.true(logs.some(log => log.type === '错误' && log.message.includes('授权请求期间连接断开')), '应该记录授权请求中断错误');

  delete global.deviceContext;
});

runner.test('应该正确处理服务调用错误', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const handler = new ErrorHandler(mockLogManager);

  // 测试普通错误
  const normalError = new Error('Network error');
  const normalResult = { error: { message: 'Service failed' } };
  const errorInfo = handler.handleServiceError(normalError, normalResult);

  Assert.equal(errorInfo.errorType, 'auth_rejected', '默认错误类型应该是auth_rejected');
  Assert.true(errorInfo.message.includes('Service failed'), '错误消息应该包含服务错误信息');

  // 测试超时错误
  mockLogManager.clear();
  const timeoutError = new Error('Timeout');
  timeoutError.name = 'TimeoutError';
  const timeoutResult = { error: { code: 'TIMEOUT' } };
  const timeoutInfo = handler.handleServiceError(timeoutError, timeoutResult);

  Assert.equal(timeoutInfo.errorType, 'timeout', '超时错误类型应该是timeout');

  // 测试连接错误
  mockLogManager.clear();
  const networkError = new Error('Connection failed');
  networkError.name = 'NetworkError';
  const networkResult = { error: { code: 'CONNECTION_FAILED' } };
  const networkInfo = handler.handleServiceError(networkError, networkResult);

  Assert.equal(networkInfo.errorType, 'connection_failed', '网络错误类型应该是connection_failed');
});

runner.test('应该正确处理授权回复消息', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const mockAuthStateManager = new MockAuthStateManager();
  const handler = new ErrorHandler(mockLogManager);

  mockAuthStateManager.currentRequestTid = 'test-tid-123';
  mockAuthStateManager.userCallsign = 'TestPilot';
  mockAuthStateManager.authStartTime = Date.now() - 5000;

  // 测试成功授权回复
  const successMsg = {
    tid: 'test-tid-123',
    data: { result: 0, output: { status: 'ok' } }
  };
  let result = handler.handleAuthReply(successMsg, mockAuthStateManager);

  Assert.true(result.shouldUpdateUI, '成功授权应该更新UI');
  const successLog = mockLogManager.getLogs().find(log => log.message.includes('云端控制授权已批准'));
  Assert.notNull(successLog, '应该记录授权成功日志');

  // 测试进行中回复
  mockLogManager.clear();
  mockAuthStateManager.resetAuth();
  mockAuthStateManager.currentRequestTid = 'test-tid-123';
  const progressMsg = {
    tid: 'test-tid-123',
    data: { result: 0, output: { status: 'in_progress' } }
  };
  result = handler.handleAuthReply(progressMsg, mockAuthStateManager);

  Assert.true(result.shouldUpdateUI, '进行中状态应该更新UI');
  const progressLogs = mockLogManager.getLogs();
  Assert.true(progressLogs.some(log => log.message.includes('授权请求已发送到遥控器')), '应该记录进行中状态');

  // 测试失败回复
  mockLogManager.clear();
  const failMsg = {
    tid: 'test-tid-123',
    data: { result: 1, output: { status: 'failed' } }
  };
  result = handler.handleAuthReply(failMsg, mockAuthStateManager);

  Assert.true(result.shouldUpdateUI, '失败回复应该更新UI');
  Assert.equal(mockAuthStateManager.authStatus, 'unauthorized', '失败后状态应该重置');

  // 测试TID不匹配
  mockLogManager.clear();
  const wrongTidMsg = {
    tid: 'wrong-tid',
    data: { result: 0, output: { status: 'ok' } }
  };
  result = handler.handleAuthReply(wrongTidMsg, mockAuthStateManager);

  Assert.false(result.shouldUpdateUI, 'TID不匹配不应该更新UI');
  const debugLog = mockLogManager.getLastLog();
  Assert.equal(debugLog.type, '调试', '应该记录调试日志');
});

runner.test('应该提供正确的错误恢复建议', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const handler = new ErrorHandler(mockLogManager);

  // 测试连接失败建议
  const connectionAdvice = handler.getErrorRecoveryAdvice('connection_failed');
  Assert.true(Array.isArray(connectionAdvice), '应该返回建议数组');
  Assert.true(connectionAdvice.some(advice => advice.includes('网络连接')), '应该包含网络连接建议');

  // 测试设备离线建议
  const deviceAdvice = handler.getErrorRecoveryAdvice('device_offline');
  Assert.true(deviceAdvice.some(advice => advice.includes('设备电源')), '应该包含设备电源建议');

  // 测试授权拒绝建议
  const authAdvice = handler.getErrorRecoveryAdvice('auth_rejected');
  Assert.true(authAdvice.some(advice => advice.includes('遥控器')), '应该包含遥控器操作建议');

  // 测试超时建议
  const timeoutAdvice = handler.getErrorRecoveryAdvice('timeout');
  Assert.true(timeoutAdvice.some(advice => advice.includes('网络延迟')), '应该包含网络延迟建议');

  // 测试未知错误类型
  const unknownAdvice = handler.getErrorRecoveryAdvice('unknown_error');
  Assert.true(unknownAdvice.some(advice => advice.includes('技术支持')), '未知错误应该建议联系技术支持');
});

runner.test('应该正确显示错误建议', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const handler = new ErrorHandler(mockLogManager);

  handler.showErrorAdvice('connection_failed');

  const logs = mockLogManager.getLogs();
  Assert.true(logs.some(log => log.type === '帮助' && log.message === '故障排除建议:'), '应该显示帮助标题');
  Assert.true(logs.some(log => log.type === '提示'), '应该包含提示日志');
  Assert.true(logs.length > 1, '应该记录多条建议日志');
});

runner.test('应该提供具体的错误建议', async () => {
  const { ErrorHandler } = await import('../helpers/error-handler-mock.js');
  const mockLogManager = new MockLogManager();
  const handler = new ErrorHandler(mockLogManager);

  // 测试result=1的情况
  handler.provideSpecificErrorAdvice(1);
  let lastLog = mockLogManager.getLastLog();
  Assert.true(lastLog.message.includes('遥控器用户拒绝'), 'result=1应该提示用户拒绝');

  // 测试result=2的情况
  mockLogManager.clear();
  handler.provideSpecificErrorAdvice(2);
  lastLog = mockLogManager.getLastLog();
  Assert.true(lastLog.message.includes('不支持云端控制'), 'result=2应该提示不支持功能');

  // 测试result=3的情况
  mockLogManager.clear();
  handler.provideSpecificErrorAdvice(3);
  lastLog = mockLogManager.getLastLog();
  Assert.true(lastLog.message.includes('当前状态不允许'), 'result=3应该提示状态不允许');
});

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();