#!/usr/bin/env node

/**
 * DRC全流程集成测试
 *
 * 用法: node tests/integration/drc-full-workflow.test.js <设备SN>
 */

import { deviceContext } from '#lib/state.js';
import { mqttManager } from '#lib/mqtt.js';
import { DrcModeController } from '#cards/DrcModeCard/controllers/drc-mode-controller.js';
import { CloudControlCardUI } from '#cards/CloudControlCard/controllers/cloud-control-ui.js';

class DrcWorkflowTest {
  constructor(deviceSN) {
    this.deviceSN = deviceSN;
    this.drcController = null;
    this.cloudCard = null;
  }

  async run() {
    if (!this.deviceSN) {
      console.error('❌ 请提供设备SN');
      console.log('用法: node tests/integration/drc-full-workflow.test.js <设备SN>');
      process.exit(1);
    }

    console.log(`🚀 开始DRC全流程测试 - 设备: ${this.deviceSN}`);

    try {
      await this.setup();
      await this.testDeviceSelection();
      await this.testMqttConnection();
      await this.testCloudControlAuth();
      await this.testDrcEntry();
      await this.testHeartbeat();
      console.log('✅ 全流程测试完成');
    } catch (error) {
      console.error('❌ 测试失败:', error.message);
    }
  }

  async setup() {
    console.log('📦 初始化组件...');

    // 创建Node.js环境的模拟依赖
    global.window = {
      addEventListener() {},
      dispatchEvent() {},
      setInterval: setInterval,
      clearInterval: clearInterval,
      setTimeout: setTimeout,
      clearTimeout: clearTimeout
    };

    // 模拟localStorage
    global.localStorage = {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {}
    };

    // 初始化卡片实例
    this.drcController = new DrcModeController();
    this.cloudCard = new CloudControlCardUI();

    console.log('✅ 组件初始化完成');
  }

  async testDeviceSelection() {
    console.log('🔍 1. 设备选择测试...');

    // 直接设置当前设备
    deviceContext.setCurrentDevice(this.deviceSN);

    const currentDevice = deviceContext.getCurrentDevice();
    if (currentDevice !== this.deviceSN) {
      throw new Error(`设备设置失败: ${currentDevice}`);
    }

    console.log(`✅ 设备已选择: ${this.deviceSN}`);
  }

  async testMqttConnection() {
    console.log('🌐 2. MQTT连接测试...');

    // 调用生产代码建立MQTT连接
    const connection = await mqttManager.ensureConnection(this.deviceSN);

    if (!connection || !connection.isConnected) {
      throw new Error('MQTT连接失败');
    }

    console.log(`✅ MQTT连接已建立 (ClientID: station-${this.deviceSN})`);
  }

  async testCloudControlAuth() {
    console.log('☁️ 3. 云端控制授权测试...');

    // 配置云端控制参数
    const authConfig = {
      user_id: 'test_pilot_001',
      user_callsign: 'TestStation',
      expire_time: Math.floor(Date.now() / 1000) + 3600
    };

    console.log('📤 发送云端控制授权请求...');
    console.log(`👤 用户ID: ${authConfig.user_id}`);
    console.log(`📻 呼号: ${authConfig.user_callsign}`);

    // 调用生产代码发送授权
    const authResult = await this.cloudCard.requestAuth(authConfig);

    if (!authResult || !authResult.success) {
      throw new Error(`云端授权请求发送失败: ${authResult?.error || '未知错误(无回复/不成功)'}`);
    }

    console.log('✅ 云端控制授权请求已发送到遥控器');
    console.log('⚠️  请在遥控器上手动点击确认授权');
    console.log('⏳ 确认后请按回车键继续下一步测试...');

    // 等待用户手动确认
    await this.waitForUserInput();

    console.log('✅ 用户已确认，继续下一步测试');
  }

  async waitForUserInput() {
    return new Promise((resolve) => {
      process.stdin.once('data', () => {
        resolve();
      });
    });
  }

  async testDrcEntry() {
    console.log('🛸 4. DRC模式进入测试...');

    // 配置DRC参数
    const drcConfig = {
      mqtt_broker: {
        address: 'mqtt.dji.com:8883',
        client_id: `station-${this.deviceSN}`,
        username: 'drc_test_user',
        password: 'drc_test_pass',
        enable_tls: true,
        expire_time: Math.floor(Date.now() / 1000) + 3600
      },
      osd_frequency: 30,
      hsi_frequency: 5
    };

    console.log('📤 发送DRC模式进入请求...');
    console.log(`🔧 MQTT中继: ${drcConfig.mqtt_broker.address}`);
    console.log(`📊 OSD频率: ${drcConfig.osd_frequency}Hz`);
    console.log(`🧭 HSI频率: ${drcConfig.hsi_frequency}Hz`);

    // 调用生产代码进入DRC
    const drcResult = await this.drcController.enterDrcMode();

    if (!drcResult.success) {
      throw new Error(`DRC进入失败: ${drcResult.error}`);
    }

    console.log(`📋 DRC TID: ${drcResult.tid}`);

    // 等待DRC激活
    await this.waitForDrcActivation();

    console.log('✅ DRC模式已激活');
  }

  async waitForDrcActivation(timeout = 30000) {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();

      const checkDrc = () => {
        // 检查DRC状态
        const drcStatus = this.drcController.drcStatus;

        if (drcStatus === 'active') {
          resolve();
        } else if (Date.now() - startTime > timeout) {
          reject(new Error('DRC模式激活超时'));
        } else {
          setTimeout(checkDrc, 1000);
        }
      };

      checkDrc();
    });
  }

  async testHeartbeat() {
    console.log('💓 5. 心跳测试...');

    // 检查心跳是否启动
    const heartbeatActive = this.drcController.heartbeatActive;

    if (!heartbeatActive) {
      throw new Error('心跳未启动');
    }

    console.log('✅ 心跳已启动');

    // 验证心跳频率
    console.log('⏱️  验证心跳频率 (10秒)...');

    const initialCount = this.drcController.heartbeatSeq || 0;
    const startTime = Date.now();

    await new Promise(resolve => setTimeout(resolve, 10000));

    const finalCount = this.drcController.heartbeatSeq || 0;
    const elapsed = Date.now() - startTime;
    const heartbeatCount = finalCount - initialCount;
    const frequency = (heartbeatCount / elapsed * 1000).toFixed(1);

    console.log(`📊 10秒内发送 ${heartbeatCount} 个心跳`);
    console.log(`📈 平均频率: ${frequency}Hz`);

    if (heartbeatCount < 40) {  // 期望50个，允许误差
      throw new Error(`心跳频率过低: ${frequency}Hz (期望: ~5Hz)`);
    }

    console.log('✅ 心跳频率正常');
  }
}

// 运行测试
const deviceSN = process.argv[2];
const test = new DrcWorkflowTest(deviceSN);
test.run().catch(console.error);