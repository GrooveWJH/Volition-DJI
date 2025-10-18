/**
 * EMQX客户端查询API - 简化版
 * 直接调用EMQX API，无需执行shell脚本
 */

import debugLogger from '@/lib/debug.js';

export async function GET({ request }) {
  const url = new URL(request.url);
  const host = url.searchParams.get('host');
  const port = url.searchParams.get('port') || '18083';
  const apiKey = url.searchParams.get('apiKey');
  const secretKey = url.searchParams.get('secretKey');

  debugLogger.debug('[EMQX API]', '收到设备扫描请求', {
    host,
    port,
    apiKey: apiKey ? `${apiKey.substring(0, 8)}...` : '未设置',
    secretKey: secretKey ? '***已设置***' : '未设置'
  });

  if (!host || !apiKey || !secretKey) {
    debugLogger.error('[EMQX API]', '参数不完整，缺少必需配置');
    return new Response(JSON.stringify({
      error: '缺少必需配置参数: host, apiKey, secretKey',
      clientIds: []
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const apiUrl = `http://${host}:${port}/api/v5/clients`;
    const auth = Buffer.from(`${apiKey}:${secretKey}`).toString('base64');

    debugLogger.debug('[EMQX API]', `请求 EMQX API: ${apiUrl}`);

    const response = await fetch(apiUrl, {
      headers: {
        'Authorization': `Basic ${auth}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      debugLogger.error('[EMQX API]', `HTTP错误 ${response.status}`, errorText);
      throw new Error(`EMQX API错误: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    const clients = data.data || [];

    debugLogger.debug('[EMQX API]', `获取到 ${clients.length} 个客户端`);

    // 过滤DJI设备客户端 (14位大写字母数字)
    const djiClientIds = clients
      .map(client => client.clientid)
      .filter(clientId => /^[A-Z0-9]{14}$/.test(clientId))
      .sort();

    debugLogger.info('[EMQX API]', `扫描完成，发现 ${djiClientIds.length} 个DJI设备`, djiClientIds);

    return new Response(JSON.stringify({
      clientIds: djiClientIds,
      total: djiClientIds.length
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (error) {
    debugLogger.error('[EMQX API]', '扫描失败', error.message);
    return new Response(JSON.stringify({
      error: error.message,
      clientIds: []
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
