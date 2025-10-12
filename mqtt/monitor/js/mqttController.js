let client = null;

export function connectClient(config) {
  const {
    host,
    port,
    useTls,
    username,
    password,
    clientId,
    topics,
    onStatus,
    onConnected,
    onReconnecting,
    onDisconnected,
    onError,
    onMessage,
  } = config;

  disconnectClient();

  const protocol = useTls ? "wss" : "ws";
  const url = `${protocol}://${host}:${port}/mqtt`;

  const options = {
    clientId,
    clean: true,
    reconnectPeriod: 5000,
  };

  if (username) {
    options.username = username;
    options.password = password;
  }

  onStatus?.(`正在连接 ${url}`);

  client = mqtt.connect(url, options);

  client.on("connect", () => {
    onStatus?.(`已连接 ${url}`);
    onConnected?.();
    topics.forEach(({ topic }) => {
      client.subscribe(topic, (err) => {
        if (err) {
          onError?.(`订阅 ${topic} 失败：${err.message}`);
        }
      });
    });
  });

  client.on("reconnect", () => {
    onStatus?.("正在重连...");
    onReconnecting?.();
  });

  client.on("close", () => {
    onStatus?.("连接已断开");
    onDisconnected?.();
  });

  client.on("error", (err) => {
    onError?.(err);
  });

  client.on("message", (topic, payload) => {
    onMessage?.(topic, payload.toString());
  });

  return url;
}

export function disconnectClient() {
  if (!client) return;
  client.end(true);
  client = null;
}

export function hasActiveClient() {
  return Boolean(client);
}
