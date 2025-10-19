#!/usr/bin/env node
/**
 * 设备扫描到MQTT连接建立流程集成测试
 * 极简版本 - 使用真实的EMQX API，打印所有数据包
 *
 * 用法:
 *   node device-scan-mqtt-connection.test.js
 *
 * 环境变量:
 *   EMQX_HOST      - EMQX API 主机地址 (默认: 192.168.31.209)
 *   EMQX_PORT      - EMQX API 端口 (默认: 18083)
 *   EMQX_API_KEY   - EMQX API Key
 *   EMQX_SECRET    - EMQX Secret Key
 *   MQTT_HOST      - MQTT Broker 主机 (默认: 192.168.31.116)
 *   MQTT_PORT      - MQTT Broker 端口 (默认: 8083)
 */

import mqtt from 'mqtt';

// ============ 配置 ============
const config = {
  emqx: {
    host: process.env.EMQX_HOST || '192.168.31.209',
    port: process.env.EMQX_PORT || '18083',
    apiKey: process.env.EMQX_API_KEY || 'ce9de7b674acfed7',
    secretKey: process.env.EMQX_SECRET || 'XaG9CEa2AserrayKx13MjlWPTJ29AYPdfB7KeXORhiVqP'
  },
  mqtt: {
    host: process.env.MQTT_HOST || '192.168.31.116',
    port: process.env.MQTT_PORT || '8083'
  }
};

// ============ 颜色输出 ============
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  gray: '\x1b[90m'
};

function log(color, prefix, message, data) {
  const timestamp = new Date().toISOString();
  console.log(`${colors.gray}[${timestamp}]${colors.reset} ${color}${prefix}${colors.reset} ${message}`);
  if (data) {
    console.log(`${colors.gray}${JSON.stringify(data, null, 2)}${colors.reset}`);
  }
}

// ============ 步骤1: 调用 EMQX API 扫描设备 ============
async function scanDevices() {
  const url = `http://${config.emqx.host}:${config.emqx.port}/api/v5/clients`;
  const auth = Buffer.from(`${config.emqx.apiKey}:${config.emqx.secretKey}`).toString('base64');

  log(colors.blue, '[→ HTTP REQUEST]', `GET ${url}`, {
    headers: {
      Authorization: `Basic ${auth.substring(0, 20)}...`
    }
  });

  const response = await fetch(url, {
    headers: {
      'Authorization': `Basic ${auth}`,
      'Content-Type': 'application/json'
    }
  });

  const data = await response.json();

  log(colors.green, '[← HTTP RESPONSE]', `Status: ${response.status}`, {
    total: data.data?.length || 0,
    clients: data.data?.map(c => c.clientid) || []
  });

  // 过滤DJI设备（clientid格式: station-{SN}）
  const djiDevices = (data.data || [])
    .filter(client => client.clientid && client.clientid.startsWith('station-'))
    .map(client => ({
      sn: client.clientid.replace('station-', ''),
      clientId: client.clientid,
      connected: client.connected,
      ip: client.ip_address,
      connectedAt: client.connected_at
    }));

  log(colors.cyan, '[📡 DEVICES FOUND]', `发现 ${djiDevices.length} 个DJI设备`, djiDevices);

  return djiDevices;
}

// ============ 步骤2: 建立MQTT连接 ============
async function connectMQTT(sn) {
  const clientId = `test-station-${sn}-${Date.now()}`;
  const url = `ws://${config.mqtt.host}:${config.mqtt.port}/mqtt`;

  log(colors.blue, '[→ MQTT CONNECT]', `连接到 ${url}`, {
    clientId,
    keepalive: 60,
    clean: true
  });

  const client = mqtt.connect(url, {
    clientId,
    keepalive: 60,
    clean: true
  });

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      client.end();
      reject(new Error('MQTT连接超时 (5秒)'));
    }, 5000);

    client.on('connect', () => {
      clearTimeout(timeout);
      log(colors.green, '[← MQTT CONNECTED]', '连接成功', {
        clientId,
        broker: `${config.mqtt.host}:${config.mqtt.port}`
      });
      resolve(client);
    });

    client.on('error', (error) => {
      clearTimeout(timeout);
      log(colors.red, '[✗ MQTT ERROR]', error.message);
      reject(error);
    });

    client.on('message', (topic, message) => {
      log(colors.yellow, '[← MQTT MESSAGE]', `收到消息: ${topic}`, {
        payload: message.toString()
      });
    });
  });
}

