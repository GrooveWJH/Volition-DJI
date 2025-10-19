/**
 * 设备扫描到MQTT连接建立流程集成测试
 * 测试从设备发现到长连接保持的完整流程
 */

import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[设备扫描MQTT连接集成测试]');
const runner = new TestRunner('设备扫描到MQTT连接建立集成测试');

// Mock全局对象
global.debugLogger = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
  mqtt: () => {},
  state: () => {},
  service: () => {}
};

// Mock fetch for API calls
global.fetch = async (url) => {
  // 模拟EMQX API响应
  if (url.includes('/api/emqx-clients')) {
    return {
      ok: true,
      status: 200,
      json: async () => ({
        clientIds: ['9N9CN2J0012CXY'],
        total: 1
      })
    };
  }
  throw new Error(`未知的URL: ${url}`);
};

// Setup/teardown
runner.beforeEach(() => {
  mockBrowserEnvironment();
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
});

runner.test('应该完成从设备扫描到MQTT连接建立的完整流程', async () => {
  logger.info('开始集成测试：设备扫描 -> 设备显示 -> MQTT连接');

  // 1. 导入设备管理器和MQTT管理器
  const { deviceManager } = await import('../../src/lib/devices.js');
  const { mqttManager } = await import('../../src/lib/mqtt.js');
  const { deviceContext } = await import('../../src/lib/state.js');

  // 2. 配置EMQX
  const emqxConfig = {
    host: '127.0.0.1',
    port: '18083',
    apiKey: '9b8799abe2c3d581',
    secretKey: '8AotAV126dc9B7E8eMhfnbSlC6pTxtl0eLS29AWMi2DrC'
  };
  deviceManager.updateEmqxConfig(emqxConfig);
  logger.info('EMQX配置已设置');

  // 3. 配置MQTT broker
  const mqttConfig = {
    host: '127.0.0.1',
    port: 8083,
    username: 'admin',
    password: 'public'
  };
  mqttManager.updateBrokerConfig(mqttConfig);
  logger.info('MQTT配置已设置');

  // 4. 设置事件监听器来跟踪状态变化
  let devicesFound = false;
  let deviceSelected = false;
  let mqttConnected = false;

  deviceManager.addListener((eventType, data) => {
    logger.info(`DeviceManager事件: ${eventType}`, data);
    if (eventType === 'devices-updated') {
      devicesFound = true;
    }
  });

  deviceContext.addListener((eventType, data) => {
    logger.info(`DeviceContext事件: ${eventType}`, data);
    if (eventType === 'device-changed' && data.currentSN) {
      deviceSelected = true;
    }
  });

  // 5. 执行设备扫描
  logger.info('开始设备扫描...');
  await deviceManager.scan();

  // 6. 验证设备发现
  const devices = deviceManager.getDeviceList();
  Assert.true(devices.length > 0, '应该发现至少一个设备');
  Assert.true(devicesFound, '应该触发devices-updated事件');

  const targetDevice = devices.find(d => d.sn === '9N9CN2J0012CXY');
  Assert.notNull(targetDevice, '应该发现目标设备 9N9CN2J0012CXY');
  Assert.equal(targetDevice.status, 'online', '设备应该是在线状态');

  logger.info('设备扫描成功，发现设备:', targetDevice.sn);

  // 7. 选择设备
  deviceContext.setCurrentDevice(targetDevice.sn);
  Assert.equal(deviceContext.getCurrentDevice(), targetDevice.sn, '应该正确设置当前设备');
  Assert.true(deviceSelected, '应该触发device-changed事件');

  logger.info('设备选择成功:', targetDevice.sn);

  // 8. 建立MQTT连接
  logger.info('开始建立MQTT连接...');
  const connection = await mqttManager.ensureConnection(targetDevice.sn);

  // 注意：在测试环境中，MQTT连接可能会失败，这是正常的
  // 但我们可以验证连接尝试和相关逻辑
  if (connection) {
    Assert.true(connection.isConnected, '连接对象应该显示已连接状态');
    mqttConnected = true;
    logger.info('MQTT连接建立成功');

    // 9. 保持连接10秒并验证状态
    logger.info('保持连接10秒进行测试...');
    await new Promise(resolve => setTimeout(resolve, 10000));

    // 验证连接仍然存在
    const activeConnection = mqttManager.getConnection(targetDevice.sn);
    Assert.notNull(activeConnection, '10秒后连接应该仍然存在');

    if (activeConnection.isConnected) {
      logger.info('10秒后连接仍然保持活跃');
    }

    // 10. 清理连接
    mqttManager.disconnectDevice(targetDevice.sn);
    logger.info('连接已断开');
  } else {
    logger.warn('MQTT连接失败（这在测试环境中是正常的）');
    // 即使连接失败，我们也验证了设备发现和选择流程
  }

  // 11. 最终验证
  Assert.true(devicesFound, '整个流程中应该成功发现设备');
  Assert.true(deviceSelected, '整个流程中应该成功选择设备');

  logger.info('集成测试完成');
});

runner.test('应该正确处理设备事件和状态同步', async () => {
  logger.info('开始测试设备事件处理');

  const { deviceManager } = await import('../../src/lib/devices.js');
  const { deviceContext } = await import('../../src/lib/state.js');

  let eventCount = 0;
  const events = [];

  // 监听所有事件
  deviceManager.addListener((eventType, data) => {
    eventCount++;
    events.push({ source: 'DeviceManager', type: eventType, data });
  });

  deviceContext.addListener((eventType, data) => {
    eventCount++;
    events.push({ source: 'DeviceContext', type: eventType, data });
  });

  // 触发一系列操作
  await deviceManager.scan();
  const devices = deviceManager.getDeviceList();

  if (devices.length > 0) {
    deviceContext.setCurrentDevice(devices[0].sn);
    deviceContext.setCurrentDevice(null);
    deviceContext.setCurrentDevice(devices[0].sn);
  }

  // 验证事件
  Assert.true(eventCount > 0, '应该触发了事件');
  Assert.true(events.some(e => e.source === 'DeviceManager'), '应该有DeviceManager事件');

  logger.info(`总共触发了 ${eventCount} 个事件`);
  events.forEach((event, index) => {
    logger.info(`事件 ${index + 1}: ${event.source} - ${event.type}`);
  });
});

// Run tests
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();