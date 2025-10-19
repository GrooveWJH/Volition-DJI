/**
 * LogManager 单元测试
 * 测试日志管理、过滤、统计和中央调试系统集成功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[LogManager单元测试]');
const runner = new TestRunner('LogManager 单元测试');

// Mock debugLogger
const mockDebugLogger = {
  info: () => {},
  warn: () => {},
  error: () => {},
  debug: () => {}
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
  // Mock elements
  global.mockElements = {
    logs: {
      innerHTML: '',
      scrollTop: 0,
      scrollHeight: 100
    }
  };
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
  delete global.mockElements;
});

// Tests
runner.test('应该正确初始化默认状态', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();

  Assert.equal(manager.logsHTML, '', '初始日志HTML应该为空');
  Assert.equal(manager.elements, null, '初始elements应该为null');
});

runner.test('应该正确设置DOM元素引用', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();

  const mockElements = { logs: global.mockElements.logs };
  manager.setElements(mockElements);

  Assert.equal(manager.elements, mockElements, 'elements应该被正确设置');
});

runner.test('应该正确添加日志条目', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();
  manager.setElements({ logs: global.mockElements.logs });

  manager.addLog('信息', '测试消息');

  Assert.true(manager.logsHTML.includes('测试消息'), '日志HTML应该包含消息内容');
  Assert.true(manager.logsHTML.includes('[信息]'), '日志HTML应该包含消息类型');
  Assert.true(manager.logsHTML.includes('data-log-type="信息"'), '日志HTML应该包含类型属性');
});

runner.test('应该正确应用日志类型样式', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();
  manager.setElements({ logs: global.mockElements.logs });

  const testCases = [
    { type: '成功', expectedClass: 'text-green-400' },
    { type: '错误', expectedClass: 'text-red-400' },
    { type: '警告', expectedClass: 'text-yellow-400' },
    { type: '帮助', expectedClass: 'text-blue-300' },
    { type: '提示', expectedClass: 'text-cyan-400' },
    { type: '信息', expectedClass: 'text-blue-400' }
  ];

  testCases.forEach(({ type, expectedClass }) => {
    manager.clearLogs();
    manager.addLog(type, `测试${type}消息`);
    Assert.true(manager.logsHTML.includes(expectedClass), `${type}类型应该使用${expectedClass}样式`);
  });
});

runner.test('应该正确过滤日志显示', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();
  manager.setElements({ logs: global.mockElements.logs });

  // 添加不同类型的日志
  manager.addLog('信息', '信息消息1');
  manager.addLog('错误', '错误消息1');
  manager.addLog('信息', '信息消息2');
  manager.addLog('警告', '警告消息1');

  // 测试过滤错误类型
  manager.filterLogs('错误');
  Assert.true(global.mockElements.logs.innerHTML.includes('错误消息1'), '应该显示错误消息');
  Assert.false(global.mockElements.logs.innerHTML.includes('信息消息1'), '不应该显示信息消息');

  // 测试显示全部
  manager.filterLogs('all');
  Assert.true(global.mockElements.logs.innerHTML.includes('信息消息1'), '显示全部时应该包含信息消息');
  Assert.true(global.mockElements.logs.innerHTML.includes('错误消息1'), '显示全部时应该包含错误消息');
});

runner.test('应该正确清空日志', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();
  manager.setElements({ logs: global.mockElements.logs });

  manager.addLog('信息', '测试消息');
  Assert.true(manager.logsHTML.includes('测试消息'), '添加后应该包含消息');

  manager.clearLogs();
  Assert.true(manager.logsHTML.includes('日志已清空'), '清空后应该显示清空消息');
  Assert.false(manager.logsHTML.includes('测试消息'), '清空后不应该包含原消息');
});

runner.test('应该正确计算日志统计信息', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();

  manager.addLog('信息', '信息1');
  manager.addLog('信息', '信息2');
  manager.addLog('错误', '错误1');
  manager.addLog('警告', '警告1');
  manager.addLog('成功', '成功1');

  const stats = manager.getLogStats();
  Assert.equal(stats.total, 5, '总数应该为5');
  Assert.equal(stats.信息, 2, '信息日志应该为2条');
  Assert.equal(stats.错误, 1, '错误日志应该为1条');
  Assert.equal(stats.警告, 1, '警告日志应该为1条');
  Assert.equal(stats.成功, 1, '成功日志应该为1条');
});

runner.test('空日志时统计信息应该正确', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();

  const stats = manager.getLogStats();
  Assert.equal(stats.total, 0, '空日志总数应该为0');
});

runner.test('应该正确获取日志HTML', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();

  manager.addLog('信息', '测试消息');
  const html = manager.getLogsHTML();

  Assert.equal(html, manager.logsHTML, 'getLogsHTML应该返回内部HTML');
  Assert.true(html.includes('测试消息'), '返回的HTML应该包含消息内容');
});

runner.test('应该正确从状态恢复日志', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();
  manager.setElements({ logs: global.mockElements.logs });

  // 模拟已有的日志状态
  manager.logsHTML = '<div class="text-blue-400">测试日志</div>';
  manager.restoreLogsFromState();

  Assert.true(global.mockElements.logs.innerHTML.includes('测试日志'), '应该恢复日志到DOM');
});

runner.test('无DOM元素时过滤日志应该安全处理', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();

  manager.addLog('信息', '测试消息');

  // 不设置elements，直接调用filterLogs应该不会报错
  Assert.doesNotThrow(() => {
    manager.filterLogs('all');
  }, '没有DOM元素时过滤应该安全处理');
});

runner.test('应该正确更新DOM显示并自动滚动', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();

  const mockLogsElement = {
    innerHTML: '',
    scrollTop: 0,
    scrollHeight: 200
  };

  manager.setElements({ logs: mockLogsElement });
  manager.addLog('信息', '测试消息');

  Assert.true(mockLogsElement.innerHTML.includes('测试消息'), 'DOM应该更新显示消息');
  Assert.equal(mockLogsElement.scrollTop, 200, '应该自动滚动到底部');
});

runner.test('过滤时找不到匹配日志应该显示提示', async () => {
  const { LogManager } = await import('../../src/cards/CloudControlCard/controllers/log-manager.js');
  const manager = new LogManager();
  manager.setElements({ logs: global.mockElements.logs });

  manager.addLog('信息', '信息消息');
  manager.filterLogs('错误'); // 过滤不存在的类型

  Assert.true(global.mockElements.logs.innerHTML.includes('没有找到 "错误" 类型的日志'), '应该显示无匹配日志提示');
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