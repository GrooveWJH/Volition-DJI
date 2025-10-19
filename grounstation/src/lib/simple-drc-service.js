// 超简单的 DRC 服务 - 直接可在终端测试
import mqtt from 'mqtt';
import { randomBytes } from 'crypto';

const DEFAULT_TIMEOUT = 15000;

/**
 * 创建临时 MQTT 连接并执行服务调用
 */
async function callService(brokerConfig, sn, serviceName, data) {
  const { host, port, username, password } = brokerConfig;
  const brokerUrl = `ws://${host}:${port}/mqtt`;
  const clientId = `drc-${Date.now()}-${randomBytes(4).toString('hex')}`;

  console.log(`[DRC] 连接: ${brokerUrl}`);

  const client = mqtt.connect(brokerUrl, {
    clientId,
    username,
    password,
    clean: true,
    reconnectPeriod: 0,
  });

  return new Promise((resolve, reject) => {
    let done = false;
    let timer = null;

    const cleanup = () => {
      if (timer) clearTimeout(timer);
      client.end(true);
    };

    client.on('connect', () => {
      console.log(`[DRC] ✓ 已连接`);

      const replyTopic = `thing/product/${sn}/services_reply`;

      client.subscribe(replyTopic, { qos: 0 }, (err) => {
        if (err) {
          cleanup();
          if (!done) {
            done = true;
            reject(new Error(`订阅失败: ${err.message}`));
          }
          return;
        }

        console.log(`[DRC] ✓ 已订阅: ${replyTopic}`);

        const tid = `tid_${Date.now()}_${randomBytes(6).toString('hex')}`;
        const bid = `bid_${Date.now()}_${randomBytes(6).toString('hex')}`;

        const message = {
          method: serviceName,
          data,
          tid,
          bid,
          timestamp: Date.now(),
        };

        // 监听回复
        client.on('message', (topic, payload) => {
          console.log(`[DRC] ✓ 收到消息: ${topic}`);

          try {
            const reply = JSON.parse(payload.toString());
            console.log(`[DRC] 回复数据:`, reply);

            if (reply.tid === tid) {
              console.log(`[DRC] ✓✓✓ TID 匹配! result=${reply.data?.result}`);
              cleanup();
              if (!done) {
                done = true;
                resolve(reply);
              }
            }
          } catch (e) {
            console.error(`[DRC] 解析失败:`, e);
          }
        });

        // 发送请求
        const requestTopic = `thing/product/${sn}/services`;
        console.log(`[DRC] 发送到: ${requestTopic}`);
        console.log(`[DRC] 数据:`, message);

        client.publish(requestTopic, JSON.stringify(message), { qos: 0 }, (err) => {
          if (err) {
            cleanup();
            if (!done) {
              done = true;
              reject(new Error(`发送失败: ${err.message}`));
            }
          } else {
            console.log(`[DRC] ✓ 已发送 (tid: ${tid})`);
          }
        });

        // 超时
        timer = setTimeout(() => {
          cleanup();
          if (!done) {
            done = true;
            reject(new Error('超时'));
          }
        }, DEFAULT_TIMEOUT);
      });
    });

    client.on('error', (error) => {
      console.error(`[DRC] 错误:`, error);
      cleanup();
      if (!done) {
        done = true;
        reject(error);
      }
    });
  });
}

/**
 * 进入 DRC 模式
 */
export async function enterDrc(sn, mqttBroker, osdFreq = 30, hsiFreq = 10) {
  console.log(`\n========== 进入 DRC 模式 ==========`);
  console.log(`设备: ${sn}`);

  const data = {
    osd_frequency: osdFreq,
    hsi_frequency: hsiFreq,
    mqtt_broker: {
      address: mqttBroker.address,
      client_id: mqttBroker.client_id || `drc-${sn}`,
      username: mqttBroker.username || '',
      password: mqttBroker.password || '',
      enable_tls: mqttBroker.enable_tls || false,
      expire_time: mqttBroker.expire_time || Math.floor(Date.now() / 1000) + 3600,
    },
  };

  const brokerConfig = {
    host: mqttBroker.ws_host || '192.168.31.73',
    port: mqttBroker.ws_port || 8083,
    username: mqttBroker.username || 'admin',
    password: mqttBroker.password || '',
  };

  const reply = await callService(brokerConfig, sn, 'drc_mode_enter', data);

  if (reply.data?.result === 0) {
    console.log(`\n✓✓✓ DRC 模式进入成功! ✓✓✓\n`);
  } else {
    console.error(`\n✗ DRC 模式进入失败: result=${reply.data?.result}\n`);
  }

  return reply;
}

/**
 * 退出 DRC 模式
 */
export async function exitDrc(sn, brokerConfig) {
  console.log(`\n========== 退出 DRC 模式 ==========`);
  console.log(`设备: ${sn}`);

  const reply = await callService(brokerConfig, sn, 'drc_mode_exit', {});

  if (reply.data?.result === 0) {
    console.log(`\n✓✓✓ DRC 模式退出成功! ✓✓✓\n`);
  } else {
    console.error(`\n✗ DRC 模式退出失败: result=${reply.data?.result}\n`);
  }

  return reply;
}

/**
 * 发送心跳（简化版，不等待回复）
 * 使用 heart-{sn} 作为client_id
 */
export async function sendHeartbeat(sn, brokerConfig) {
  const { host, port, username, password } = brokerConfig;
  const brokerUrl = `ws://${host}:${port}/mqtt`;
  const clientId = `heart-${sn}`; // 心跳专用client_id

  const client = mqtt.connect(brokerUrl, {
    clientId,
    username,
    password,
    clean: true,
    reconnectPeriod: 0,
  });

  return new Promise((resolve, reject) => {
    client.on('connect', () => {
      const topic = `thing/product/${sn}/drc/down`;
      const message = {
        seq: Date.now(),
        method: 'heart_beat',
        data: { timestamp: Date.now() },
      };

      client.publish(topic, JSON.stringify(message), { qos: 0 }, (err) => {
        client.end();
        if (err) reject(err);
        else resolve(true);
      });
    });

    client.on('error', (error) => {
      client.end();
      reject(error);
    });
  });
}
