/**
 * EMQX客户端查询API
 * 通过URL路径传递参数并调用脚本
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

export async function GET({ request }) {
  const url = request.url;
  const urlObj = new URL(url);
  const queryString = urlObj.search.substring(1);

  if (!queryString) {
    return new Response(JSON.stringify({
      error: '缺少配置参数',
      clientIds: []
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // 手动解析参数
  const params_obj = {};
  queryString.split('&').forEach(pair => {
    const [key, value] = pair.split('=');
    params_obj[decodeURIComponent(key)] = decodeURIComponent(value);
  });

  const host = params_obj.host;
  const port = params_obj.port;
  const apiKey = params_obj.apiKey;
  const secretKey = params_obj.secretKey;

  if (!host || !port || !apiKey || !secretKey) {
    return new Response(JSON.stringify({
      error: '缺少必需配置参数',
      clientIds: []
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const scriptPath = path.resolve(__dirname, '../../scripts/emqx-client-query.js');
    const apiUrl = `http://${host}:${port}/api/v5/clients`;

    const env = {
      ...process.env,
      EMQX_API_KEY: apiKey,
      EMQX_SECRET_KEY: secretKey,
      EMQX_API_URL: apiUrl
    };

    const { stdout, stderr } = await execAsync(`node "${scriptPath}" ids`, { env });

    if (stderr) {
      console.error('[API错误]', stderr);
    }

    const clientIds = JSON.parse(stdout.trim());

    return new Response(JSON.stringify({ clientIds }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (err) {
    console.error('[API错误]', err.message);
    return new Response(JSON.stringify({
      error: err.message,
      clientIds: []
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
