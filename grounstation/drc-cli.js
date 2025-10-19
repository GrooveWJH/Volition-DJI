#!/usr/bin/env node

/**
 * DRC CLI 工具
 * 用法：
 *   node drc-cli.js enter --sn=xxx --mqtt-host=xxx --mqtt-port=8083 --username=admin --password=xxx --osd-freq=30 --hsi-freq=10
 *   node drc-cli.js exit --sn=xxx --mqtt-host=xxx --mqtt-port=8083 --username=admin --password=xxx
 *   node drc-cli.js heartbeat --sn=xxx --mqtt-host=xxx --mqtt-port=8083 --username=admin --password=xxx
 *
 * 输出JSON格式到stdout，错误信息到stderr
 */

import { enterDrc, exitDrc, sendHeartbeat } from './src/lib/simple-drc-service.js';

// 解析命令行参数
function parseArgs() {
  const args = process.argv.slice(2);
  const command = args[0];
  const params = {};

  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith('--')) {
      const [key, value] = arg.slice(2).split('=');
      params[key] = value;
    }
  }

  return { command, params };
}

// 输出JSON结果
function output(success, result = 0, data = null, message = '', error = null) {
  const json = {
    success,
    result,
    data,
    message,
    error,
    timestamp: Date.now()
  };
  console.log(JSON.stringify(json));
}

// 主函数
async function main() {
  const { command, params } = parseArgs();

  // 验证必需参数
  if (!command || !params.sn) {
    output(false, -1, null, '', '缺少必需参数: command 和 --sn');
    process.exit(1);
  }

  const {
    sn,
    'mqtt-host': mqttHost = '192.168.31.73',
    'mqtt-port': mqttPort = '8083',
    username = '',
    password = '',
    'osd-freq': osdFreq = '30',
    'hsi-freq': hsiFreq = '10',
    'enable-tls': enableTls = 'false'
  } = params;

  try {
    switch (command) {
      case 'enter': {
        // 构建MQTT broker配置
        const mqttBroker = {
          ws_host: mqttHost,
          ws_port: parseInt(mqttPort),
          username,
          password,
          address: `${mqttHost}:${mqttPort === '8083' ? '1883' : mqttPort}`,
          client_id: `drc-${sn}`,
          enable_tls: enableTls === 'true',
          expire_time: Math.floor(Date.now() / 1000) + 3600,
        };

        const reply = await enterDrc(sn, mqttBroker, parseInt(osdFreq), parseInt(hsiFreq));

        const resultCode = reply?.data?.result;
        if (resultCode === 0) {
          output(true, resultCode, reply.data, 'DRC模式进入成功', null);
          process.exit(0);
        } else {
          output(false, resultCode, reply.data, 'DRC模式进入失败', `result code: ${resultCode}`);
          process.exit(1);
        }
        break;
      }

      case 'exit': {
        const brokerConfig = {
          host: mqttHost,
          port: parseInt(mqttPort),
          username,
          password,
        };

        const reply = await exitDrc(sn, brokerConfig);

        const resultCode = reply?.data?.result;
        if (resultCode === 0) {
          output(true, resultCode, reply.data, 'DRC模式退出成功', null);
          process.exit(0);
        } else {
          output(false, resultCode, reply.data, 'DRC模式退出失败', `result code: ${resultCode}`);
          process.exit(1);
        }
        break;
      }

      case 'heartbeat': {
        const brokerConfig = {
          host: mqttHost,
          port: parseInt(mqttPort),
          username,
          password,
        };

        await sendHeartbeat(sn, brokerConfig);
        output(true, 0, null, '心跳发送成功', null);
        process.exit(0);
        break;
      }

      default:
        output(false, -1, null, '', `未知命令: ${command}。支持的命令: enter, exit, heartbeat`);
        process.exit(1);
    }
  } catch (error) {
    output(false, -1, null, '', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

main();
