/**
 * EMQX客户端查询API - 简化版
 * 直接调用EMQX API，无需执行shell脚本
 */

export async function GET({ request }) {
  const url = new URL(request.url);
  const host = url.searchParams.get('host');
  const port = url.searchParams.get('port') || '18083';
  const apiKey = url.searchParams.get('apiKey');
  const secretKey = url.searchParams.get('secretKey');

  if (!host || !apiKey || !secretKey) {
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

    const response = await fetch(apiUrl, {
      headers: {
        'Authorization': `Basic ${auth}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`EMQX API错误: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    const clients = data.data || [];

    // 过滤DJI设备客户端 (14位大写字母数字)
    const djiClientIds = clients
      .map(client => client.clientid)
      .filter(clientId => /^[A-Z0-9]{14}$/.test(clientId))
      .sort();

    return new Response(JSON.stringify({
      clientIds: djiClientIds,
      total: djiClientIds.length
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (error) {
    console.error('[EMQX API错误]', error.message);
    return new Response(JSON.stringify({
      error: error.message,
      clientIds: []
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
