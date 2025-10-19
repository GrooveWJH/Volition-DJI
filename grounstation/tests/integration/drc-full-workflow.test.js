#!/usr/bin/env node
/**
 * DRC全流程集成测试
 *
 * 用法: node tests/integration/drc-full-workflow.test.js <设备SN>
 * 示例: node tests/integration/drc-full-workflow.test.js 9N9CN2J0012CXY
 */

// ==================== 配置参数 ====================
const CONFIG = {
  // 云端控制授权
  auth: {
    user_id: 'test_pilot_001',
    user_callsign: 'TestStation',
    control_keys: ['flight']
  },

  // DRC模式配置
  drc: {
    mqtt_broker: {
      address: '192.168.31.73:1883',
      username: 'admin',
      password: '302811055wjhhz',
      enable_tls: false
    },
    osd_frequency: 30,
    hsi_frequency: 10
  },

  // 心跳监测
  heartbeat: {
    duration: 10000  // 监测时长(ms)
  }
};

// ANSI颜色
const colors = {
  blue: '\x1b[34m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  red: '\x1b[31m',
  gray: '\x1b[90m',
  reset: '\x1b[0m'
};

// ==================== 导入业务代码 ====================
import { deviceContext } from '#lib/state.js';
import { mqttManager } from '#lib/mqtt.js';
import { topicServiceManager } from '#lib/services.js';
import { DrcModeController } from '#cards/DrcModeCard/controllers/drc-mode-controller.js';

// ==================== 测试类 ====================
class DrcWorkflowTest {
  constructor(sn) {
    this.sn = sn;
    this.heartbeatStats = {
      sent: 0,
      received: 0,
      lastSentSeq: null,
      lastRecvSeq: null
    };
    this.setupGlobals();
  }

  setupGlobals() {
    global.window = {
      addEventListener() {},
      dispatchEvent() {},
      setInterval, clearInterval,
      setTimeout, clearTimeout
    };
    global.localStorage = {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {}
    };
  }

  async run() {
    console.log(`${colors.cyan}🚀 DRC全流程测试 - ${this.sn}${colors.reset}\n`);

    try {
      await this.setupDevice();
      await this.testCloudControlAuth();
      await this.testDrcMode();
      console.log(`${colors.green}✅ 测试完成${colors.reset}`);
    } catch (error) {
      console.log(`${colors.red}❌ 测试失败: ${error.message}${colors.reset}`);
      process.exit(1);
    }
  }

  async setupDevice() {
    // 1. 设备选择
    deviceContext.setCurrentDevice(this.sn);
    console.log(`${colors.green}✅ 设备已选择: ${this.sn}${colors.reset}\n`);

    // 2. MQTT连接
    const connection = await mqttManager.ensureConnection(this.sn);
    if (!connection?.isConnected) {
      throw new Error('MQTT连接失败');
    }
    this.connection = connection;
    console.log(`${colors.green}✅ MQTT已连接 (ClientID: station-${this.sn})${colors.reset}\n`);

    // 3. 设置数据包监听
    this.setupPacketLogging();
    this.setupHeartbeatMonitoring();

    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  setupPacketLogging() {
    // 监听接收的消息
    this.connection.client.on('message', (topic, message) => {
      // 心跳消息特殊处理（不打印，只统计）
      if (topic.includes('/drc/up')) {
        try {
          const parsed = JSON.parse(message.toString());
          if (parsed.method === 'heart_beat') {
            this.heartbeatStats.received++;
            this.heartbeatStats.lastRecvSeq = parsed.seq;
            return;
          }
        } catch (e) {}
      }

      // 其他消息正常打印
      console.log(`${colors.green}[← 接收] ${topic}${colors.reset}`);
      try {
        console.log(JSON.stringify(JSON.parse(message.toString()), null, 2) + '\n');
      } catch (e) {
        console.log(message.toString() + '\n');
      }
    });

    // 拦截发送，打印数据包
    const originalPublish = this.connection.publish.bind(this.connection);
    this.connection.publish = async (topic, payload, options) => {
      // 心跳消息特殊处理（不打印，只统计）
      if (topic.includes('/drc/down')) {
        try {
          const parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
          if (parsed.method === 'heart_beat') {
            this.heartbeatStats.sent++;
            this.heartbeatStats.lastSentSeq = parsed.seq;
            return originalPublish(topic, payload, options);
          }
        } catch (e) {}
      }

      // 其他消息正常打印
      console.log(`${colors.blue}[→ 发送] ${topic}${colors.reset}`);
      try {
        const parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
        console.log(JSON.stringify(parsed, null, 2) + '\n');
      } catch (e) {
        console.log(payload + '\n');
      }
      return originalPublish(topic, payload, options);
    };
  }

  setupHeartbeatMonitoring() {
    this.heartbeatInterval = setInterval(() => {
      this.updateHeartbeatDisplay();
    }, 500);
  }

  updateHeartbeatDisplay() {
    if (!this.showingHeartbeat) return;

    // 清除之前的4行
    process.stdout.write('\x1b[4A\x1b[0J');

    const { sent, received, lastSentSeq, lastRecvSeq } = this.heartbeatStats;
    const elapsed = ((Date.now() - this.heartbeatStartTime) / 1000).toFixed(1);
    const sendRate = (sent / (elapsed || 1)).toFixed(1);
    const recvRate = (received / (elapsed || 1)).toFixed(1);

    console.log(`${colors.yellow}━━━ DRC心跳监测 ━━━${colors.reset}`);
    console.log(`${colors.blue}↓ 发送[${sent}]${colors.reset} | 频率: ${sendRate}Hz | seq: ${lastSentSeq || '-'}`);
    console.log(`${colors.green}↑ 接收[${received}]${colors.reset} | 频率: ${recvRate}Hz | seq: ${lastRecvSeq || '-'}`);
    console.log(`${colors.gray}已运行: ${elapsed}s${colors.reset}`);
  }

  async testCloudControlAuth() {
    console.log(`${colors.cyan}☁️  云端控制授权${colors.reset}`);

    // 使用业务代码调用授权服务
    const result = await topicServiceManager.callService(
      this.sn,
      'cloud_control_auth_request',
      CONFIG.auth
    );

    console.log(`${colors.yellow}📤 授权结果:${colors.reset}`);
    console.log(JSON.stringify(result, null, 2) + '\n');

    if (!result.success) {
      throw new Error(`授权失败: ${result.error?.message}`);
    }

    console.log(`${colors.green}✅ 授权请求已发送${colors.reset}`);
    console.log(`${colors.yellow}📱 请在遥控器上点击"允许"${colors.reset}`);
    console.log(`${colors.yellow}⏳ 完成后按回车继续...${colors.reset}\n`);

    await this.waitForEnter();
  }

  async testDrcMode() {
    console.log(`${colors.cyan}🛸 DRC模式测试${colors.reset}`);

    // 使用业务代码的DRC控制器
    const drcController = new DrcModeController();

    // 配置DRC参数
    drcController.updateMqttConfig({
      ...CONFIG.drc.mqtt_broker,
      client_id: `drc-${this.sn}`
    });
    drcController.osdFrequency = CONFIG.drc.osd_frequency;
    drcController.hsiFrequency = CONFIG.drc.hsi_frequency;

    // 进入DRC模式
    const drcResult = await drcController.enterDrcMode();
    console.log(`${colors.yellow}📤 DRC结果:${colors.reset}`);
    console.log(JSON.stringify(drcResult, null, 2) + '\n');

    if (!drcResult.success) {
      throw new Error(`DRC进入失败: ${drcResult.error?.message}`);
    }

    console.log(`${colors.green}✅ DRC模式已进入${colors.reset}\n`);

    // 启动心跳
    await this.testHeartbeat(drcController);
  }

  async testHeartbeat(drcController) {
    console.log(`${colors.cyan}💓 启动DRC心跳${colors.reset}\n`);

    // 重置统计
    this.heartbeatStats = { sent: 0, received: 0, lastSentSeq: null, lastRecvSeq: null };
    this.heartbeatStartTime = Date.now();
    this.showingHeartbeat = true;

    // 预留4行显示空间
    console.log('\n\n\n');

    // 使用业务代码启动心跳
    drcController.startHeartbeat();

    // 监测指定时长
    await new Promise(resolve => setTimeout(resolve, CONFIG.heartbeat.duration));

    // 停止心跳
    drcController.stopHeartbeat();
    this.showingHeartbeat = false;
    clearInterval(this.heartbeatInterval);

    // 最后更新一次显示
    this.updateHeartbeatDisplay();

    console.log(`\n${colors.green}✅ 心跳测试完成${colors.reset}\n`);
  }

  waitForEnter() {
    return new Promise((resolve) => {
      process.stdin.once('data', () => resolve());
    });
  }
}

// ==================== 主程序 ====================
const sn = process.argv[2];
if (!sn) {
  console.error(`${colors.red}错误: 缺少设备SN参数${colors.reset}`);
  console.log('用法: node tests/integration/drc-full-workflow.test.js <设备SN>');
  console.log('示例: node tests/integration/drc-full-workflow.test.js 9N9CN2J0012CXY');
  process.exit(1);
}

const test = new DrcWorkflowTest(sn);
test.run().catch(console.error);
