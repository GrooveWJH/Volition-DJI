/**
 * UIUpdater 单元测试
 * 测试UI更新、视觉状态管理和用户界面同步功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[UIUpdater单元测试]');
const runner = new TestRunner('UIUpdater 单元测试');

// Mock AuthStateManager
class MockAuthStateManager {
  constructor() {
    this.authStatus = 'unauthorized';
    this.controlKeys = [];
    this.userId = 'test_user';
    this.userCallsign = 'TestPilot';
    this.authorizedAt = null;
    this.authorizedUser = null;
  }

  getSessionInfo() {
    if (this.authStatus === 'authorized') {
      return {
        user: this.authorizedUser,
        authorizedAt: this.authorizedAt,
        duration: this.authorizedAt ? Math.round((Date.now() - this.authorizedAt) / 1000) : 0,
        controlKeys: this.controlKeys
      };
    }
    return null;
  }
}

// Mock device context
const mockDeviceContext = {
  getCurrentDevice: () => 'TEST123456789'
};

// Setup/teardown
runner.beforeEach(() => {
  mockBrowserEnvironment();
  global.console = {
    log: () => {},
    warn: () => {},
    error: () => {},
    table: () => {}
  }; // Mock console
  global.window.deviceContext = mockDeviceContext;
  global.window.mqttManager = {
    getConnection: () => ({ isConnected: true })
  };

  // Mock DOM elements
  global.mockElements = {
    statusText: { textContent: '' },
    statusSpinner: { classList: { add: () => {}, remove: () => {} } },
    cloudStatus: { classList: { add: () => {}, remove: () => {} } },
    controlKeysDisplay: { textContent: '' },
    authInfo: { classList: { add: () => {}, remove: () => {} } },
    authDetails: { innerHTML: '' },
    requestBtn: { classList: { add: () => {}, remove: () => {} }, disabled: false },
    confirmBtn: { classList: { add: () => {}, remove: () => {} } },
    releaseBtn: { classList: { add: () => {}, remove: () => {} } },
    requestBtnSpinner: { classList: { add: () => {}, remove: () => {} } },
    requestBtnIcon: { classList: { add: () => {}, remove: () => {} } },
    requestBtnText: { textContent: '' },
    mqttStatus: { textContent: '', classList: { add: () => {}, remove: () => {} } },
    serialInput: { value: '' },
    userIdInput: { value: '' },
    userCallsignInput: { value: '' }
  };
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
  delete global.mockElements;
});

// Tests
runner.test('应该正确初始化', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();

  Assert.equal(updater.elements, null, '初始elements应该为null');
});

runner.test('应该正确设置DOM元素引用', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();

  updater.setElements(global.mockElements);
  Assert.equal(updater.elements, global.mockElements, 'elements应该被正确设置');
});

runner.test('应该正确更新状态显示', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  const authManager = new MockAuthStateManager();

  // 测试未授权状态
  authManager.authStatus = 'unauthorized';
  updater.updateStatusDisplay(authManager);
  Assert.equal(global.mockElements.statusText.textContent, '未授权', '未授权状态文本应该正确');

  // 测试请求中状态
  authManager.authStatus = 'requesting';
  updater.updateStatusDisplay(authManager);
  Assert.equal(global.mockElements.statusText.textContent, '请求中...', '请求中状态文本应该正确');

  // 测试已授权状态
  authManager.authStatus = 'authorized';
  updater.updateStatusDisplay(authManager);
  Assert.equal(global.mockElements.statusText.textContent, '已授权', '已授权状态文本应该正确');
});

runner.test('应该正确更新控制权显示', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  const authManager = new MockAuthStateManager();

  // 测试无控制权
  authManager.controlKeys = [];
  updater.updateControlKeysDisplay(authManager);
  Assert.equal(global.mockElements.controlKeysDisplay.textContent, '-', '无控制权时应该显示"-"');

  // 测试有控制权
  authManager.controlKeys = ['flight'];
  updater.updateControlKeysDisplay(authManager);
  Assert.equal(global.mockElements.controlKeysDisplay.textContent, 'flight', '有控制权时应该显示控制权列表');

  // 测试多个控制权
  authManager.controlKeys = ['flight', 'gimbal'];
  updater.updateControlKeysDisplay(authManager);
  Assert.equal(global.mockElements.controlKeysDisplay.textContent, 'flight, gimbal', '多个控制权应该用逗号分隔');
});

runner.test('应该正确更新授权信息显示', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  const authManager = new MockAuthStateManager();

  // 测试未授权时隐藏信息
  authManager.authStatus = 'unauthorized';
  const hiddenCalled = [];
  global.mockElements.authInfo.classList.add = (className) => {
    if (className === 'hidden') hiddenCalled.push('hidden');
  };
  updater.updateAuthInfoDisplay(authManager);
  Assert.true(hiddenCalled.includes('hidden'), '未授权时应该隐藏授权信息');

  // 测试已授权时显示信息
  authManager.authStatus = 'authorized';
  authManager.authorizedAt = Date.now() - 5000; // 5秒前
  authManager.authorizedUser = 'TestPilot';
  const removedCalled = [];
  global.mockElements.authInfo.classList.remove = (className) => {
    if (className === 'hidden') removedCalled.push('hidden');
  };

  updater.updateAuthInfoDisplay(authManager);
  Assert.true(removedCalled.includes('hidden'), '已授权时应该显示授权信息');
  Assert.true(global.mockElements.authDetails.innerHTML.includes('TestPilot'), '应该显示授权用户');
});

runner.test('应该正确更新按钮状态', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  const authManager = new MockAuthStateManager();

  // 测试未授权状态按钮
  authManager.authStatus = 'unauthorized';
  const requestBtnCalls = [];
  const confirmBtnCalls = [];
  const releaseBtnCalls = [];

  global.mockElements.requestBtn.classList.remove = (className) => requestBtnCalls.push(`remove-${className}`);
  global.mockElements.confirmBtn.classList.add = (className) => confirmBtnCalls.push(`add-${className}`);
  global.mockElements.releaseBtn.classList.add = (className) => releaseBtnCalls.push(`add-${className}`);

  updater.updateButtonStates(authManager);

  Assert.true(requestBtnCalls.includes('remove-hidden'), '未授权时应该显示请求按钮');
  Assert.true(confirmBtnCalls.includes('add-hidden'), '未授权时应该隐藏确认按钮');
  Assert.true(releaseBtnCalls.includes('add-hidden'), '未授权时应该隐藏释放按钮');

  // 测试请求中状态按钮
  authManager.authStatus = 'requesting';
  const requestBtnCalls2 = [];
  const confirmBtnCalls2 = [];

  global.mockElements.requestBtn.classList.add = (className) => requestBtnCalls2.push(`add-${className}`);
  global.mockElements.confirmBtn.classList.remove = (className) => confirmBtnCalls2.push(`remove-${className}`);

  updater.updateButtonStates(authManager);

  Assert.true(requestBtnCalls2.includes('add-hidden'), '请求中时应该隐藏请求按钮');
  Assert.true(confirmBtnCalls2.includes('remove-hidden'), '请求中时应该显示确认按钮');
});

runner.test('应该正确更新MQTT状态', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  // 测试有设备且已连接
  const addClassCalls = [];
  const removeClassCalls = [];
  global.mockElements.mqttStatus.classList.add = (className) => addClassCalls.push(className);
  global.mockElements.mqttStatus.classList.remove = (className) => removeClassCalls.push(className);

  updater.updateMqttStatus();

  Assert.equal(global.mockElements.mqttStatus.textContent, '已连接', '已连接设备应该显示"已连接"');
  Assert.true(addClassCalls.includes('text-green-600'), '已连接时应该使用绿色样式');

  // 测试无设备
  global.window.deviceContext.getCurrentDevice = () => null;
  updater.updateMqttStatus();
  Assert.equal(global.mockElements.mqttStatus.textContent, '未选择设备', '无设备时应该显示"未选择设备"');
});

runner.test('应该正确更新设备序列号', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  updater.updateDeviceSerial('ABC123DEF45678');
  Assert.equal(global.mockElements.serialInput.value, 'ABC123DEF45678', '应该正确设置设备序列号');

  updater.updateDeviceSerial(null);
  Assert.equal(global.mockElements.serialInput.value, '', '空设备序列号应该清空输入框');
});

runner.test('应该正确从状态恢复输入框', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  const authManager = new MockAuthStateManager();
  authManager.userId = 'restored_user';
  authManager.userCallsign = 'RestoredPilot';

  updater.restoreInputsFromState(authManager);

  Assert.equal(global.mockElements.userIdInput.value, 'restored_user', '应该恢复用户ID');
  Assert.equal(global.mockElements.userCallsignInput.value, 'RestoredPilot', '应该恢复用户呼号');
});

runner.test('应该正确更新完整UI', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();
  updater.setElements(global.mockElements);

  const authManager = new MockAuthStateManager();
  authManager.authStatus = 'authorized';
  authManager.controlKeys = ['flight'];

  // updateUI应该调用所有子更新方法
  updater.updateUI(authManager);

  Assert.equal(global.mockElements.statusText.textContent, '已授权', 'updateUI应该更新状态显示');
  Assert.equal(global.mockElements.controlKeysDisplay.textContent, 'flight', 'updateUI应该更新控制权显示');
});

runner.test('缺少DOM元素时应该安全处理', async () => {
  const { UIUpdater } = await import('../../src/cards/CloudControlCard/controllers/ui-updater.js');
  const updater = new UIUpdater();

  const authManager = new MockAuthStateManager();

  // 不设置elements，调用更新方法应该不会报错
  Assert.doesNotThrow(() => {
    updater.updateUI(authManager);
  }, '缺少DOM元素时应该安全处理');

  Assert.doesNotThrow(() => {
    updater.updateMqttStatus();
  }, '缺少DOM元素时MQTT状态更新应该安全处理');
});

// 添加断言辅助方法
Assert.doesNotThrow = function(fn, message = '') {
  try {
    fn();
  } catch (error) {
    throw new Error(`Assertion failed: ${message}\n  Function should not have thrown: ${error.message}`);
  }
};

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();