// ============ 步骤3: 订阅主题并发送测试消息 ============
async function testMQTTCommunication(client, sn) {
  const testTopic = `thing/product/${sn}/state`;
  const replyTopic = `thing/product/${sn}/state_reply`;

  // 订阅回复主题
  log(colors.blue, '[→ MQTT SUBSCRIBE]', `订阅主题: ${replyTopic}`);

  await new Promise((resolve, reject) => {
    client.subscribe(replyTopic, (err) => {
      if (err) {
        log(colors.red, '[✗ SUBSCRIBE ERROR]', err.message);
        reject(err);
      } else {
        log(colors.green, '[← MQTT SUBSCRIBED]', `订阅成功: ${replyTopic}`);
        resolve();
      }
    });
  });

  // 发送测试消息
  const testMessage = {
    method: 'state_query',
    timestamp: Date.now()
  };

  log(colors.blue, '[→ MQTT PUBLISH]', `发布到: ${testTopic}`, testMessage);

  client.publish(testTopic, JSON.stringify(testMessage), (err) => {
    if (err) {
      log(colors.red, '[✗ PUBLISH ERROR]', err.message);
    } else {
      log(colors.green, '[← MQTT PUBLISHED]', '消息已发送');
    }
  });

  // 等待5秒以接收可能的回复
  log(colors.cyan, '[⏳ WAITING]', '等待5秒接收回复...');
  await new Promise(resolve => setTimeout(resolve, 5000));
}

// ============ 主测试流程 ============
async function main() {
  console.log(`\n${'='.repeat(80)}`);
  log(colors.cyan, '[🚀 TEST START]', '设备扫描到MQTT连接集成测试');
  console.log(`${'='.repeat(80)}\n`);

  log(colors.cyan, '[⚙️  CONFIG]', '测试配置', config);

  try {
    // 步骤1: 扫描设备
    console.log(`\n${'-'.repeat(80)}`);
    log(colors.cyan, '[STEP 1]', '扫描EMQX在线设备');
    console.log(`${'-'.repeat(80)}\n`);

    const devices = await scanDevices();

    if (devices.length === 0) {
      log(colors.yellow, '[⚠️  WARNING]', '未发现任何DJI设备在线，测试结束');
      process.exit(0);
    }

    // 选择第一个设备进行测试
    const targetDevice = devices[0];
    log(colors.cyan, '[🎯 TARGET]', `选择设备: ${targetDevice.sn}`);

    // 步骤2: 建立MQTT连接
    console.log(`\n${'-'.repeat(80)}`);
    log(colors.cyan, '[STEP 2]', `建立MQTT连接到设备: ${targetDevice.sn}`);
    console.log(`${'-'.repeat(80)}\n`);

    const client = await connectMQTT(targetDevice.sn);

    // 步骤3: 测试MQTT通信
    console.log(`\n${'-'.repeat(80)}`);
    log(colors.cyan, '[STEP 3]', '测试MQTT消息收发');
    console.log(`${'-'.repeat(80)}\n`);

    await testMQTTCommunication(client, targetDevice.sn);

    // 清理
    console.log(`\n${'-'.repeat(80)}`);
    log(colors.blue, '[→ MQTT DISCONNECT]', '断开连接');
    client.end();
    log(colors.green, '[← MQTT DISCONNECTED]', '连接已断开');
    console.log(`${'-'.repeat(80)}\n`);

    // 测试成功
    console.log(`\n${'='.repeat(80)}`);
    log(colors.green, '[✓ TEST PASSED]', '集成测试成功完成');
    console.log(`${'='.repeat(80)}\n`);

    process.exit(0);

  } catch (error) {
    console.log(`\n${'='.repeat(80)}`);
    log(colors.red, '[✗ TEST FAILED]', '测试失败', {
      error: error.message,
      stack: error.stack
    });
    console.log(`${'='.repeat(80)}\n`);

    process.exit(1);
  }
}

// 运行测试
main();
