#!/usr/bin/env node

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

// 配置参数 - 从环境变量或默认值获取
const MQTT_HOST = process.env.MQTT_HOST || '192.168.1.100';  // MQTT服务器地址
const USERNAME = process.env.USERNAME || 'admin';
const PASSWORD = process.env.PASSWORD || 'password';
const PORT = process.env.PORT || 5000;

console.log(`配置信息: MQTT Host=${MQTT_HOST}, Username=${USERNAME}, Port=${PORT}`);

// 创建HTTP服务器
const server = http.createServer((req, res) => {
  const parsedUrl = new URL(req.url, `http://${req.headers.host}`);
  
  if (parsedUrl.pathname === '/login') {
    try {
      // 读取HTML模板文件
      const templatePath = path.join(__dirname, 'templates', 'login.html');
      let htmlContent = fs.readFileSync(templatePath, 'utf8');
      
      // 替换占位符
      htmlContent = htmlContent.replace(/hostnamehere/g, MQTT_HOST);
      htmlContent = htmlContent.replace(/userloginhere/g, USERNAME);
      htmlContent = htmlContent.replace(/userpasswordhere/g, PASSWORD);
      
      // 设置响应头
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
      });
      
      res.end(htmlContent);
      console.log(`[${new Date().toISOString()}] 页面访问: ${req.url} from ${req.socket.remoteAddress}`);
      
    } catch (error) {
      console.error('读取HTML模板失败:', error);
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('服务器内部错误');
    }
    
  } else if (parsedUrl.pathname === '/status') {
    // 状态检查端点
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({
      status: 'running',
      mqttHost: MQTT_HOST,
      port: PORT,
      timestamp: new Date().toISOString()
    }));
    
  } else {
    // 404 处理
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('页面未找到');
  }
});

// 获取本机IP地址
function getLocalIP() {
  const interfaces = require('os').networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const netInterface of interfaces[name]) {
      if (netInterface.family === 'IPv4' && !netInterface.internal) {
        return netInterface.address;
      }
    }
  }
  return '127.0.0.1';
}

const LOCAL_IP = getLocalIP();

// 启动服务器
server.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 登录页面服务器已启动`);
  console.log(`📍 本机访问: http://localhost:${PORT}/login`);
  console.log(`📍 局域网访问: http://${LOCAL_IP}:${PORT}/login`);
  console.log(`📊 状态检查: http://${LOCAL_IP}:${PORT}/status`);
  console.log(`📡 MQTT服务器: ${MQTT_HOST}`);
  console.log(`⏰ 启动时间: ${new Date().toISOString()}`);
});

// 优雅关闭处理
process.on('SIGINT', () => {
  console.log('\n📴 正在关闭服务器...');
  server.close(() => {
    console.log('✅ 服务器已关闭');
    process.exit(0);
  });
});

// 导出服务器实例（用于编程式控制）
module.exports = { server, MQTT_HOST, LOCAL_IP, PORT };