#!/usr/bin/env node

/**
 * DRC 服务终端测试脚本
 * 运行: node grounstation/test-drc-service.js
 */

import { enterDrc, exitDrc } from './src/lib/simple-drc-service.js';

// 配置
const DEVICE_SN = '9N9CN2J0012CXY';

const MQTT_BROKER = {
  // WebSocket 连接配置
  ws_host: '192.168.31.73',
  ws_port: 8083,
  username: 'admin',
  password: '302811055wjhhz',

  // DRC 模式配置
  address: '192.168.31.73:1883',
  client_id: `station-${DEVICE_SN}`,
  enable_tls: false,
};

async function test() {
  console.log('\n╔══════════════════════════════════════╗');
  console.log('║   DRC 服务终端测试                  ║');
  console.log('╚══════════════════════════════════════╝\n');

  try {
    // 测试 1: 进入 DRC 模式
    console.log('📍 测试 1: 进入 DRC 模式');
    const enterReply = await enterDrc(DEVICE_SN, MQTT_BROKER, 30, 10);

    if (enterReply.data?.result !== 0) {
      console.error('❌ 进入 DRC 失败，停止测试');
      process.exit(1);
    }

    console.log('⏳ 等待 3 秒...\n');
    await new Promise((resolve) => setTimeout(resolve, 3000));

    // 测试 2: 退出 DRC 模式
    console.log('📍 测试 2: 退出 DRC 模式');
    const exitReply = await exitDrc(DEVICE_SN, {
      host: MQTT_BROKER.ws_host,
      port: MQTT_BROKER.ws_port,
      username: MQTT_BROKER.username,
      password: MQTT_BROKER.password,
    });

    if (exitReply.data?.result !== 0) {
      console.error('❌ 退出 DRC 失败');
      process.exit(1);
    }

    console.log('\n╔══════════════════════════════════════╗');
    console.log('║   ✓✓✓ 所有测试通过! ✓✓✓           ║');
    console.log('╚══════════════════════════════════════╝\n');

    process.exit(0);
  } catch (error) {
    console.error('\n❌ 测试失败:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

test();
