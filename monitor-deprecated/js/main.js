import { buildTopics } from "./topics.js";
import { initTopicTable, populateTopicTable, applyTopicMessage } from "./topicTable.js";
import { ensureClientId, parseMessagePayload } from "./utils.js";
import { connectClient, disconnectClient, hasActiveClient } from "./mqttController.js";

const rcTopicsBody = document.getElementById("rc-topics");
const droneTopicsBody = document.getElementById("drone-topics");
const statusEl = document.getElementById("status");
const connectBtn = document.getElementById("connect");
const disconnectBtn = document.getElementById("disconnect");

const hostInput = document.getElementById("host");
const portInput = document.getElementById("port");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const deviceSnInput = document.getElementById("device-sn");
const gatewaySnInput = document.getElementById("gateway-sn");
const useTlsSelect = document.getElementById("use-tls");
const clientIdInput = document.getElementById("client-id");

initTopicTable(rcTopicsBody, droneTopicsBody);

function updateStatus(message, tone = "neutral") {
  statusEl.textContent = `状态：${message}`;
  statusEl.className = tone === "success" ? "status-ok" : tone === "error" ? "status-error" : "";
}

function gatherConnectionConfig() {
  const host = hostInput.value.trim();
  const port = portInput.value.trim();
  const username = usernameInput.value.trim();
  const password = passwordInput.value.trim();
  const deviceSn = deviceSnInput.value.trim();
  const gatewaySn = gatewaySnInput.value.trim();
  const useTls = useTlsSelect.value === "true";
  const clientId = ensureClientId(clientIdInput.value);

  return { host, port, username, password, deviceSn, gatewaySn, useTls, clientId };
}

function validateConfig({ host, port, deviceSn, gatewaySn }) {
  if (!host || !port || !deviceSn || !gatewaySn) {
    updateStatus("请填写主机、端口、设备SN和网关SN", "error");
    return false;
  }
  return true;
}

function handleConnect() {
  connectBtn.disabled = true;

  const config = gatherConnectionConfig();
  if (!validateConfig(config)) {
    connectBtn.disabled = false;
    return;
  }

  const { rcTopics, droneTopics } = buildTopics(config.deviceSn, config.gatewaySn);
  const allTopics = [...rcTopics, ...droneTopics];

  if (!allTopics.length) {
    updateStatus("没有可订阅的主题，请检查 SN 输入", "error");
    connectBtn.disabled = false;
    return;
  }

  populateTopicTable(rcTopics, droneTopics);

  disconnectBtn.disabled = true;

  const url = connectClient({
    host: config.host,
    port: config.port,
    useTls: config.useTls,
    username: config.username,
    password: config.password,
    clientId: config.clientId,
    topics: allTopics,
    onStatus: (message) => updateStatus(message),
    onConnected: () => {
      updateStatus(`已连接 ${url}`, "success");
      disconnectBtn.disabled = false;
    },
    onReconnecting: () => {
      updateStatus("正在重连...");
    },
    onDisconnected: () => {
      updateStatus("连接已断开", "error");
      connectBtn.disabled = false;
      disconnectBtn.disabled = true;
    },
    onError: (err) => {
      const message = err?.message ? `连接错误：${err.message}` : "连接出现未知错误";
      updateStatus(message, "error");
      connectBtn.disabled = false;
      disconnectBtn.disabled = true;
    },
    onMessage: (topic, payload) => {
      const messageInfo = parseMessagePayload(payload);
      applyTopicMessage(topic, messageInfo);
    },
  });
}

function handleDisconnect() {
  if (!hasActiveClient()) {
    return;
  }
  disconnectClient();
  updateStatus("已断开", "error");
  connectBtn.disabled = false;
  disconnectBtn.disabled = true;
}

connectBtn.addEventListener("click", handleConnect);
disconnectBtn.addEventListener("click", handleDisconnect);

window.addEventListener("beforeunload", () => disconnectClient());
window.addEventListener("load", () => {
  handleConnect();
});
