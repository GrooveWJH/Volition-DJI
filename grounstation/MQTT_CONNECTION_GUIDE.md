# 全局 MQTT-SN Handler 使用指南

## 📋 功能概述

全局 MQTT 连接池管理器已成功集成到地面站系统中，为每个设备 SN 提供独立的 MQTT 长连接管理。

### 核心特性

- ✅ **自动连接管理**：点击设备自动创建 MQTT 连接
- ✅ **连接池维护**：多设备连接同时保持，直到设备下线
- ✅ **状态可视化**：设备切换器指示灯颜色表示连接状态
- ✅ **全局访问**：通过 `window.mqttManager` 在任何 Card 中使用
- ✅ **配置持久化**：MQTT Broker 配置保存到 localStorage

## 🎨 连接状态指示

设备切换器中的指示灯颜色代表不同的连接状态：

| 颜色 | 状态 | 说明 |
|------|------|------|
| 🟢 绿色呼吸 | 设备在线，未连接 MQTT | 设备已发现但尚未建立 MQTT 连接 |
| 🔵 蓝色呼吸 | 设备在线，MQTT 已连接 | MQTT 连接正常，可以收发消息 |
| 🟠 橙色闪烁 | MQTT 连接中 | 正在建立或重连 MQTT 连接 |
| 🔴 红色 | MQTT 连接错误 | 连接失败或出现错误 |
| ⚪ 灰色 | 设备离线 | 设备不在线 |

## ⚙️ 配置说明

### 1. 打开设置面板

点击设备切换器右侧的齿轮图标 ⚙️

### 2. 配置 MQTT Broker

在左栏 "MQTT Broker 配置" 中填写：

- **Broker 地址**：MQTT 服务器地址（默认：192.168.31.116）
- **WebSocket 端口**：WebSocket 端口（默认：8083）
- **用户名**：MQTT 认证用户名（默认：admin）
- **密码**：MQTT 认证密码（默认：public）

### 3. 保存配置

点击 "保存全部" 按钮，配置会保存到 localStorage

## 🔌 连接生命周期

### 自动连接流程

1. **设备发现**：DeviceManager 扫描到设备
2. **设备切换**：用户点击切换到某个设备
3. **创建连接**：MqttConnectionManager 自动为该设备创建连接
   - ClientID：`station-{SN}`
   - 自动订阅默认主题
4. **状态更新**：设备指示灯变为蓝色呼吸

### 连接保持机制

- 切换到其他设备时，先前的连接**不会断开**
- 多个设备可以同时保持 MQTT 连接
- 连接失败自动重试（最多 3 次）

### 自动断开条件

- 设备从在线变为离线
- 页面关闭/刷新（自动清理）

## 💻 在 Card 中使用 MQTT 连接

### 获取当前设备的连接

```javascript
// 方式1：获取当前选中设备的连接
const connection = window.mqttManager.getCurrentConnection();

// 方式2：获取指定设备的连接
const connection = window.mqttManager.getConnection('设备SN');

if (connection && connection.isConnected()) {
  // 连接可用
}
```

### 发布消息

```javascript
const sn = deviceContext.getCurrentDevice();
const topic = `thing/product/${sn}/services`;
const payload = {
  method: 'camera_mode_switch',
  data: { mode: 1 }
};

await window.mqttManager.publish(sn, topic, payload);
```

### 订阅主题

```javascript
const sn = deviceContext.getCurrentDevice();
const topic = `thing/product/${sn}/services_reply`;

window.mqttManager.subscribe(sn, topic, (message, topic) => {
  console.log('收到消息:', message);
  // 处理消息
});
```

### 直接使用连接对象

```javascript
const connection = window.mqttManager.getCurrentConnection();

if (connection) {
  // 订阅
  connection.subscribe('custom/topic', (msg) => {
    console.log(msg);
  });

  // 发布
  await connection.publish('custom/topic', { data: 'test' });

  // 检查状态
  console.log('连接状态:', connection.getState());
  console.log('是否已连接:', connection.isConnected());
}
```

### 监听连接状态变化

```javascript
window.addEventListener('mqtt-connection-changed', (event) => {
  const { sn, state, oldState } = event.detail;
  console.log(`设备 ${sn} 状态: ${oldState} → ${state}`);
});
```

## 🔍 调试和监控

### 查看所有连接

```javascript
// 获取连接统计
const stats = window.mqttManager.getStats();
console.log('连接统计:', stats);
// { total: 3, connected: 2, connecting: 1, disconnected: 0, error: 0 }

// 获取详细信息
const info = window.mqttManager.getConnectionsInfo();
console.log('连接详情:', info);
```

### 手动管理连接

```javascript
// 手动创建连接
await window.mqttManager.connect('设备SN');

// 断开指定设备连接
await window.mqttManager.disconnect('设备SN');

// 断开所有连接
await window.mqttManager.disconnectAll();

// 启用/禁用自动连接
window.mqttManager.setAutoConnect(false);
```

## 📦 默认订阅主题

每个连接建立后会自动订阅以下主题（{sn} 会替换为实际设备 SN）：

- `thing/product/{sn}/services_reply`
- `thing/product/{sn}/drc/down`
- `thing/product/{sn}/state`

## 🛠️ 故障排查

### 连接失败

1. 检查 MQTT Broker 配置是否正确
2. 确认 WebSocket 端口（通常是 8083 或 8084）
3. 查看浏览器控制台的错误日志
4. 测试 Broker 是否可访问：`ws://{host}:{port}/mqtt`

### 状态不更新

- 刷新页面重新初始化
- 检查控制台是否有错误信息
- 确认设备是否在线

### 消息未收到

- 确认连接状态为 "connected"（蓝色指示灯）
- 检查订阅的主题名称是否正确
- 查看控制台日志中的消息记录

## 📁 相关文件

### 核心文件
- `src/shared/services/mqtt-connection-manager.js` - 连接池管理器
- `src/shared/services/mqtt-client-wrapper.js` - MQTT 客户端封装
- `src/shared/config/mqtt-config.js` - MQTT 配置和常量

### UI 集成
- `src/shared/components/DroneDeviceSwitcher.astro` - 设备切换器（包含状态显示）
- `src/styles/global.css` - 状态指示灯样式

### 依赖管理
- `src/shared/core/device-context.js` - 设备上下文
- `src/shared/services/device-manager.js` - 设备管理器

## 🔄 版本信息

- MQTT.js 版本：5.14.1
- 实现日期：2025-10-14
- 支持的协议：WebSocket (ws://)

## 📝 注意事项

1. **不要在 Card 中手动管理连接**：使用全局管理器统一管理
2. **ClientID 自动生成**：格式为 `station-{SN}`，无需手动指定
3. **配置变更**：修改 MQTT 配置后需要重新创建连接才能生效
4. **页面刷新**：刷新后连接会自动重建（如果设备仍在线）
5. **性能考虑**：避免频繁创建/销毁连接，利用连接池机制

## ✅ 测试清单

- [ ] 配置 MQTT Broker 信息并保存
- [ ] 点击设备，观察指示灯变为蓝色
- [ ] 切换多个设备，确认都能建立连接
- [ ] 在控制台测试发布/订阅功能
- [ ] 模拟设备离线，确认连接自动断开
- [ ] 刷新页面，确认连接自动恢复

---

**如有问题或建议，请查看控制台日志或联系开发团队。**
