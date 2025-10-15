# 多设备卡片状态管理系统使用指南

## 📚 概述

这是一个**零侵入式**的状态管理系统，通过JavaScript Proxy自动拦截卡片的状态读写，实现**多设备状态隔离和自动切换**。

### 核心特性

- ✅ **零侵入**：卡片代码几乎不需要修改
- ✅ **自动隔离**：每个设备(SN)的状态完全独立
- ✅ **自动切换**：设备切换时自动保存/恢复状态
- ✅ **持久化**：支持localStorage自动持久化
- ✅ **类型安全**：保持卡片原有的代码结构

---

## 🏗️ 架构

```
┌──────────────────────────────────────────────────┐
│         CardStateManager (统一入口)               │
├──────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌────────────────────┐   │
│  │ CardStateProxy   │  │ DeviceStateManager │   │
│  │  (Proxy拦截器)   │  │   (状态存储)        │   │
│  └──────────────────┘  └────────────────────┘   │
└──────────────────────────────────────────────────┘
                      ↓
        ┌────────────────────────────┐
        │   设备状态结构 (Map)        │
        ├────────────────────────────┤
        │ SN-1                        │
        │   ├─ drcControl: {...}      │
        │   └─ streaming: {...}       │
        │ SN-2                        │
        │   ├─ drcControl: {...}      │
        │   └─ streaming: {...}       │
        └────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 在卡片中集成（仅需3步）

以 `DrcControlCardUI` 为例：

```javascript
// Step 1: 导入状态管理器
import cardStateManager from '@/shared/core/card-state-manager.js';

export class DrcControlCardUI {
  constructor() {
    this.controller = defaultDrcController;

    // Step 2: 定义需要跨设备保持的状态属性
    this.currentStep = 'idle';       // 工作流步骤
    this.drcStatus = 'inactive';     // DRC状态
    this.logsHTML = '';              // 日志HTML

    this.init();

    // Step 3: 注册到状态管理器（返回代理对象）
    return cardStateManager.register(this, 'drcControl', {
      debug: true  // 可选：开启调试模式
    });
  }

  init() {
    // ... 其他初始化代码

    // 监听设备切换后的状态恢复事件
    window.addEventListener('card-state-restored', () => {
      this.updateUI();  // 刷新UI
    });
  }

  // 在状态变化时，直接赋值即可（会自动保存）
  someMethod() {
    this.currentStep = 'requesting';  // 自动保存到当前设备的状态
    this.drcStatus = 'active';        // 自动保存
  }
}
```

**就是这样！** 不需要任何`setState()`或`getState()`调用。

---

## 📖 详细说明

### 状态代理机制

当你写：
```javascript
this.currentStep = 'requesting';
```

实际上会被Proxy拦截并自动执行：
```javascript
deviceStateManager.setState(当前SN, 'drcControl', 'currentStep', 'requesting');
```

当你读：
```javascript
const step = this.currentStep;
```

实际上会被Proxy拦截并自动执行：
```javascript
const step = deviceStateManager.getState(当前SN, 'drcControl', 'currentStep');
```

**完全透明，无需手动调用！**

---

### 设备切换流程

```
用户点击设备切换器：SN-1 → SN-2

              ↓

DeviceContext 触发 'device-changed' 事件

              ↓

CardStateManager 监听到事件
  ├─ 通知所有 CardStateProxy 切换设备
  └─ 触发 'card-state-restored' 事件

              ↓

CardStateProxy 执行
  ├─ 从 DeviceStateManager 读取 SN-2 的状态
  └─ 应用到卡片实例

              ↓

卡片监听 'card-state-restored' 事件
  └─ 调用 updateUI() 刷新界面

              ↓

