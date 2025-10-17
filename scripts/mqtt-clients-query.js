#!/usr/bin/env node

/**
 * EMQX客户端查询脚本 - 快速探测MQTT服务器上的DJI设备SN号
 * 用于查询EMQX Broker的连接客户端信息并过滤DJI设备
 *
 * 使用方法:
 * 1. 修改下方的配置参数 (apiKey, secretKey, apiUrl 等)
 * 2. 运行: node mqtt-clients-query.js
 * 3. 查看输出的DJI设备SN号列表
 */

// ==================== 配置参数 ====================
// 请在此处直接修改配置参数
const EMQX_CONFIG = {
  // EMQX API 认证信息 (必须填写)
  apiKey: '29275299af4a3366',
  secretKey: '0WrSJ49ADbOnNIa439CyYGWOUBKnhPhejSPFCqdRR9AcvE',

  // EMQX API 地址
  apiUrl: 'http://127.0.0.1:18083/api/v5/clients',

  // DJI设备ClientID匹配规则 (14位大写字母和数字)
  djiClientPattern: /^[A-Z0-9]{14}$/,

  // 输出模式: 'simple' | 'json' | 'full'
  // simple: 纯文本输出SN列表 (推荐用于快速查看)
  // json: JSON格式输出SN数组 (用于程序调用)
  // full: 完整的设备信息 (包含连接状态、流量统计等)
  outputMode: 'full',

  // 是否只显示DJI设备 (true: 只显示DJI设备, false: 显示所有客户端)
  onlyDjiDevices: true,

  // 是否显示详细日志 (true: 显示查询过程, false: 仅输出结果)
  verbose: true
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
async function fetchClients() {
  const auth = Buffer.from(`${EMQX_CONFIG.apiKey}:${EMQX_CONFIG.secretKey}`).toString('base64');

  try {
    if (EMQX_CONFIG.verbose) {
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

    // 如果启用了DJI设备过滤，只返回匹配的设备
    if (EMQX_CONFIG.onlyDjiDevices && data.data) {
      data.data = data.data.filter(client =>
        EMQX_CONFIG.djiClientPattern.test(client.clientid)
      );

      if (EMQX_CONFIG.verbose) {
        console.log(colorize(`📱 发现 ${data.data.length} 个DJI设备`, colors.green));
      }
    }

    return data;
  } catch (error) {
    if (EMQX_CONFIG.verbose) {
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

// ==================== DJI设备SN输出 ====================
function printDjiDevicesSimple(data) {
  const clients = data.data;

  if (clients.length === 0) {
    if (EMQX_CONFIG.verbose) {
      console.log(colorize('\n⚠️  未发现任何DJI设备', colors.yellow));
    }
    return;
  }

  console.log(colorize('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.green));
  console.log(colorize('  📱 DJI设备SN列表', colors.bright + colors.green));
  console.log(colorize('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.bright + colors.green));

  console.log('');
  clients.forEach((client) => {
    console.log(`  ${colorize(client.clientid, colors.bright)}`);
  });
  console.log(colorize('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.bright + colors.green));
}

function printDjiDevicesJSON(data) {
  const clients = data.data;
  const deviceSNs = clients.map(c => c.clientid);

  console.log(JSON.stringify(deviceSNs, null, 2));
}


// ==================== 主函数 ====================
async function main() {
  const mode = EMQX_CONFIG.outputMode;

  if (EMQX_CONFIG.verbose) {
    console.clear();
    console.log(colorize('╔════════════════════════════════════════════════════════════════════════════╗', colors.bright + colors.blue));
    console.log(colorize('║                   DJI设备MQTT客户端探测工具                                ║', colors.bright + colors.blue));
    console.log(colorize('╚════════════════════════════════════════════════════════════════════════════╝', colors.bright + colors.blue));
  }

  const data = await fetchClients();

  if (!data.data || data.data.length === 0) {
    if (mode === 'json') {
      console.log('[]');
    } else if (EMQX_CONFIG.verbose) {
      console.log(colorize('\n⚠️  未找到任何连接的设备', colors.yellow));
    }
    return;
  }

  if (EMQX_CONFIG.verbose) {
    const deviceType = EMQX_CONFIG.onlyDjiDevices ? 'DJI设备' : '客户端';
    console.log(colorize(`\n✅ 成功获取 ${data.data.length} 个${deviceType}`, colors.green));
  }

  // 根据配置的输出模式输出不同格式
  switch (mode) {
    case 'simple':
      printDjiDevicesSimple(data);
      break;

    case 'json':
      printDjiDevicesJSON(data);
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