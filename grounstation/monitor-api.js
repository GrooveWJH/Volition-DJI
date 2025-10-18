#!/usr/bin/env node

/**
 * 实时监控 API 请求
 * 用于诊断浏览器请求是否到达服务器
 */

const http = require('http');

const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
};

function log(msg, color = colors.reset) {
  const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  console.log(`${color}[${timestamp}] ${msg}${colors.reset}`);
}

console.clear();
log('╔════════════════════════════════════════════════════════════════════════════╗', colors.bright + colors.cyan);
log('║                   EMQX API 请求实时监控器                                  ║', colors.bright + colors.cyan);
log('╚════════════════════════════════════════════════════════════════════════════╝', colors.bright + colors.cyan);
log('', colors.reset);
log('监听端口: http://localhost:4321/api/emqx-clients', colors.cyan);
log('按 Ctrl+C 停止监控', colors.dim);
log('━'.repeat(80), colors.cyan);

let requestCount = 0;

// 持续轮询测试
async function monitorAPI() {
  const testUrl = 'http://localhost:4321/api/emqx-clients?host=192.168.31.209&port=18083&apiKey=ce9de7b674acfed7&secretKey=XaG9CEa2AserrayKx13MjlWPTJ29AYPdfB7KeXORhiVqP';

  try {
    const startTime = Date.now();
    const response = await fetch(testUrl);
    const duration = Date.now() - startTime;
    const data = await response.json();

    requestCount++;

    const statusColor = response.ok ? colors.green : colors.red;
    const deviceCount = data.clientIds?.length || 0;
    const deviceColor = deviceCount > 0 ? colors.bright + colors.green : colors.yellow;

    log(`[请求 #${requestCount}] ${response.status} ${response.statusText} (${duration}ms)`, statusColor);
    log(`  └─ 设备数量: ${deviceCount}`, deviceColor);

    if (deviceCount > 0) {
      data.clientIds.forEach(id => {
        log(`     ├─ ${id}`, colors.bright);
      });
    } else {
      log(`     └─ ⚠️  返回空列表`, colors.yellow);
    }

  } catch (error) {
    log(`[请求 #${requestCount}] ❌ 失败: ${error.message}`, colors.red);
  }
}

// 每 3 秒监控一次
setInterval(monitorAPI, 3000);
monitorAPI(); // 立即执行一次

// 优雅退出
process.on('SIGINT', () => {
  log('\n━'.repeat(80), colors.cyan);
  log(`共监控 ${requestCount} 次请求`, colors.cyan);
  log('监控已停止', colors.yellow);
  process.exit(0);
});
