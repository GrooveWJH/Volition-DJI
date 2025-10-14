#!/usr/bin/env node

/**
 * EMQX客户端查询脚本
 * 用于查询EMQX Broker的连接客户端信息并格式化输出
 */

// ==================== 配置 ====================
// 从环境变量或命令行参数读取配置
const EMQX_CONFIG = {
  apiKey: process.env.EMQX_API_KEY || '',
  secretKey: process.env.EMQX_SECRET_KEY || '',
  apiUrl: process.env.EMQX_API_URL || 'http://127.0.0.1:18083/api/v5/clients',
};

// ==================== 颜色工具 ====================
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',

  // 前景色
  black: '\x1b[30m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',

  // 背景色
  bgBlack: '\x1b[40m',
  bgRed: '\x1b[41m',
  bgGreen: '\x1b[42m',
  bgYellow: '\x1b[43m',
  bgBlue: '\x1b[44m',
  bgMagenta: '\x1b[45m',
  bgCyan: '\x1b[46m',
  bgWhite: '\x1b[47m',
};

// 颜色化文本
function colorize(text, color) {
  return `${color}${text}${colors.reset}`;
}

// ==================== HTTP 请求 ====================
async function fetchClients(silent = false) {
  const auth = Buffer.from(`${EMQX_CONFIG.apiKey}:${EMQX_CONFIG.secretKey}`).toString('base64');

  try {
    if (!silent) {
      console.log(colorize('\n🔍 正在查询 EMQX 客户端列表...', colors.cyan));
      console.log(colorize(`📡 API: ${EMQX_CONFIG.apiUrl}`, colors.dim));
      console.log(colorize('━'.repeat(80), colors.dim));
    }

    const response = await fetch(EMQX_CONFIG.apiUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Basic ${auth}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    if (!silent) {
      console.error(colorize(`\n❌ 请求失败: ${error.message}`, colors.red));
    }
    process.exit(1);
  }
}

// ==================== 格式化输出 ====================
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatUptime(connectedAt) {
  const now = new Date();
  const connected = new Date(connectedAt);
  const diff = Math.floor((now - connected) / 1000); // 秒

  const hours = Math.floor(diff / 3600);
  const minutes = Math.floor((diff % 3600) / 60);
  const seconds = diff % 60;

  return `${hours}时${minutes}分${seconds}秒`;
}

function printClientInfo(client, index) {
  const statusColor = client.connected ? colors.green : colors.red;
  const statusText = client.connected ? '✓ 在线' : '✗ 离线';

  console.log(colorize(`\n┌─ 客户端 #${index + 1}`, colors.bright + colors.cyan));
  console.log(colorize('├─────────────────────────────────────────────────────────────────────────────', colors.dim));

  // 基本信息
  console.log(`${colorize('│ 客户端ID:', colors.yellow)} ${colorize(client.clientid, colors.bright)}`);
  console.log(`${colorize('│ 状态:', colors.yellow)} ${colorize(statusText, statusColor)}`);
  console.log(`${colorize('│ IP地址:', colors.yellow)} ${client.ip_address}:${client.port}`);
  console.log(`${colorize('│ 节点:', colors.yellow)} ${client.node}`);
  console.log(`${colorize('│ 协议:', colors.yellow)} ${client.proto_name} v${client.proto_ver}`);

  // 连接信息
  console.log(colorize('├─────────────────────────────────────────────────────────────────────────────', colors.dim));
  console.log(`${colorize('│ 连接时间:', colors.yellow)} ${formatDate(client.connected_at)}`);
  console.log(`${colorize('│ 在线时长:', colors.yellow)} ${formatUptime(client.connected_at)}`);
  console.log(`${colorize('│ 保活时间:', colors.yellow)} ${client.keepalive}秒`);
  console.log(`${colorize('│ Clean Start:', colors.yellow)} ${client.clean_start ? '是' : '否'}`);
  console.log(`${colorize('│ 持久化:', colors.yellow)} ${client.is_persistent ? '是' : '否'}`);

  // 订阅信息
  console.log(colorize('├─────────────────────────────────────────────────────────────────────────────', colors.dim));
  console.log(`${colorize('│ 订阅数量:', colors.yellow)} ${colorize(client.subscriptions_cnt, colors.green)}`);
  console.log(`${colorize('│ 最大订阅:', colors.yellow)} ${client.subscriptions_max}`);

  // 消息统计
  console.log(colorize('├─────────────────────────────────────────────────────────────────────────────', colors.dim));
  console.log(colorize('│ 📨 接收统计:', colors.magenta));
  console.log(`${colorize('│   ├─ 报文数:', colors.yellow)} ${colorize(client.recv_pkt, colors.cyan)}`);
  console.log(`${colorize('│   ├─ 消息数:', colors.yellow)} ${colorize(client.recv_msg, colors.cyan)} (QoS0: ${client.recv_msg.qos0}, QoS1: ${client.recv_msg.qos1}, QoS2: ${client.recv_msg.qos2})`);
  console.log(`${colorize('│   ├─ 字节数:', colors.yellow)} ${colorize(formatBytes(client.recv_oct), colors.cyan)}`);
  console.log(`${colorize('│   └─ 丢弃数:', colors.yellow)} ${client.recv_msg.dropped}`);

  console.log(colorize('│ 📤 发送统计:', colors.magenta));
  console.log(`${colorize('│   ├─ 报文数:', colors.yellow)} ${colorize(client.send_pkt, colors.cyan)}`);
  console.log(`${colorize('│   ├─ 消息数:', colors.yellow)} ${colorize(client.send_msg, colors.cyan)} (QoS0: ${client.send_msg.qos0}, QoS1: ${client.send_msg.qos1}, QoS2: ${client.send_msg.qos2})`);
  console.log(`${colorize('│   ├─ 字节数:', colors.yellow)} ${colorize(formatBytes(client.send_oct), colors.cyan)}`);
  console.log(`${colorize('│   └─ 丢弃数:', colors.yellow)} ${client.send_msg.dropped}`);

  // 队列信息
  console.log(colorize('├─────────────────────────────────────────────────────────────────────────────', colors.dim));
  console.log(`${colorize('│ 消息队列长度:', colors.yellow)} ${client.mqueue_len}/${client.mqueue_max}`);
  console.log(`${colorize('│ 队列丢弃数:', colors.yellow)} ${client.mqueue_dropped}`);
  console.log(`${colorize('│ 飞行窗口:', colors.yellow)} ${client.inflight_cnt}/${client.inflight_max}`);
  console.log(`${colorize('│ 等待释放:', colors.yellow)} ${client.awaiting_rel_cnt}/${client.awaiting_rel_max}`);

  // 其他信息
  console.log(colorize('├─────────────────────────────────────────────────────────────────────────────', colors.dim));
  console.log(`${colorize('│ 监听器:', colors.yellow)} ${client.listener}`);
  console.log(`${colorize('│ Zone:', colors.yellow)} ${client.zone}`);
  console.log(`${colorize('│ 用户名:', colors.yellow)} ${client.username || '(无)'}`);
  console.log(`${colorize('│ Heap Size:', colors.yellow)} ${formatBytes(client.heap_size)}`);
  console.log(`${colorize('│ Reductions:', colors.yellow)} ${client.reductions.toLocaleString()}`);

  console.log(colorize('└─────────────────────────────────────────────────────────────────────────────', colors.dim));
}

function printSummary(data) {
  const meta = data.meta;
  const clients = data.data;

  console.log(colorize('\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.cyan));
  console.log(colorize('  📊 查询摘要', colors.bright + colors.cyan));
  console.log(colorize('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.cyan));

  console.log(`\n  ${colorize('总客户端数:', colors.yellow)} ${colorize(meta.count, colors.bright + colors.green)}`);
  console.log(`  ${colorize('当前页码:', colors.yellow)} ${meta.page}`);
  console.log(`  ${colorize('每页限制:', colors.yellow)} ${meta.limit}`);
  console.log(`  ${colorize('是否有下一页:', colors.yellow)} ${meta.hasnext ? '是' : '否'}`);

  if (clients.length > 0) {
    const totalRecvBytes = clients.reduce((sum, c) => sum + c.recv_oct, 0);
    const totalSendBytes = clients.reduce((sum, c) => sum + c.send_oct, 0);
    const totalSubscriptions = clients.reduce((sum, c) => sum + c.subscriptions_cnt, 0);

    console.log(`\n  ${colorize('总接收字节:', colors.yellow)} ${colorize(formatBytes(totalRecvBytes), colors.cyan)}`);
    console.log(`  ${colorize('总发送字节:', colors.yellow)} ${colorize(formatBytes(totalSendBytes), colors.cyan)}`);
    console.log(`  ${colorize('总订阅数:', colors.yellow)} ${colorize(totalSubscriptions, colors.cyan)}`);
  }

  console.log(colorize('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.bright + colors.cyan));
}

// ==================== ClientID 列表输出 ====================
function printClientIDs(data) {
  const clients = data.data;
  const clientIds = clients.map(c => c.clientid);

  // 只输出纯 JSON，方便其他程序调用
  console.log(JSON.stringify(clientIds));
}

function printClientIDsSimple(data) {
  const clients = data.data;

  console.log(colorize('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.green));
  console.log(colorize('  📝 Client IDs (纯文本)', colors.bright + colors.green));
  console.log(colorize('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.green));

  if (clients.length === 0) {
    console.log(colorize('\n  (无连接客户端)', colors.dim));
    return;
  }

  console.log('');
  clients.forEach((client) => {
    console.log(`  ${client.clientid}`);
  });
  console.log(colorize('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.bright + colors.green));
}

function printClientIDsJSON(data) {
  const clients = data.data;
  const clientIds = clients.map(c => c.clientid);

  console.log(colorize('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.magenta));
  console.log(colorize('  🔧 Client IDs (JSON)', colors.bright + colors.magenta));
  console.log(colorize('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.magenta));

  console.log('\n' + JSON.stringify(clientIds, null, 2));
  console.log(colorize('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.bright + colors.magenta));
}

// ==================== 命令行参数解析 ====================
function parseArgs() {
  const args = process.argv.slice(2);
  const mode = args[0] || 'full';

  const validModes = ['full', 'ids', 'simple', 'json'];

  if (!validModes.includes(mode)) {
    console.log(colorize('\n❌ 无效的模式参数', colors.red));
    console.log(colorize('\n使用方法:', colors.yellow));
    console.log(colorize('  node emqx-client-query.js [mode]', colors.cyan));
    console.log(colorize('\n可用模式:', colors.yellow));
    console.log(colorize('  full   ', colors.cyan) + ' - 显示完整的客户端信息（默认）');
    console.log(colorize('  ids    ', colors.cyan) + ' - 输出纯 JSON 格式的客户端ID数组（用于程序调用）');
    console.log(colorize('  simple ', colors.cyan) + ' - 只显示客户端ID（纯文本，每行一个）');
    console.log(colorize('  json   ', colors.cyan) + ' - 以JSON格式输出客户端ID数组（带格式化）');
    console.log('');
    process.exit(1);
  }

  return mode;
}

// ==================== 主函数 ====================
async function main() {
  const mode = parseArgs();

  // ids 模式静默运行，不输出额外信息
  if (mode !== 'ids') {
    console.clear();
    console.log(colorize('╔════════════════════════════════════════════════════════════════════════════╗', colors.bright + colors.blue));
    console.log(colorize('║                        EMQX 客户端查询工具                                 ║', colors.bright + colors.blue));
    console.log(colorize('╚════════════════════════════════════════════════════════════════════════════╝', colors.bright + colors.blue));
  }

  const data = await fetchClients(mode === 'ids');

  if (!data.data || data.data.length === 0) {
    if (mode === 'ids') {
      // ids 模式返回空数组
      console.log('[]');
    } else {
      console.log(colorize('\n⚠️  未找到任何连接的客户端', colors.yellow));
    }
    return;
  }

  if (mode !== 'ids') {
    console.log(colorize(`\n✅ 成功获取 ${data.meta.count} 个客户端信息`, colors.green));
  }

  // 根据模式输出不同格式
  switch (mode) {
    case 'ids':
      printClientIDs(data);
      break;

    case 'simple':
      printClientIDsSimple(data);
      break;

    case 'json':
      printClientIDsJSON(data);
      break;

    case 'full':
    default:
      data.data.forEach((client, index) => {
        printClientInfo(client, index);
      });
      printSummary(data);
      break;
  }
}

// ==================== 执行 ====================
main().catch(error => {
  console.error(colorize(`\n💥 发生错误: ${error.message}`, colors.red));
  console.error(colorize(error.stack, colors.dim));
  process.exit(1);
});
