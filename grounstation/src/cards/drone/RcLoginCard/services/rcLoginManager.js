// @ts-nocheck
import { getLocalIP, buildLocalAccessUrl } from './networkUtils.js';
import { startServer, stopServer, checkServerStatus } from './loginPageServer.js';

let localIP = '';

function addLog(message) {
  const container = document.getElementById('logs-container');
  if (!container) return;

  const timestamp = new Date().toLocaleTimeString();
  const logEntry = document.createElement('div');
  logEntry.innerHTML = `<span class="text-gray-400">[${timestamp}]</span> ${message}`;
  container.appendChild(logEntry);
  container.scrollTop = container.scrollHeight;
}

function clearLogs() {
  const container = document.getElementById('logs-container');
  if (container) {
    container.innerHTML = '<div class="text-gray-500">日志已清空</div>';
  }
}

function updateServerStatusUI(isRunning, url) {
  const statusDiv = document.getElementById('server-status');
  const accessInfo = document.getElementById('page-access-info');
  const publishBtn = document.getElementById('publish-page-btn');
  const stopBtn = document.getElementById('stop-server-btn');
  const statusText = document.getElementById('server-status-text');
  const urlElement = document.getElementById('lan-access-url');

  if (!statusDiv || !accessInfo || !publishBtn || !stopBtn || !statusText) {
    return;
  }

  if (isRunning) {
    statusDiv.className = 'bg-green-50 border border-green-200 rounded-lg p-4';
    const icon = statusDiv.querySelector('.material-symbols-outlined');
    const text = statusDiv.querySelector('span:last-child');
    if (icon && text) {
      icon.textContent = 'check_circle';
      icon.className = 'material-symbols-outlined text-green-600 text-lg';
      text.textContent = '服务运行中';
      text.className = 'font-medium text-sm text-green-800';
    }
    statusText.textContent = '运行中';
    accessInfo.classList.remove('hidden');
    publishBtn.classList.add('hidden');
    stopBtn.classList.remove('hidden');
    if (urlElement) {
      urlElement.textContent = url;
    }
  } else {
    statusDiv.className = 'bg-red-50 border border-red-200 rounded-lg p-4';
    const icon = statusDiv.querySelector('.material-symbols-outlined');
    const text = statusDiv.querySelector('span:last-child');
    if (icon && text) {
      icon.textContent = 'error';
      icon.className = 'material-symbols-outlined text-red-600 text-lg';
      text.textContent = '服务未运行';
      text.className = 'font-medium text-sm text-red-800';
    }
    statusText.textContent = '已停止';
    accessInfo.classList.add('hidden');
    publishBtn.classList.remove('hidden');
    stopBtn.classList.add('hidden');
  }
}

function readInputValue(id, defaultValue) {
  const element = document.getElementById(id);
  if (element && element instanceof HTMLInputElement) {
    return element.value || defaultValue;
  }
  return defaultValue;
}

function hydrateInputFromStorage(input) {
  const storageKey = input.getAttribute('data-storage-key');
  if (!storageKey) return;

  const savedValue = localStorage.getItem(storageKey);
  if (savedValue && input instanceof HTMLInputElement) {
    input.value = savedValue;
  }

  input.addEventListener('input', () => {
    if (input instanceof HTMLInputElement) {
      localStorage.setItem(storageKey, input.value);
    }
  });
}

async function handleStartServer() {
  addLog('正在启动登录页面服务器...');

  const port = readInputValue('page-port', '8080');
  const mqttHost = readInputValue('mqtt-host', '192.168.1.100');
  const mqttPort = readInputValue('mqtt-port', '1883');
  const username = readInputValue('mqtt-username', 'admin');

  const result = await startServer({
    port: parseInt(port, 10),
    mqttHost,
    mqttPort: parseInt(mqttPort, 10),
    username,
    password: 'admin',
  });

  if (result.success) {
    const url = buildLocalAccessUrl(localIP, port);
    addLog(`✓ 服务器已启动在端口 ${port}`);
    addLog(`✓ 登录页面地址: ${url}`);
    updateServerStatusUI(true, url);
  } else {
    addLog(`✗ 启动失败: ${result.message}`);
  }
}

async function handleStopServer() {
  addLog('正在停止服务器...');
  const result = await stopServer();

  if (result.success) {
    addLog('✓ 服务器已停止');
    updateServerStatusUI(false);
  } else {
    addLog(`✗ 停止失败: ${result.message}`);
  }
}

async function handleCheckStatus() {
  const port = readInputValue('page-port', '8080');
  const url = buildLocalAccessUrl(localIP, port);
  const result = await checkServerStatus();

  updateServerStatusUI(Boolean(result.running), url);
  if (result.success) {
    addLog(`状态检查: ${result.running ? '运行中' : '已停止'}`);
  } else {
    addLog(`状态检查失败: ${result.message || '未知错误'}`);
  }
}

function handleCopyUrl() {
  const urlElement = document.getElementById('lan-access-url');
  if (urlElement && urlElement.textContent) {
    navigator.clipboard.writeText(urlElement.textContent);
    addLog('✓ URL已复制到剪贴板');
  }
}

async function initializeRcLogin() {
  localIP = String(await getLocalIP());
  const localIpElement = document.getElementById('local-ip');
  if (localIpElement) {
    localIpElement.textContent = localIP;
  }

  const inputs = document.querySelectorAll('input[data-storage-key]');
  inputs.forEach((input) => hydrateInputFromStorage(input));

  const publishBtn = document.getElementById('publish-page-btn');
  const stopBtn = document.getElementById('stop-server-btn');
  const checkBtn = document.getElementById('check-status-btn');
  const clearBtn = document.getElementById('clear-logs-btn');
  const copyBtn = document.getElementById('copy-url-btn');

  if (publishBtn) publishBtn.addEventListener('click', handleStartServer);
  if (stopBtn) stopBtn.addEventListener('click', handleStopServer);
  if (checkBtn) checkBtn.addEventListener('click', handleCheckStatus);
  if (clearBtn) clearBtn.addEventListener('click', clearLogs);
  if (copyBtn) copyBtn.addEventListener('click', handleCopyUrl);

  await handleCheckStatus();
}

document.addEventListener('DOMContentLoaded', () => {
  initializeRcLogin();
});
