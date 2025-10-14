/**
 * 设备扫描器
 */

function getConfig() {
  return {
    host: localStorage.getItem('emqx_host') || '',
    port: localStorage.getItem('emqx_port') || '',
    apiKey: localStorage.getItem('emqx_key') || '',
    secretKey: localStorage.getItem('emqx_secret') || ''
  };
}

export async function scanDevices() {
  const config = getConfig();

  if (!config.host || !config.port || !config.apiKey || !config.secretKey) {
    return [];
  }

  try {
    const params = new URLSearchParams(config);
    const res = await fetch(`/api/emqx-clients?${params.toString()}`, {
      method: 'GET'
    });

    if (!res.ok) {
      return [];
    }

    const data = await res.json();
    return data.clientIds || [];

  } catch (err) {
    console.error('[扫描错误]', err.message);
    return [];
  }
}

export function saveConfig(config) {
  localStorage.setItem('emqx_host', config.host);
  localStorage.setItem('emqx_port', config.port);
  localStorage.setItem('emqx_key', config.apiKey);
  localStorage.setItem('emqx_secret', config.secretKey);
}
