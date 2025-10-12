/**
 * HTML动态生成工具
 * 用于创建和管理动态HTML内容
 */

/**
 * 创建DJI登录页面HTML模板
 * @param {Object} config - 配置对象
 * @param {string} config.mqttUrl - MQTT连接URL
 * @param {string} config.mqttUsername - MQTT用户名
 * @param {string} config.mqttPassword - MQTT密码
 * @param {string} config.currentTime - 当前时间字符串
 * @returns {string} 完整的HTML页面字符串
 */
export function generateDjiLoginPage(config) {
  const { mqttUrl, mqttUsername, mqttPassword, currentTime } = config;
  
  return `<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>DJI 遥控器登录页面</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      ${getDjiLoginPageStyles()}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>🚁 DJI 云 API 登录页面</h1>
      
      <div class="status">
        通过地面站控制台自动生成 - ${currentTime}
      </div>

      <div class="button-row">
        <button id="login-button">🔐 登录验证</button>
        <button id="logout-button">🚪 注销登出</button>
        <button id="raport-button">📊 状态报告</button>
      </div>
      
      <div id="connection-info"></div>
      <ul id="logs"></ul>
    </div>
    
    <script>
      ${getDjiLoginPageScript(mqttUrl, mqttUsername, mqttPassword)}
    </script>
  </body>
</html>`;
}

/**
 * 获取DJI登录页面的CSS样式
 * @returns {string} CSS样式字符串
 */
function getDjiLoginPageStyles() {
  return `
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      margin: 20px;
      background: #f5f5f5;
    }
    .container {
      max-width: 800px;
      margin: 0 auto;
      background: white;
      padding: 30px;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .button-row {
      display: flex;
      justify-content: space-between;
      margin: 20px 0;
    }
    button {
      flex: 1;
      margin: 0 5px;
      padding: 12px 20px;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    button:hover {
      transform: translateY(-1px);
    }
    #login-button {
      background: #10b981;
      color: white;
    }
    #login-button:hover {
      background: #059669;
    }
    #logout-button {
      background: #ef4444;
      color: white;
    }
    #logout-button:hover {
      background: #dc2626;
    }
    #raport-button {
      background: #3b82f6;
      color: white;
    }
    #raport-button:hover {
      background: #2563eb;
    }
    #connection-info {
      margin: 20px 0;
      padding: 15px;
      border: 1px solid #f59e0b;
      background: #fffbeb;
      border-radius: 6px;
      font-family: monospace;
      font-size: 12px;
    }
    #logs {
      background: #1f2937;
      color: #10b981;
      padding: 20px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 12px;
      max-height: 300px;
      overflow-y: auto;
      list-style: none;
      margin: 0;
    }
    #logs li {
      margin: 5px 0;
      word-break: break-all;
    }
    h1 {
      color: #1f2937;
      text-align: center;
      margin-bottom: 30px;
    }
    .status {
      text-align: center;
      padding: 10px;
      background: #dbeafe;
      border-radius: 6px;
      margin-bottom: 20px;
      font-size: 14px;
      color: #1e40af;
    }
  `;
}

/**
 * 获取DJI登录页面的JavaScript代码
 * @param {string} mqttUrl - MQTT连接URL
 * @param {string} mqttUsername - MQTT用户名
 * @param {string} mqttPassword - MQTT密码
 * @returns {string} JavaScript代码字符串
 */
