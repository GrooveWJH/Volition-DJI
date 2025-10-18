/**
 * TopicTemplateManager 单元测试
 * 测试消息模板管理、服务配置解析和消息构建功能
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const logger = createLogger('[TopicTemplateManager单元测试]');
const runner = new TestRunner('TopicTemplateManager 单元测试');

// Mock template data
const mockTemplates = {
  dji_services: {
    cloud_control_auth_request: {
      topic_template: "thing/product/{sn}/services",
      response_topic: "thing/product/{sn}/services_reply",
      method: "cloud_control_auth_request",
      timeout: 10000,
      required_params: ["user_id", "user_callsign"],
      default_values: { control_keys: ["flight"] }
    }
  }
};

// Setup/teardown
runner.beforeEach(async () => {
  mockBrowserEnvironment();
  // Mock fetch for template loading
  global.fetch = async (url) => ({
    ok: true,
    json: async () => mockTemplates
  });
});

runner.afterEach(async () => {
  cleanupBrowserEnvironment();
  delete global.fetch;
});

// Tests
runner.test('应该成功加载模板配置', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  Assert.true(manager.loaded, '模板应该加载完成');
  Assert.true(manager.hasService('cloud_control_auth_request'), '应该包含 cloud_control_auth_request 服务');
});

runner.test('应该正确构建服务主题', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  const topic = manager.buildServiceTopic('ABC123DEF45678', 'cloud_control_auth_request');
  Assert.equal(topic, 'thing/product/ABC123DEF45678/services', '主题应该正确替换 SN');
});

runner.test('应该正确构建响应主题', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  const topic = manager.buildResponseTopic('ABC123DEF45678', 'cloud_control_auth_request');
  Assert.equal(topic, 'thing/product/ABC123DEF45678/services_reply', '响应主题应该正确替换 SN');
});

runner.test('应该正确构建服务消息', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  const message = manager.buildServiceMessage('cloud_control_auth_request', {
    user_id: 'test_user',
    user_callsign: 'TestPilot'
  });

  Assert.equal(message.method, 'cloud_control_auth_request', '方法名应该正确');
  Assert.equal(message.data.user_id, 'test_user', 'user_id 应该正确');
  Assert.equal(message.data.user_callsign, 'TestPilot', 'user_callsign 应该正确');
  Assert.deepEqual(message.data.control_keys, ['flight'], '默认值应该正确');
  Assert.notNull(message.tid, 'tid 应该存在');
  Assert.notNull(message.bid, 'bid 应该存在');
  Assert.notNull(message.timestamp, 'timestamp 应该存在');
});

runner.test('缺少必需参数时应该抛出错误', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  Assert.throws(
    () => manager.buildServiceMessage('cloud_control_auth_request', { user_id: 'test' }),
    '缺少 user_callsign 应该抛出错误'
  );
});

runner.test('未知服务应该抛出错误', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  Assert.throws(
    () => manager.buildServiceTopic('SN123', 'unknown_service'),
    '未知服务应该抛出错误'
  );
});

runner.test('应该正确生成 TID 和 BID', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();

  const tid1 = manager.generateTid();
  const tid2 = manager.generateTid();
  const bid1 = manager.generateBid();
  const bid2 = manager.generateBid();

  Assert.notNull(tid1, 'TID 应该生成');
  Assert.notNull(bid1, 'BID 应该生成');
  Assert.true(tid1 !== tid2, '每次生成的 TID 应该不同');
  Assert.true(bid1 !== bid2, '每次生成的 BID 应该不同');
  Assert.true(tid1.startsWith('tid_'), 'TID 应该有正确的前缀');
  Assert.true(bid1.startsWith('bid_'), 'BID 应该有正确的前缀');
});

runner.test('应该返回正确的服务超时时间', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  const timeout = manager.getServiceTimeout('cloud_control_auth_request');
  Assert.equal(timeout, 10000, '超时时间应该为 10000ms');
});

runner.test('应该返回所有服务列表', async () => {
  const { TopicTemplateManager } = await import('../../src/lib/services.js');
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  const services = manager.getAllServices();
  Assert.true(Array.isArray(services), '应该返回数组');
  Assert.true(services.includes('cloud_control_auth_request'), '应该包含 cloud_control_auth_request');
});

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();
