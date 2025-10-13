// @ts-nocheck

const API_BASE = '/api/mqtt-login';

export async function startServer(config) {
  try {
    const response = await fetch(`${API_BASE}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      throw new Error('启动失败');
    }

    return {
      success: true,
      message: '服务器启动成功',
    };
  } catch (error) {
    return {
      success: false,
      message: error instanceof Error ? error.message : '服务器启动失败',
    };
  }
}

export async function stopServer() {
  try {
    const response = await fetch(`${API_BASE}/stop`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error('停止失败');
    }

    return {
      success: true,
      message: '服务器停止成功',
    };
  } catch (error) {
    return {
      success: false,
      message: error instanceof Error ? error.message : '服务器停止失败',
    };
  }
}

export async function checkServerStatus() {
  try {
    const response = await fetch(`${API_BASE}/status`);
    if (!response.ok) {
      throw new Error('状态检查失败');
    }
    const result = await response.json();
    return {
      success: true,
      running: Boolean(result.running),
    };
  } catch (error) {
    return {
      success: false,
      running: false,
      message: error instanceof Error ? error.message : '状态检查失败',
    };
  }
}
