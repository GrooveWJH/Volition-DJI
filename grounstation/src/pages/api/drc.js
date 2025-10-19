/**
 * DRC模式控制API - DEPRECATED
 *
 * ⚠️ 已废弃：现在DRC直接使用长连接 station-{sn} 发送服务请求
 * 此endpoint保留仅用于向后兼容和CLI测试
 *
 * 新架构：
 * - station-{sn}: 长连接，发送所有服务请求
 * - heart-{sn}: 心跳专用
 * - drc-{sn}: 设备回传数据专用
 */

import debugLogger from '@/lib/debug.js';

export async function POST({ request }) {
  debugLogger.warn('[DRC API]', '⚠️ 已废弃的API被调用');

  return new Response(JSON.stringify({
    success: false,
    error: '此API已废弃。请使用长连接 mqttManager.getConnection(sn) 直接发送DRC指令',
    message: '架构已升级：所有服务请求现在通过 station-{sn} 长连接发送'
  }), {
    status: 410, // Gone
    headers: { 'Content-Type': 'application/json' }
  });
}
