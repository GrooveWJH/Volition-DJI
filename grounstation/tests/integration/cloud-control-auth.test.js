#!/usr/bin/env node
/**
 * 云端控制授权集成测试
 *
 * 功能：创建真实的 MQTT 客户端，连接到 MQTT Broker，发送云端控制授权请求
 *
 * 使用方法：
 *   node cloud-control-auth.test.js <SN> [options]
 *
 * 参数：
 *   <SN>                    设备序列号 (14位, 例如: 9N9CN2J0012CXY)
 *   --host <host>           MQTT Broker 地址 (默认: 192.168.31.116)
 *   --port <port>           MQTT Broker 端口 (默认: 8083)
 *   --user-id <id>          用户ID (默认: test_user_001)
 *   --user-callsign <name>  用户呼号 (默认: TestStation)
 *   --timeout <ms>          超时时间 (默认: 30000)
 *   --release               测试释放控制 (而非请求授权)
 *
 * 示例：
 *   node cloud-control-auth.test.js 9N9CN2J0012CXY
 *   node cloud-control-auth.test.js 9N9CN2J0012CXY --host 192.168.1.100 --port 8083
 *   node cloud-control-auth.test.js 9N9CN2J0012CXY --release
 */

import mqtt from 'mqtt';
import { createLogger } from '../helpers/logger.js';
import { randomUUID } from 'crypto';

const logger = createLogger('[云端控制授权集成测试]');

// 解析命令行参数
function parseArgs(args) {
  const config = {
    sn: null,
    host: '192.168.31.116',
    port: 8083,
    userId: 'test_user_001',
    userCallsign: 'TestStation',
    timeout: 30000,
    release: false
  };

  for (let i = 2; i < args.length; i++) {
    const arg = args[i];

    if (!arg.startsWith('--')) {
      if (!config.sn) {
        config.sn = arg;
      }
      continue;
    }

    const flag = arg.slice(2);
    const value = args[i + 1];

    switch (flag) {
      case 'host':
        config.host = value;
        i++;
        break;
      case 'port':
        config.port = parseInt(value);
        i++;
        break;
      case 'user-id':
        config.userId = value;
        i++;
        break;
      case 'user-callsign':
        config.userCallsign = value;
        i++;
        break;
      case 'timeout':
        config.timeout = parseInt(value);
        i++;
        break;
      case 'release':
        config.release = true;
        break;
      default:
        logger.warn(`未知参数: --${flag}`);
    }
  }

  return config;
}

// 验证配置
function validateConfig(config) {
  if (!config.sn) {
    logger.error('缺少设备序列号参数');
    logger.info('使用方法: node cloud-control-auth.test.js <SN>');
    return false;
  }

  if (!/^[A-Z0-9]{14}$/.test(config.sn)) {
    logger.error(`无效的设备序列号: ${config.sn} (应为14位字母数字组合)`);
    return false;
  }

  return true;
}

// 生成消息 ID
function generateTid() {
  return `tid_${Date.now()}_${randomUUID().substring(0, 8)}`;
}

function generateBid() {
  return `bid_${Date.now()}_${randomUUID().substring(0, 8)}`;
}

// 构建云端控制授权请求消息
function buildAuthRequestMessage(config) {
  return {
    method: 'cloud_control_auth_request',
    data: {
      user_id: config.userId,
      user_callsign: config.userCallsign,
      control_keys: ['flight']
    },
    tid: generateTid(),
    bid: generateBid(),
    timestamp: Date.now()
  };
}

// 构建释放控制消息
function buildReleaseMessage(config) {
  return {
    method: 'cloud_control_release',
    data: {
      control_keys: ['flight']
    },
    tid: generateTid(),
    bid: generateBid(),
    timestamp: Date.now()
  };
}

