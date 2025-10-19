# 云端控制授权卡片逻辑说明

本文档梳理 `CloudControlCard` 的整体交互流程、关键模块职责以及它与 MQTT 服务之间的连锁反应，帮助开发者快速定位问题或扩展功能。

---

## 1. 目标与角色

- **目标**：允许地面站为当前选中的无人机请求云端飞行控制权（`flight` 控制键），并在页面上展示状态与日志。
- **关键角色**：
  - `CloudControlCard.astro`：界面结构与入口脚本。
  - `CloudControlCardUI` 控制器：统一管理状态、事件绑定与服务调用。
  - `AuthStateManager`：维护授权状态与会话信息。
  - `UIUpdater`：根据状态更新 DOM。
  - `LogManager`：同步卡片日志与中央调试系统。
  - `ErrorHandler`：统一生成错误提示与恢复建议。
  - `TopicServiceManager`：通过 MQTT 调用云端授权服务。

---

## 2. 初始化流程

1. **Astro 卡片加载**  
   `CloudControlCard.astro` 在浏览器环境初始化后导入 `cloudControlCardUI` 实例，并挂到 `window.cloudControlCardUI` 供调试或手动调用。

2. **控制器构造** (`cloud-control-ui.js:15`)  
   - 创建 `AuthStateManager`、`LogManager`、`ErrorHandler`、`UIUpdater`。
   - 通过 `cardStateManager.register` 将自身注册到全局卡片状态系统。

3. **init()** (`cloud-control-ui.js:33`)  
   - 从 `AuthStateManager` 恢复用户配置（用户 ID、呼号）。
   - 在浏览器环境下绑定 DOM 元素、事件、监听器，并执行第一次 `updateUI()`。
   - 监听：
     - `device-changed`：设备切换时刷新 MQTT 状态显示。
     - `mqtt-connection-changed`：MQTT 连接变化时更新状态、写日志。
     - `card-state-restored`：跨页面恢复状态时同步 UI。

4. **服务路由注册** (`cloud-control-ui.js:120`)  
   - `MessageRouter` 注册 `cloud_control_auth_request` 的回复回调，供 MQTT 消息进来时触发 UI 更新。

---

## 3. UI 与状态同步

### `UIUpdater.updateUI(authStateManager)`
- **状态指示**：更新状态文本、颜色、加载动画。
- **控制键展示**：展示当前获得的控制键（无则 `-`）。
- **按钮区**：根据 `authStatus` 切换请求/确认按钮、禁用状态与 loading。
- **MQTT 状态**：查询 `deviceContext` 当前 SN，并通过 `window.mqttManager.getConnection(sn)` 判断是否连接。

### 状态广播
- 每次调用 `updateUI()` 后，卡片会触发全局事件 `cloud-control-status-changed`，方便其他模块感知授权状态变化。

---

## 4. 授权请求主流程

### 4.1 用户触发
- 点击“请求云端控制授权”按钮 → `CloudControlCardUI.requestAuth()`。
- 日志阶段标签写入 `[AUTH][stage]` 以便追踪半途卡点。

### 4.2 参数准备与校验
1. 获取当前设备 SN (`deviceContext.getCurrentDevice()`)，记录上下文。
2. `ErrorHandler.validateAuthRequest` 目前只检查：
   - 是否选择设备。
   - 用户 ID / 呼号是否填写。
   （设备在线检查已按需求移除）。
3. 校验成功后进入请求流程，否则记录错误并输出恢复建议。

### 4.3 状态迁移与 UI
- 调用 `authStateManager.startAuthRequest()`，将状态置为 `requesting` 并保存开始时间。
- 设置 30s 超时，超时回调会自动重置状态并输出建议。
- 同步 `AuthStateManager` → 实例字段 → 更新 UI 按钮与状态显示。

### 4.4 MQTT 服务调用
1. 构造请求体：
   ```json
   {
     "user_id": "<UserID>",
     "user_callsign": "<Callsign>",
     "control_keys": ["flight"]
   }
   ```
2. `TopicServiceManager.callService(sn, 'cloud_control_auth_request', requestData)`：
   - 等待 MQTT 管理器初始化完成。
   - 若本地缓存中无连接或 `!isConnected`，自动调用 `ensureConnection(sn)` 重新建立 `station-${sn}` 客户端。
   - 生成服务消息（包含 `tid`/`bid`），并通过 MQTT 发布到模板定义的主题。
   - 如果 `options.noWait` 未设置，则挂起回调等待匹配的服务回复；超时会返回 `SERVICE_RESULT.TIMEOUT`。

### 4.5 调用结果
- **成功发送**：保存 `tid`，日志记录等待遥控器确认。
- **发送失败**：`ErrorHandler.handleServiceError` 输出具体错误和恢复建议，同时重置状态与 UI。
- **异常捕获**：同上，确保状态回滚，UI 还原。

