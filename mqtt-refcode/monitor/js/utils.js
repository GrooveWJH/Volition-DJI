const CLIENT_ID_PREFIX = "monitor-";

export function currentTime() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

export function ensureClientId(rawClientId = "") {
  const trimmed = rawClientId.trim();
  if (trimmed) {
    return trimmed;
  }
  return `${CLIENT_ID_PREFIX}${Math.random().toString(16).slice(2)}`;
}

export function stringifyPayload(payload) {
  if (!payload) {
    return "暂无数据";
  }
  try {
    const parsed = JSON.parse(payload);
    return JSON.stringify(parsed, null, 2);
  } catch (err) {
    return payload;
  }
}

export function parseMessagePayload(payload) {
  const text =
    typeof payload === "string"
      ? payload
      : payload === undefined || payload === null
      ? ""
      : String(payload);
  if (!text.trim()) {
    return {
      formatted: "暂无数据",
      method: "未知",
      raw: null,
      rawText: text,
      isJson: false,
    };
  }
  try {
    const parsed = JSON.parse(text);
    const method =
      typeof parsed.method === "string" && parsed.method.trim()
        ? parsed.method.trim()
        : "无 method";
    return {
      formatted: JSON.stringify(parsed, null, 2),
      method,
      raw: parsed,
      rawText: text,
      isJson: true,
    };
  } catch (err) {
    return {
      formatted: text,
      method: "非 JSON",
      raw: null,
      rawText: text,
      isJson: false,
    };
  }
}