用户看到 SN-2 的完整状态
```

---

## 🎯 配置选项

### register() 方法参数

```javascript
cardStateManager.register(cardInstance, cardId, options);
```

**参数说明**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `cardInstance` | Object | ✅ | 卡片实例（通常是`this`） |
| `cardId` | String | ✅ | 卡片唯一ID（如`'drcControl'`） |
| `options` | Object | ❌ | 配置选项 |

**options 配置项**：

```javascript
{
  // 仅代理这些属性（留空则代理所有）
  includedProps: ['status', 'logs'],

  // 排除这些属性（函数方法默认已排除）
  excludedProps: ['controller', 'elements'],

  // 是否自动同步DOM元素（暂未实现）
  syncDOMElements: true,

  // 开启调试模式（打印状态读写日志）
  debug: true
}
```

---

## 💡 最佳实践

### ✅ DO - 推荐做法

1. **明确定义状态属性**
   ```javascript
   constructor() {
     // 在构造函数中初始化所有状态属性
     this.status = 'idle';
     this.logs = [];
     this.config = {};
   }
   ```

2. **使用基本类型或可序列化对象**
   ```javascript
   this.status = 'active';        // ✅ 字符串
   this.count = 42;               // ✅ 数字
   this.logs = ['log1', 'log2'];  // ✅ 数组
   this.config = { a: 1, b: 2 };  // ✅ 普通对象
   ```

3. **监听状态恢复事件更新UI**
   ```javascript
   window.addEventListener('card-state-restored', () => {
     this.updateUI();
     this.restoreLogsFromState();
   });
   ```

### ❌ DON'T - 避免做法

1. **不要存储DOM元素**
   ```javascript
   this.element = document.getElementById('xxx');  // ❌ 无法序列化
   ```

2. **不要存储函数或类实例**
   ```javascript
   this.callback = () => {};          // ❌ 函数
   this.controller = new Controller(); // ❌ 类实例
   ```

3. **不要存储循环引用对象**
   ```javascript
   const obj = {};
   obj.self = obj;  // ❌ 循环引用
   this.data = obj;
   ```

---

## 🛠️ API 参考

### CardStateManager

#### `register(cardInstance, cardId, options)`
注册卡片到状态管理系统
```javascript
return cardStateManager.register(this, 'myCard');
```

#### `unregister(cardId)`
注销卡片
```javascript
cardStateManager.unregister('myCard');
```

#### `snapshotAll(sn)`
手动快照所有卡片状态
```javascript
cardStateManager.snapshotAll();  // 当前设备
cardStateManager.snapshotAll('SN001');  // 指定设备
```

#### `restoreAll(sn)`
手动恢复所有卡片状态
```javascript
cardStateManager.restoreAll('SN002');
```

#### `clearDeviceStates(sn)`
清除指定设备的所有状态
```javascript
cardStateManager.clearDeviceStates('SN001');
```

#### `setPersistence(enabled)`
启用/禁用localStorage持久化
```javascript
cardStateManager.setPersistence(false);  // 禁用
```

#### `debug()`
打印调试信息
```javascript
cardStateManager.debug();
```

---

### DeviceStateManager（低级API，通常不需要直接使用）

#### `getCardState(sn, cardId)`
获取指定设备的指定卡片的完整状态对象

#### `setState(sn, cardId, key, value)`
设置单个状态属性

#### `updateCardState(sn, cardId, updates)`
批量更新状态

---

## 🔍 调试

### 1. 开启调试模式

```javascript
cardStateManager.register(this, 'myCard', { debug: true });
```

控制台会输出：
```
[CardStateProxy][myCard] SET status: active
[CardStateProxy][myCard] GET status: active
```

### 2. 查看所有状态

在浏览器控制台：
```javascript
// 方法1: 使用调试方法
cardStateManager.debug();

// 方法2: 直接查看
window.deviceStateManager.getAllStates();

// 方法3: 查看统计
cardStateManager.getStats();
```

### 3. 手动清除状态

```javascript
// 清除当前设备的某个卡片状态
deviceStateManager.clearCardState('SN001', 'drcControl');

