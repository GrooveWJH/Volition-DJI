/**
 * MessageRouter 单元测试
 * 测试消息路由、规则匹配和回调执行功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[MessageRouter单元测试]');
const runner = new TestRunner('MessageRouter 单元测试');

// Setup/teardown
runner.beforeEach(() => {
  mockBrowserEnvironment();
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ dji_services: {} })
  });
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
  delete global.fetch;
});

// Tests
runner.test('应该成功注册路由规则', async () => {
  const { MessageRouter, ROUTE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  const ruleId = router.registerRoute('test-rule', { type: ROUTE_TYPES.EXACT, topic: 'test/topic' }, () => {
    // Test callback
  });

  Assert.equal(ruleId, 'test-rule', '应该返回正确的规则ID');
  Assert.true(router.routeRules.has('test-rule'), '路由规则应该被注册');
});

runner.test('应该成功注销路由规则', async () => {
  const { MessageRouter, ROUTE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  router.registerRoute('test-rule', { type: ROUTE_TYPES.EXACT, topic: 'test/topic' }, () => {});
  router.unregisterRoute('test-rule');

  Assert.false(router.routeRules.has('test-rule'), '路由规则应该被注销');
});

runner.test('EXACT 类型规则应该精确匹配主题', async () => {
  const { MessageRouter, ROUTE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  let matchedTopic = null;
  router.registerRoute('exact-rule', { type: ROUTE_TYPES.EXACT, topic: 'thing/product/SN123/services' }, (_msg, topic) => {
    matchedTopic = topic;
  });

  router.routeMessage({ test: 'data' }, 'thing/product/SN123/services', 'SN123');
  Assert.equal(matchedTopic, 'thing/product/SN123/services', '应该匹配正确的主题');

  matchedTopic = null;
  router.routeMessage({ test: 'data' }, 'thing/product/SN456/services', 'SN456');
  Assert.equal(matchedTopic, null, '不应该匹配不同的主题');
});

runner.test('PREFIX 类型规则应该匹配前缀', async () => {
  const { MessageRouter, ROUTE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  let matchCount = 0;
  router.registerRoute('prefix-rule', { type: ROUTE_TYPES.PREFIX, prefix: 'thing/product/' }, () => {
    matchCount++;
  });

  router.routeMessage({}, 'thing/product/SN123/services', 'SN123');
  router.routeMessage({}, 'thing/product/SN456/events', 'SN456');
  router.routeMessage({}, 'other/topic', null);

  Assert.equal(matchCount, 2, '应该匹配 2 个带前缀的主题');
});

runner.test('SERVICE 类型规则应该匹配服务回复', async () => {
  const { MessageRouter } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  let receivedMethod = null;
  router.registerServiceRoute('cloud_control_auth_request', (msg) => {
    receivedMethod = msg.method;
  });

  // 模拟服务回复消息
  const message = {
    method: 'cloud_control_auth_request',
    data: { result: 0 }
  };

  router.routeMessage(message, 'thing/product/SN123/services_reply', 'SN123');
  Assert.equal(receivedMethod, 'cloud_control_auth_request', '应该路由到正确的服务处理器');
});

runner.test('通配符 * 应该匹配所有服务回复', async () => {
  const { MessageRouter } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  let matchCount = 0;
  router.registerServiceRoute('*', () => {
    matchCount++;
  });

  router.routeMessage({ method: 'service1' }, 'thing/product/SN123/services_reply', 'SN123');
  router.routeMessage({ method: 'service2' }, 'thing/product/SN123/services_reply', 'SN123');
  router.routeMessage({ method: 'service3' }, 'thing/product/SN123/events', 'SN123');

  Assert.equal(matchCount, 2, '应该匹配所有服务回复消息');
});

runner.test('应该正确识别消息类型', async () => {
  const { MessageRouter, MESSAGE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  const topics = [
    { topic: 'thing/product/SN123/services_reply', expected: MESSAGE_TYPES.SERVICE_REPLY },
    { topic: 'thing/product/SN123/drc/up', expected: MESSAGE_TYPES.DRC_DATA },
    { topic: 'thing/product/SN123/events', expected: MESSAGE_TYPES.DEVICE_STATUS },
    { topic: 'thing/product/SN123/other', expected: MESSAGE_TYPES.UNKNOWN }
  ];

  topics.forEach(({ topic, expected }) => {
    const type = router._identifyMessageType(topic);
    Assert.equal(type, expected, `主题 ${topic} 应该识别为 ${expected}`);
  });
});

runner.test('应该正确从主题提取 SN', async () => {
  const { MessageRouter } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  const sn = router._extractSNFromTopic('thing/product/ABC123DEF45678/services');
  Assert.equal(sn, 'ABC123DEF45678', '应该提取正确的 14 位 SN');

  const noSN = router._extractSNFromTopic('invalid/topic');
  Assert.equal(noSN, null, '无效主题应该返回 null');
});

runner.test('应该正确解析 JSON 消息', async () => {
  const { MessageRouter } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  const obj = router._parseMessage({ test: 'data' });
  Assert.deepEqual(obj, { test: 'data' }, '应该返回对象本身');

  const parsed = router._parseMessage('{"test":"data"}');
  Assert.deepEqual(parsed, { test: 'data' }, '应该解析 JSON 字符串');

  const invalid = router._parseMessage('invalid json');
  Assert.equal(invalid, null, '无效 JSON 应该返回 null');
});

runner.test('应该收集统计信息', async () => {
  const { MessageRouter, ROUTE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  router.registerRoute('test-rule', { type: ROUTE_TYPES.EXACT, topic: 'test/topic' }, () => {});

  router.routeMessage({ method: 'test1' }, 'thing/product/SN123/services_reply', 'SN123');
  router.routeMessage({ method: 'test1' }, 'thing/product/SN123/services_reply', 'SN123');
  router.routeMessage({ method: 'test2' }, 'thing/product/SN123/services_reply', 'SN123');

  const stats = router.getStats();
  Assert.equal(stats.totalReceived, 3, '应该记录接收的消息数');
  Assert.equal(stats.registeredRules, 1, '应该记录注册的规则数');
  Assert.equal(stats.byServiceType.test1, 2, '应该统计 test1 服务调用次数');
  Assert.equal(stats.byServiceType.test2, 1, '应该统计 test2 服务调用次数');
});

runner.test('应该支持多个回调', async () => {
  const { MessageRouter, ROUTE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  let count1 = 0, count2 = 0;

  router.registerRoute('multi-rule', { type: ROUTE_TYPES.EXACT, topic: 'test/topic' }, () => { count1++; });
  router.registerRoute('multi-rule', { type: ROUTE_TYPES.EXACT, topic: 'test/topic' }, () => { count2++; });

  router.routeMessage({}, 'test/topic', null);

  Assert.equal(count1, 1, '第一个回调应该被调用');
  Assert.equal(count2, 1, '第二个回调应该被调用');
});

runner.test('回调异常不应该影响其他回调', async () => {
  const { MessageRouter, ROUTE_TYPES } = await import('../../src/lib/services.js');
  const router = new MessageRouter();

  let called = false;

  router.registerRoute('error-rule', { type: ROUTE_TYPES.EXACT, topic: 'test/topic' }, () => {
    throw new Error('Test error');
  });

  router.registerRoute('error-rule', { type: ROUTE_TYPES.EXACT, topic: 'test/topic' }, () => {
    called = true;
  });

  router.routeMessage({}, 'test/topic', null);

  Assert.true(called, '正常回调应该仍然被执行');
});

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();