// 主测试流程
async function runTest(config) {
  logger.header('云端控制授权集成测试');

  logger.info('测试配置:');
  logger.table({
    '设备序列号': config.sn,
    'MQTT Broker': `${config.host}:${config.port}`,
    '客户端ID': `station-${config.sn}`,
    '用户ID': config.userId,
    '用户呼号': config.userCallsign,
    '测试类型': config.release ? '释放控制' : '请求授权',
    '超时时间': `${config.timeout}ms`
  });

  return new Promise((resolve, reject) => {
    let client = null;
    let timeoutId = null;
    let requestMessage = null;

    // 步骤1: 创建 MQTT 客户端
    logger.section('步骤1: 创建 MQTT 客户端');
    const clientId = `station-${config.sn}`;
    const brokerUrl = `ws://${config.host}:${config.port}/mqtt`;

    logger.info(`连接到: ${brokerUrl}`);
    logger.info(`客户端ID: ${clientId}`);

    try {
      client = mqtt.connect(brokerUrl, {
        clientId,
        keepalive: 60,
        connectTimeout: 30000,
        reconnectPeriod: 0,
        clean: true
      });
    } catch (error) {
      logger.error(`MQTT 客户端创建失败: ${error.message}`);
      reject(error);
      return;
    }

    // 设置超时
    timeoutId = setTimeout(() => {
      logger.error(`测试超时 (${config.timeout}ms)`);
      client?.end();
      reject(new Error('Test timeout'));
    }, config.timeout);

    // 步骤2: 监听连接事件
    client.on('connect', () => {
      logger.success('MQTT 连接成功');

      // 步骤3: 订阅回复主题
      logger.section('步骤3: 订阅回复主题');
      const replyTopic = `thing/product/${config.sn}/services_reply`;

      client.subscribe(replyTopic, (err) => {
        if (err) {
          logger.error(`订阅失败: ${err.message}`);
          clearTimeout(timeoutId);
          client.end();
          reject(err);
          return;
        }

        logger.success(`订阅成功: ${replyTopic}`);

        // 步骤4: 发送授权请求
        logger.section('步骤4: 发送授权请求');
        const serviceTopic = `thing/product/${config.sn}/services`;

        if (config.release) {
          requestMessage = buildReleaseMessage(config);
          logger.info('发送释放控制消息:');
        } else {
          requestMessage = buildAuthRequestMessage(config);
          logger.info('发送授权请求消息:');
        }

        logger.info(JSON.stringify(requestMessage, null, 2));

        client.publish(serviceTopic, JSON.stringify(requestMessage), (err) => {
          if (err) {
            logger.error(`发送失败: ${err.message}`);
            clearTimeout(timeoutId);
            client.end();
            reject(err);
            return;
          }

          logger.success(`消息已发送到: ${serviceTopic}`);
          logger.info(`TID: ${requestMessage.tid}`);
          logger.info('等待回复...');
        });
      });
    });

    // 步骤5: 处理回复消息
    client.on('message', (topic, message) => {
      try {
        const reply = JSON.parse(message.toString());

        logger.section('步骤5: 收到回复消息');
        logger.info(`来自主题: ${topic}`);
        logger.info('回复内容:');
        logger.info(JSON.stringify(reply, null, 2));

        // 验证 TID 匹配
        if (reply.tid !== requestMessage.tid) {
          logger.warn(`TID 不匹配: ${reply.tid} !== ${requestMessage.tid}`);
          return;
        }

        logger.success('TID 匹配');

        // 检查结果
        const result = reply.data?.result;
        const status = reply.data?.output?.status;

        logger.section('步骤6: 分析结果');

        if (result === 0 && status === 'ok') {
          logger.success('✓ 授权请求成功');
          logger.success(`  Result: ${result}`);
          logger.success(`  Status: ${status}`);

          if (!config.release) {
            logger.info('');
            logger.info('🎉 云端控制授权已获批准！');
            logger.info('   遥控器应该已经显示授权确认弹窗并批准了请求');
            logger.info('   您现在拥有 flight 控制权');
          } else {
            logger.info('');
            logger.info('🎉 云端控制已释放！');
            logger.info('   控制权已成功归还给遥控器');
          }

          clearTimeout(timeoutId);
          client.end();
          resolve({ success: true, reply });

        } else {
          logger.error('✗ 授权请求失败');
          logger.error(`  Result: ${result}`);
          logger.error(`  Status: ${status || 'unknown'}`);

          if (result !== 0) {
            logger.error('');
            logger.error('可能的原因:');
            logger.error('  1. 遥控器用户拒绝了授权请求');
            logger.error('  2. 设备不支持云端控制功能');
            logger.error('  3. 设备当前状态不允许授权');
          }

          clearTimeout(timeoutId);
          client.end();
          reject(new Error(`Authorization failed: result=${result}`));
        }

      } catch (error) {
        logger.error(`处理回复消息失败: ${error.message}`);
        logger.debug('原始消息:', message.toString());
      }
    });

    // 错误处理
    client.on('error', (error) => {
      logger.error(`MQTT 连接错误: ${error.message}`);
      clearTimeout(timeoutId);
      client.end();
      reject(error);
    });

    client.on('close', () => {
      logger.info('MQTT 连接已关闭');
    });
  });
}

// 主程序入口
(async () => {
  try {
    const config = parseArgs(process.argv);

    if (!validateConfig(config)) {
      process.exit(1);
    }

    await runTest(config);

    logger.header('测试完成');
    logger.success('所有步骤执行成功');
    process.exit(0);

  } catch (error) {
    logger.header('测试失败');
    logger.error(error.message);
    if (error.stack) {
      logger.debug(error.stack);
    }
    process.exit(1);
  }
})();