function getDjiLoginPageScript(mqttUrl, mqttUsername, mqttPassword) {
  return `
    // DJI配置参数
    const APP_ID = 171440;
    const LICENSE = "krC5HsEFLzVC8xkKM38JCcSxNEQvsQ/7IoiHEJRaulGiPQildia+n/+bF+SO21pk1JTS8CfaNS+fn8qt+17i3Y7uoqtBOOsdtLUQhqPMb0DVea0dmZ7oZhdP2CuQrQSn1bobS3pQ+MW2eEOq0XCcCkpo+HxAC1r5/33yEDxc6NE=";
    const APP_KEY = "b57ab1ee70f0a78e1797c592742e7d4";
    
    // MQTT配置参数
    const MQTT_HOST = "${mqttUrl}";
    const MQTT_USERNAME = "${mqttUsername}";
    const MQTT_PASSWORD = "${mqttPassword}";
    
    var fieldList = document.getElementById("logs");
    var connectionInfo = document.getElementById("connection-info");
    connectionInfo.innerHTML = 
      "<strong>当前 MQTT 配置</strong><br>" +
      "Host: " + MQTT_HOST + "<br>" +
      "Username: " + MQTT_USERNAME + "<br>" +
      "Password: " + MQTT_PASSWORD;
      
    var log = function (msg) {
      var li = document.createElement("li");
      li.innerHTML = "<span style='color:#6b7280'>[" + new Date().toLocaleTimeString() + "]</span> " + msg;
      fieldList.appendChild(li);
      fieldList.scrollTop = fieldList.scrollHeight;
    };
    
    var reg_calback = function () {
      log("🎉 回调触发，参数：" + Array.from(arguments).join(', '));
    };
    
    function checkDjiBridge() {
      if (typeof window.djiBridge === 'undefined') {
        log("❌ 错误: 未检测到 DJI Bridge，请确保在DJI遥控器浏览器中打开此页面");
        return false;
      }
      return true;
    }
    
    var loginButton = document.getElementById("login-button");
    loginButton.addEventListener("click", function () {
      log("🚀 开始验证平台许可证...");
      
      if (!checkDjiBridge()) return;
      
      try {
        var token = window.djiBridge.platformVerifyLicense(APP_ID, APP_KEY, LICENSE);
        log("✅ 平台验证状态：" + window.djiBridge.platformIsVerified());

        var register_params = JSON.stringify({
          host: MQTT_HOST,
          connectCallback: "reg_calback",
          username: MQTT_USERNAME,
          password: MQTT_PASSWORD,
        });
        
        log("📦 加载组件 thing：" + window.djiBridge.platformLoadComponent("thing", register_params));
        log("ℹ️ 当前状态：" + window.djiBridge.thingGetConnectState());
        
        log("🔗 开始连接：" + window.djiBridge.thingConnect(MQTT_USERNAME, MQTT_PASSWORD, "reg_calback"));
        log("📡 Thing 连接状态：" + window.djiBridge.thingGetConnectState());
        
      } catch (error) {
        log("❌ 登录过程出错：" + error.message);
      }
    });

    var logoutButton = document.getElementById("logout-button");
    logoutButton.addEventListener("click", function () {
      log("🚪 开始注销...");
      
      if (!checkDjiBridge()) return;
      
      try {
        log("🗂️ 卸载组件：" + window.djiBridge.platformUnloadComponent("thing"));
        log("✅ 注销完成");
      } catch (error) {
        log("❌ 注销过程出错：" + error.message);
      }
    });

    document.getElementById("raport-button").addEventListener("click", function () {
      log("📊 查询系统状态...");
      
      if (!checkDjiBridge()) return;
      
      try {
        log("📊 组件加载状态：" + window.djiBridge.platformIsComponentLoaded("thing"));
        log("📡 Thing 状态：" + window.djiBridge.thingGetConnectState());
        log("🔐 平台验证状态：" + window.djiBridge.platformIsVerified());
      } catch (error) {
        log("❌ 状态查询出错：" + error.message);
      }
    });

    log("🎯 页面初始化完成");
    log("⚡ 平台验证状态：" + (checkDjiBridge() ? window.djiBridge.platformIsVerified() : "DJI Bridge 未加载"));
    log("💡 提示：请确保在DJI遥控器的内置浏览器中使用此页面");
  `;
}

/**
 * 创建Blob URL用于预览HTML页面
 * @param {string} htmlContent - HTML内容
 * @returns {string} Blob URL
 */
export function createBlobUrl(htmlContent) {
  const blob = new Blob([htmlContent], { type: 'text/html' });
  return URL.createObjectURL(blob);
}

/**
 * 清理Blob URL
 * @param {string} blobUrl - 要清理的Blob URL
 */
export function revokeBlobUrl(blobUrl) {
  if (blobUrl && blobUrl.startsWith('blob:')) {
    URL.revokeObjectURL(blobUrl);
  }
}