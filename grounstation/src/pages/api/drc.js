/**
 * DRC模式控制API
 *
 * POST /api/drc
 * 请求体：
 * {
 *   "action": "enter" | "exit" | "heartbeat",
 *   "sn": "9N9CN2J0012CXY",
 *   "mqttHost": "192.168.31.73",
 *   "mqttPort": 8083,
 *   "username": "admin",
 *   "password": "xxx",
 *   "osdFreq": 30,
 *   "hsiFreq": 10,
 *   "enableTls": false
 * }
 *
 * 响应：
 * {
 *   "success": true,
 *   "result": 0,
 *   "data": {...},
 *   "message": "操作成功"
 * }
 */

import { enterDrc, exitDrc } from '@/lib/simple-drc-service.js';
import debugLogger from '@/lib/debug.js';

export async function POST({ request }) {
  try {
    const body = await request.json();
    const {
      action,
      sn,
      mqttHost = '192.168.31.73',
      mqttPort = 8083,
      username = '',
      password = '',
      osdFreq = 30,
      hsiFreq = 10,
      enableTls = false
    } = body;

    debugLogger.info('[DRC API]', `收到请求: ${action}`, { sn, mqttHost });

    // 验证必需参数
    if (!action || !sn) {
      return new Response(JSON.stringify({
        success: false,
        result: -1,
        error: '缺少必需参数: action 和 sn'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    switch (action) {
      case 'enter': {
        const mqttBroker = {
          ws_host: mqttHost,
          ws_port: parseInt(mqttPort),
          username,
          password,
          address: `${mqttHost}:${mqttPort === 8083 ? 1883 : mqttPort}`,
          client_id: `drc-${sn}`,
          enable_tls: enableTls,
          expire_time: Math.floor(Date.now() / 1000) + 3600,
        };

        debugLogger.debug('[DRC API]', '调用 enterDrc', { mqttBroker });
        const reply = await enterDrc(sn, mqttBroker, parseInt(osdFreq), parseInt(hsiFreq));

        const resultCode = reply?.data?.result;
        if (resultCode === 0) {
          debugLogger.info('[DRC API]', 'DRC模式进入成功', { sn });
          return new Response(JSON.stringify({
            success: true,
            result: resultCode,
            data: reply.data,
            message: 'DRC模式进入成功'
          }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          });
        } else {
          debugLogger.error('[DRC API]', 'DRC模式进入失败', { sn, resultCode });
          return new Response(JSON.stringify({
            success: false,
            result: resultCode,
            data: reply.data,
            error: `进入失败 (result: ${resultCode})`
          }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          });
        }
      }

      case 'exit': {
        const brokerConfig = {
          host: mqttHost,
          port: parseInt(mqttPort),
          username,
          password,
        };

        debugLogger.debug('[DRC API]', '调用 exitDrc', { brokerConfig });
        const reply = await exitDrc(sn, brokerConfig);

        const resultCode = reply?.data?.result;
        if (resultCode === 0) {
          debugLogger.info('[DRC API]', 'DRC模式退出成功', { sn });
          return new Response(JSON.stringify({
            success: true,
            result: resultCode,
            data: reply.data,
            message: 'DRC模式退出成功'
          }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          });
        } else {
          debugLogger.error('[DRC API]', 'DRC模式退出失败', { sn, resultCode });
          return new Response(JSON.stringify({
            success: false,
            result: resultCode,
            data: reply.data,
            error: `退出失败 (result: ${resultCode})`
          }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          });
        }
      }

      case 'heartbeat': {
        // 已废弃：心跳现在直接使用长连接发送，不再需要API endpoint
        // 保留此分支以兼容旧代码
        return new Response(JSON.stringify({
          success: false,
          result: -1,
          error: '心跳功能已迁移到长连接，请使用 mqttManager.getConnection(sn).publish() 直接发送'
        }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      default:
        return new Response(JSON.stringify({
          success: false,
          result: -1,
          error: `未知操作: ${action}`
        }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        });
    }

  } catch (error) {
    debugLogger.error('[DRC API]', '请求处理失败', error);
    return new Response(JSON.stringify({
      success: false,
      result: -1,
      error: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
