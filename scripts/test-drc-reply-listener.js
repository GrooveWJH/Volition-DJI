#!/usr/bin/env node

/**
 * 测试脚本：验证 DRC 模式进入请求和回复监听
 * 用途：直接测试 MQTT 消息发送和 services_reply 监听功能
 */

import mqtt from 'mqtt';
import { randomBytes } from 'crypto';

// 配置
const MQTT_CONFIG = {
  host: '192.168.31.73',
  port: 1883,
  username: 'admin',
  password: '302811055wjhhz',
};

const DEVICE_SN = '9N9CN2J0012CXY';
const TEST_TIMEOUT = 20000; // 20秒超时

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
};

function log(color, prefix, message, data = null) {
  const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  console.log(`${color}[${timestamp}] [${prefix}]${colors.reset} ${message}`);
  if (data) {
    console.log(`${color}${JSON.stringify(data, null, 2)}${colors.reset}`);
  }
}

function generateTid() {
  return `tid_${Date.now()}_${randomBytes(6).toString('hex')}`;
}

function generateBid() {
  return `bid_${Date.now()}_${randomBytes(6).toString('hex')}`;
}

async function testDrcReplyListener() {
  log(colors.cyan, '系统', '=== DRC Reply 监听测试开始 ===');

  const brokerUrl = `mqtt://${MQTT_CONFIG.host}:${MQTT_CONFIG.port}`;
  log(colors.cyan, '连接', `正在连接到 MQTT Broker: ${brokerUrl}`);

  const client = mqtt.connect(brokerUrl, {
    clientId: `test-drc-${Date.now()}`,
    username: MQTT_CONFIG.username,
    password: MQTT_CONFIG.password,
    clean: true,
    reconnectPeriod: 0,
  });

  return new Promise((resolve) => {
    let isResolved = false;
    let timer = null;

    client.on('connect', () => {
      log(colors.green, '连接', '✓ MQTT 连接成功');

      // 1. 订阅 services_reply topic
      const replyTopic = `thing/product/${DEVICE_SN}/services_reply`;
      log(colors.yellow, '订阅', `正在订阅: ${replyTopic}`);

      client.subscribe(replyTopic, { qos: 0 }, (err) => {
        if (err) {
          log(colors.red, '错误', '订阅失败', { error: err.message });
          cleanup(1);
          return;
        }

        log(colors.green, '订阅', `✓ 订阅成功: ${replyTopic}`);

        // 2. 设置消息监听器
        const tid = generateTid();
        const bid = generateBid();

        log(colors.magenta, '监听', `开始监听回复消息 (tid: ${tid})`);

        client.on('message', (topic, payload) => {
          log(colors.cyan, '收到消息', `Topic: ${topic}`);
          log(colors.cyan, '原始数据', `Payload 长度: ${payload.length} bytes`);

          const raw = payload.toString();
          log(colors.cyan, '原始 JSON', raw);

          try {
            const parsed = JSON.parse(raw);
            log(colors.green, '解析成功', '解析后的数据:', parsed);

            if (parsed.tid === tid) {
              log(colors.green, '✓ 匹配', `找到匹配的回复 (tid: ${tid})`);
              log(colors.green, '结果代码', `result: ${parsed.data?.result}`);
              cleanup(0);
            } else {
              log(colors.yellow, '不匹配', `TID 不匹配 (收到: ${parsed.tid}, 期望: ${tid})`);
            }
          } catch (error) {
            log(colors.red, '解析错误', error.message);
          }
        });

        // 3. 发送 DRC 进入请求
        setTimeout(() => {
          const requestTopic = `thing/product/${DEVICE_SN}/services`;
          const requestPayload = {
            method: 'drc_mode_enter',
            data: {
              osd_frequency: 30,
              hsi_frequency: 10,
              mqtt_broker: {
                address: `${MQTT_CONFIG.host}:${MQTT_CONFIG.port}`,
                client_id: `station-${DEVICE_SN}`,
                username: MQTT_CONFIG.username,
                password: MQTT_CONFIG.password,
                enable_tls: false,
                expire_time: Math.floor(Date.now() / 1000) + 3600,
              },
            },
            tid,
            bid,
            timestamp: Date.now(),
          };

          log(colors.yellow, '发送请求', `Topic: ${requestTopic}`);
          log(colors.yellow, '请求数据', '完整请求负载:', requestPayload);

          client.publish(requestTopic, JSON.stringify(requestPayload), { qos: 0 }, (err) => {
            if (err) {
              log(colors.red, '发送失败', err.message);
              cleanup(1);
            } else {
              log(colors.green, '发送成功', `✓ 请求已发送 (tid: ${tid})`);
            }
          });
        }, 500);

        // 4. 设置超时
        timer = setTimeout(() => {
          log(colors.red, '超时', `${TEST_TIMEOUT / 1000}秒内未收到回复`);
          cleanup(1);
        }, TEST_TIMEOUT);
      });
    });

    client.on('error', (error) => {
      log(colors.red, '错误', 'MQTT 错误', { error: error.message });
      cleanup(1);
    });

    client.on('close', () => {
      log(colors.yellow, '连接', '连接已关闭');
    });

    function cleanup(exitCode) {
      if (isResolved) return;
      isResolved = true;

      if (timer) clearTimeout(timer);

      log(colors.cyan, '清理', '正在断开连接...');
      client.end(false, {}, () => {
        log(colors.cyan, '系统', '=== 测试结束 ===');
        resolve(exitCode);
        process.exit(exitCode);
      });
    }
  });
}

// 运行测试
testDrcReplyListener().catch((error) => {
  log(colors.red, '异常', '未捕获的错误', { error: error.message, stack: error.stack });
  process.exit(1);
});