---

## 5. 授权回复处理

当设备通过 MQTT 返回 `cloud_control_auth_request` 的服务回复时，`MessageRouter` 会触发 `CloudControlCardUI.handleAuthRequestReply(msg)`：

1. `ErrorHandler.handleAuthReply` 判定是否匹配当前 `tid`，并根据返回值执行：
   - `result === 0 && status === 'ok'`：授权成功 → `AuthStateManager.setAuthorized()` → 记录耗时 → 输出成功日志。
   - `result === 0 && status === 'in_progress'`：请求已下发至遥控器 → 提示用户在遥控器确认，并保留 `requesting` 状态。
   - 其他结果：视为失败 → 复位状态并输出具体建议（例如遥控器拒绝、不支持、状态不可授权）。
2. 若需要更新 UI，则调用 `syncFromAuthState()` + `updateUI()`。

---

## 6. 手动确认流程

- “确认已在遥控器上授权”按钮触发 `CloudControlCardUI.confirmAuth()`：
  - 直接将状态置为 `authorized`，计算耗时，提示可以使用云端控制。
  - 适用于遥控器无自动回传或调试场景。

---

## 7. 监听器与连锁反应

| 事件源 | 监听位置 | 作用 | 后续操作 |
| ------ | -------- | ---- | -------- |
| `deviceContext` 设备切换 | `setupDeviceContextListener()` | 更新 MQTT 状态指示 | `UIUpdater.updateMqttStatus()` |
| MQTT 连接变化 (`mqtt-connection-changed`) | `setupMqttListener()` | 记录连接建立/断开，若正在请求授权时断开则重置状态 | 调用 `ErrorHandler.handleMqttConnectionChange()`，必要时 `updateUI()` |
| `card-state-restored` | `setupStateRestoreListener()` | 从持久化状态恢复字段与日志 | `syncToAuthState()`、`updateUI()`、`restoreLogsFromState()` |
| 全局 DEBUG 日志 | `LogManager.addLog()` | 推送到中央调试系统 (`debugLogger`) | 以 `[CloudControl-<SN>]` 形式记录 |
| 服务回复 | `MessageRouter` → `handleAuthRequestReply()` | 更新授权状态 | 触发 UI 变更与日志 |

---

## 8. 日志体系

- 所有按钮动作、阶段节点使用 `LogManager` 写入 UI 终端，同时同步到中央调试系统。
- 额外的 `[AUTH][stage]` 调试日志覆盖：
  - `validation_context`：输入参数与连接状态快照。
  - `service_call` / `service_reply` / `service_error`：MQTT 服务调用链路。
  - `prepare_state` / `ui_synced`：状态机与 UI 切换过程。
- 用户可通过下拉筛选器查看不同类型日志，也可在控制台通过 `window.cloudControlCardUI.logManager.exportLogs()` 导出。

---

## 9. 关键状态与字段

| 字段 | 来源 | 用途 |
| ---- | ---- | ---- |
| `authStateManager.authStatus` | `AuthStateManager` | 授权状态枚举：`unauthorized` / `requesting` / `authorized` |
| `controlKeys` | `AuthStateManager` | 拥有的控制权（目前固定为 `flight`） |
| `currentRequestTid` | `AuthStateManager` | 当前授权请求的服务 TID，用于匹配回复 |
| `authStartTime` / `authorizedAt` | `AuthStateManager` | 计算授权时长、展示日志 |
| `userId` / `userCallsign` | `AuthStateManager` + 输入框 | 作为服务调用参数，并持久化到 `localStorage` |
| `deviceContext.currentDevice` | `DeviceContext` | 当前操作的设备 SN |

---

## 10. 扩展与排障建议

- **新增控制键**：在 `requestAuth` 的 `requestData.control_keys` 增加对应键值，同时调整 UI 展示。
- **跨模块监听授权**：订阅 `cloud-control-status-changed` 事件，读取 `detail` 中的状态、控制键与授权用户。
- **排查“未连接”问题**：关注 `[AUTH][request.validation_context]` 与 `[AUTH][request.service_reply]` 阶段日志；确认 `mqttManager.ensureConnection()` 是否成功，以及 EMQX 中是否存在 `station-${sn}` 客户端。
- **自定义错误提示**：在 `ErrorHandler.provideSpecificErrorAdvice` 与 `getErrorRecoveryAdvice` 中添加分支。
- **持久化策略**：`cardStateManager` 负责跨路由保存卡片状态，如需额外字段，确保在 `syncToAuthState()` / `syncFromAuthState()` 中同步。

---

通过以上梳理可以看到：云端控制卡片通过控制器驱动 UI、状态管理器、日志系统与 MQTT 服务协同工作。从按钮点击到遥控器确认的整个链条，都有对应的日志与事件，便于调试与扩展。若后续引入更多服务或控制动作，可复用同样的模式快速构建交互流程。