// 清除所有状态
localStorage.clear();
```

---

## 📝 实际示例

### 示例1：DRC控制卡片（已实现）

```javascript
export class DrcControlCardUI {
  constructor() {
    // 状态属性
    this.currentStep = 'idle';
    this.drcStatus = 'inactive';
    this.logsHTML = '<div>初始日志</div>';

    this.init();
    return cardStateManager.register(this, 'drcControl', { debug: true });
  }

  // 状态变化时直接赋值
  updateStatus(newStatus) {
    this.drcStatus = newStatus;  // 自动保存到当前设备
    this.updateUI();
  }

  addLog(message) {
    this.logsHTML += `<div>${message}</div>`;  // 自动保存
    this.elements.logs.innerHTML = this.logsHTML;
  }
}
```

### 示例2：视频流卡片（待实现）

```javascript
export class StreamingCardUI {
  constructor() {
    // 状态属性
    this.isPlaying = false;
    this.rtmpUrl = '';
    this.connectionStatus = 'disconnected';
    this.logsHTML = '';

    this.init();
    return cardStateManager.register(this, 'streaming');
  }

  toggleStream() {
    this.isPlaying = !this.isPlaying;  // 自动保存
    // ... 其他逻辑
  }
}
```

---

## ⚙️ 持久化机制

### 自动持久化

状态会自动保存到localStorage：

```
localStorage
├─ device_state_SN001_drcControl: {...}
├─ device_state_SN001_streaming: {...}
├─ device_state_SN002_drcControl: {...}
└─ device_state_SN002_streaming: {...}
```

### 页面刷新后恢复

页面刷新时，`DeviceStateManager` 会自动从localStorage加载所有状态：

```javascript
// 自动执行（无需手动调用）
constructor() {
  this.loadFromStorage();
}
```

---

## 🎓 进阶用法

### 自定义状态序列化

如果需要存储复杂对象，可以在卡片中实现序列化/反序列化：

```javascript
constructor() {
  this._complexDataJSON = '';  // 存储JSON字符串

  this.init();
  return cardStateManager.register(this, 'myCard');
}

setComplexData(data) {
  this._complexDataJSON = JSON.stringify(data);
}

getComplexData() {
  return JSON.parse(this._complexDataJSON || '{}');
}
```

---

## 🐛 常见问题

### Q1: 状态没有保存？

**检查清单**：
1. 是否在构造函数中调用了`register()`？
2. 是否返回了`register()`的结果？
3. 状态属性是否是可序列化类型？
4. 是否有语法错误导致代理失败？

### Q2: 切换设备后UI没更新？

**解决方法**：
确保添加了状态恢复监听器：
```javascript
window.addEventListener('card-state-restored', () => {
  this.updateUI();
});
```

### Q3: 某些属性不想被代理？

**解决方法**：
使用 `excludedProps` 配置：
```javascript
cardStateManager.register(this, 'myCard', {
  excludedProps: ['controller', 'elements', '_internal']
});
```

### Q4: 想禁用持久化？

**解决方法**：
```javascript
cardStateManager.setPersistence(false);
```

---

## 📊 性能考虑

- **Proxy开销**：极小，现代浏览器优化很好
- **内存占用**：每个设备的状态独立存储，注意不要存储过大对象
- **持久化开销**：每次状态变化都会写localStorage，频繁写入可能影响性能

**建议**：
- 日志类数据可以考虑限制条数（如只保留最近100条）
- 大量频繁变化的数据可以考虑debounce后再保存

---

## 🔗 相关文件

```
src/shared/core/
├── device-state-manager.js     # 核心状态存储
├── card-state-proxy.js         # Proxy拦截器
└── card-state-manager.js       # 统一入口
```

---

## 📝 TODO（未来改进）

- [ ] 支持状态版本管理（migration）
- [ ] 支持状态压缩（减小localStorage占用）
- [ ] 支持状态导出/导入
- [ ] 支持状态diff和merge
- [ ] 支持远程状态同步

---

## 🙌 贡献

如果你发现问题或有改进建议，欢迎反馈！
