# 测试目录

本目录包含 DJI Ground Station 项目的单元测试和集成测试。

## 目录结构

```
tests/
├── unit/                          # 单元测试（独立模块测试）
│   ├── topic-template-manager.test.js    # TopicTemplateManager 测试
│   └── message-router.test.js            # MessageRouter 测试
├── integration/                   # 集成测试（端到端流程测试）
│   └── cloud-control-auth.test.js        # 云端控制授权完整流程测试
├── helpers/                       # 测试工具库
│   ├── logger.js                         # 彩色日志输出
│   └── mock-helpers.js                   # Mock 工具（浏览器环境、MQTT 等）
└── fixtures/                      # 测试数据
    └── topic-templates.json              # 服务模板配置
```

---

## 🧪 单元测试 (Unit Tests)

单元测试用于测试**单个模块或类**的逻辑，隔离外部依赖（使用 Mock）。

### 运行所有单元测试

```bash
pnpm test:unit
```

### 运行特定单元测试

```bash
# 测试 TopicTemplateManager
node tests/unit/topic-template-manager.test.js

# 测试 MessageRouter
node tests/unit/message-router.test.js
```

### 单元测试覆盖

#### TopicTemplateManager 测试
- ✅ 加载模板配置
- ✅ 构建服务主题（替换 {sn}）
- ✅ 构建响应主题
- ✅ 构建服务消息（参数验证、默认值）
- ✅ 缺少必需参数时抛出错误
- ✅ 未知服务抛出错误
- ✅ 生成 TID/BID
- ✅ 获取服务超时时间
- ✅ 获取所有服务列表

#### MessageRouter 测试
- ✅ 注册/注销路由规则
- ✅ EXACT 类型精确匹配
- ✅ PREFIX 类型前缀匹配
- ✅ SERVICE 类型服务回复匹配
- ✅ 通配符 `*` 匹配所有服务回复
- ✅ 正确识别消息类型 (SERVICE_REPLY, DRC_DATA, etc.)
- ✅ 从主题提取 SN
- ✅ 解析 JSON 消息
- ✅ 收集统计信息
- ✅ 支持多个回调
- ✅ 回调异常不影响其他回调

---

## 🚀 集成测试 (Integration Tests)

集成测试用于测试**多个模块协作**的完整流程，使用**真实的 MQTT 连接**。

### 云端控制授权集成测试

测试完整的云端控制授权流程：创建 MQTT 客户端 → 连接 Broker → 发送授权请求 → 等待回复。

#### 基本用法

```bash
node tests/integration/cloud-control-auth.test.js <SN>
```

**示例：**

```bash
# 使用默认配置测试设备 9N9CN2J0012CXY
node tests/integration/cloud-control-auth.test.js 9N9CN2J0012CXY

# 指定 MQTT Broker 地址
node tests/integration/cloud-control-auth.test.js 9N9CN2J0012CXY --host 192.168.1.100 --port 8083

# 测试释放控制（而非请求授权）
node tests/integration/cloud-control-auth.test.js 9N9CN2J0012CXY --release
```

#### 完整参数列表

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<SN>` | 设备序列号（14位） | **必需** |
| `--host <host>` | MQTT Broker 地址 | `192.168.31.116` |
| `--port <port>` | MQTT Broker 端口 | `8083` |
| `--user-id <id>` | 用户 ID | `test_user_001` |
| `--user-callsign <name>` | 用户呼号 | `TestStation` |
| `--timeout <ms>` | 超时时间 | `30000` (30秒) |
| `--release` | 测试释放控制 | false |

#### 测试流程

1. ✅ 创建 MQTT 客户端 (`station-<SN>`)
2. ✅ 连接到 MQTT Broker
3. ✅ 订阅回复主题 (`thing/product/{sn}/services_reply`)
4. ✅ 发送授权请求到 `thing/product/{sn}/services`
5. ✅ 等待并解析回复消息
6. ✅ 验证 TID 匹配
7. ✅ 分析结果 (result === 0 表示成功)

#### 预期输出（成功）

```
============================================================
  云端控制授权集成测试
============================================================

[+0ms] [TEST] [INFO] 测试配置:
┌────────────────┬────────────────────────┐
│ 设备序列号     │ 9N9CN2J0012CXY         │
│ MQTT Broker    │ 192.168.31.116:8083    │
│ 客户端ID       │ station-9N9CN2J0012CXY │
│ 用户ID         │ test_user_001          │
│ 用户呼号       │ TestStation            │
│ 测试类型       │ 请求授权                │
│ 超时时间       │ 30000ms                 │
└────────────────┴────────────────────────┘

▶ 步骤1: 创建 MQTT 客户端
[+120ms] [TEST] [✓ SUCCESS] MQTT 连接成功

▶ 步骤3: 订阅回复主题
[+245ms] [TEST] [✓ SUCCESS] 订阅成功: thing/product/9N9CN2J0012CXY/services_reply

▶ 步骤4: 发送授权请求
[+267ms] [TEST] [✓ SUCCESS] 消息已发送到: thing/product/9N9CN2J0012CXY/services
[+268ms] [TEST] [INFO] TID: tid_1704038400123_a1b2c3d4
[+269ms] [TEST] [INFO] 等待回复...

▶ 步骤5: 收到回复消息
[+5421ms] [TEST] [✓ SUCCESS] TID 匹配

▶ 步骤6: 分析结果
[+5423ms] [TEST] [✓ SUCCESS] ✓ 授权请求成功
[+5424ms] [TEST] [✓ SUCCESS]   Result: 0
[+5425ms] [TEST] [✓ SUCCESS]   Status: ok
[+5426ms] [TEST] [INFO]
[+5427ms] [TEST] [INFO] 🎉 云端控制授权已获批准！

============================================================
  测试完成
============================================================

[+5450ms] [TEST] [✓ SUCCESS] 所有步骤执行成功
```

#### 故障排查

**1. 连接超时**
```
✗ ERROR MQTT 连接错误: Connection timeout
```
- 检查 MQTT Broker 是否运行
- 检查 `--host` 和 `--port` 参数是否正确
- 检查网络连接

**2. 订阅失败**
```
✗ ERROR 订阅失败: Not authorized
```
- 检查 MQTT Broker 的 ACL 配置
- 确保客户端 `station-<SN>` 有订阅权限

**3. 授权被拒绝**
```
✗ ERROR ✗ 授权请求失败
  Result: 1
```
- 遥控器用户拒绝了授权请求
- 设备不支持云端控制功能
- 设备当前状态不允许授权（如已在飞行中）

**4. 超时无回复**
```
✗ ERROR 测试超时 (30000ms)
```
- 设备可能离线
- 遥控器未响应授权请求
- MQTT 消息未正确路由
- 增加 `--timeout` 值重试

---

## 🛠️ 开发新测试

### 1. 创建单元测试

```javascript
import { TestRunner, Assert, mockBrowserEnvironment, cleanupBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[我的模块测试]');
const runner = new TestRunner('我的模块单元测试');

runner.beforeEach(() => {
  mockBrowserEnvironment(); // 模拟浏览器环境
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();
});

runner.test('应该成功执行某个功能', async () => {
  const { MyModule } = await import('../../src/lib/my-module.js');
  const instance = new MyModule();

  const result = instance.doSomething();

  Assert.equal(result, 'expected value', '结果应该匹配预期值');
});

// 运行测试
(async () => {
  const results = await runner.run(logger);
  process.exit(results.failed > 0 ? 1 : 0);
})();
```

### 2. 创建集成测试

```javascript
import mqtt from 'mqtt';
import { createLogger } from '../helpers/logger.js';

const logger = createLogger('[我的集成测试]');

async function runTest(config) {
  logger.header('我的集成测试');

  const client = mqtt.connect(`ws://${config.host}:${config.port}/mqtt`, {
    clientId: `test-${Date.now()}`
  });

  return new Promise((resolve, reject) => {
    client.on('connect', () => {
      logger.success('连接成功');
      // 执行测试逻辑
      client.end();
      resolve({ success: true });
    });

    client.on('error', (error) => {
      logger.error(`错误: ${error.message}`);
      reject(error);
    });
  });
}

(async () => {
  try {
    await runTest({ host: '192.168.31.116', port: 8083 });
    logger.success('测试通过');
    process.exit(0);
  } catch (error) {
    logger.error('测试失败');
    process.exit(1);
  }
})();
```

---

## 📊 断言工具 API

`Assert` 类提供了以下断言方法：

```javascript
import { Assert } from './helpers/mock-helpers.js';

// 相等断言
Assert.equal(actual, expected, '错误信息');
Assert.deepEqual(obj1, obj2, '深度比较对象');

// 布尔断言
Assert.true(value, '应该为 true');
Assert.false(value, '应该为 false');

// 存在性断言
Assert.notNull(value, '不应该为 null/undefined');

// 异常断言
Assert.throws(() => dangerousFunction(), '应该抛出异常');

// Promise 断言
await Assert.resolves(promise, '应该 resolve');
await Assert.rejects(promise, '应该 reject');
```

---

## 🎨 日志工具 API

彩色日志输出，便于调试：

```javascript
import { createLogger } from './helpers/logger.js';

const logger = createLogger('[我的测试]');

logger.info('普通信息');        // 蓝色
logger.success('成功消息');     // 绿色
logger.error('错误消息');       // 红色
logger.warn('警告消息');        // 黄色
logger.debug('调试信息');       // 灰色

logger.header('测试标题');      // 青色大标题
logger.section('测试章节');     // 紫色小标题

logger.result(true, '通过');   // 根据条件输出成功/失败
logger.table({ key: 'value' }); // 表格输出
```

---

## 🚦 CI/CD 集成

在 CI 环境中运行所有测试：

```bash
# 运行所有测试
pnpm test

# 仅运行单元测试
pnpm test:unit

# 仅运行集成测试（需要真实 MQTT Broker）
pnpm test:integration
```

**注意**: 集成测试需要真实的 MQTT Broker 和 DJI 设备，不适合在普通 CI 环境中运行。建议仅在开发环境或专用测试环境中执行。

---

## 📝 最佳实践

1. **单元测试优先**: 先写单元测试验证核心逻辑，再写集成测试验证完整流程
2. **隔离环境**: 单元测试使用 Mock，集成测试使用真实环境
3. **清晰命名**: 测试名称应该清楚描述测试内容（使用"应该..."格式）
4. **一个测试一个断言**: 尽量让每个测试只验证一个行为
5. **避免测试依赖**: 测试之间不应该有依赖关系，顺序不应影响结果
6. **使用彩色日志**: 便于快速定位问题
7. **记录关键步骤**: 集成测试应该记录详细的执行步骤

---

## 🔗 相关文档

- [MQTT.js 文档](https://github.com/mqttjs/MQTT.js)
- [DJI Cloud API 文档](https://developer.dji.com/doc/cloud-api-tutorial/cn/)
- [项目架构文档](../CLAUDE.md)
