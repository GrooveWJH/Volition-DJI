# 测试体系架构详解

## 📚 目录

- [快速开始 - 执行指令](#快速开始---执行指令)
- [核心设计理念](#核心设计理念)
- [三层架构](#三层架构)
- [运作机制详解](#运作机制详解)
- [核心工具库](#核心工具库)
- [执行流程](#执行流程)
- [设计原则](#设计原则)
- [架构图表](#架构图表)

---

## 快速开始 - 执行指令

### 📦 可用的 npm/pnpm 脚本

本测试体系提供了以下命令用于执行测试，所有命令都配置在 `package.json` 中：

```bash
# 1️⃣ 运行所有单元测试（推荐用于日常开发）
pnpm test
# 或者
pnpm test:unit

# 2️⃣ 运行集成测试（需要真实 MQTT 环境）
pnpm test:integration <SN> [options]
# 或使用别名
pnpm test:cloud-auth <SN> [options]

# 3️⃣ 直接运行单个测试文件（开发调试时使用）
node tests/unit/topic-template-manager.test.js
node tests/unit/message-router.test.js
node tests/integration/cloud-control-auth.test.js <SN> --host 192.168.1.100
```

### 🔍 命令详解与作用链路

#### 1️⃣ 单元测试命令

```bash
pnpm test:unit
```

**命令链路图**：

```plantuml
@startuml
!theme plain
skinparam backgroundColor #FEFEFE

actor 开发者 as dev
participant "pnpm" as pnpm
participant "package.json\nscripts" as pkg
participant "Node.js" as node
participant "topic-template-manager.test.js" as test1
participant "message-router.test.js" as test2
participant "TestRunner" as runner
participant "业务代码\nsrc/lib/services.js" as code
participant "终端输出" as output

dev -> pnpm : pnpm test:unit
activate pnpm

pnpm -> pkg : 查找 scripts.test:unit
activate pkg
note right
  "test:unit": "node tests/unit/topic-template-manager.test.js && \
                node tests/unit/message-router.test.js"
end note
pkg --> pnpm : 返回命令字符串
deactivate pkg

pnpm -> node : node tests/unit/topic-template-manager.test.js
activate node

node -> test1 : 执行测试文件
activate test1

test1 -> test1 : 导入 TestRunner、Assert、Logger
test1 -> test1 : mockBrowserEnvironment()
note right
  创建 global.window
  创建 global.localStorage
  Mock fetch API
end note

test1 -> test1 : await import('../../src/lib/services.js')
test1 -> code : 动态导入业务代码
activate code
code --> test1 : { TopicTemplateManager }
deactivate code

test1 -> runner : runner.run(logger)
activate runner

loop 9 个测试用例
  runner -> test1 : 执行测试函数
  test1 -> code : new TopicTemplateManager()
  test1 -> code : manager.buildServiceMessage(...)
  code --> test1 : 返回结果
  test1 -> test1 : Assert.equal(actual, expected)

  alt 断言通过
    runner -> output : [+120ms] [✓ SUCCESS] PASS: 测试名
    output --> dev : 绿色成功日志
  else 断言失败
    runner -> output : [+120ms] [✗ ERROR] FAIL: 测试名
    output --> dev : 红色失败日志
  end
end

runner --> test1 : { passed: 9, failed: 0 }
deactivate runner

test1 -> output : 总计: 9 个测试\n通过: 9
output --> dev : 蓝色统计信息

test1 --> node : process.exit(0)
deactivate test1
deactivate node

pnpm -> node : node tests/unit/message-router.test.js
activate node
note right
  同样的流程执行
  message-router.test.js
  (14 个测试用例)
end note
node --> pnpm : 退出码 0
deactivate node

pnpm --> dev : ✓ 所有测试通过
deactivate pnpm

@enduml
```

**作用链路说明**：


| 步骤 | 组件                         | 作用                                       | 输出                      |
| ---- | ---------------------------- | ------------------------------------------ | ------------------------- |
| 1    | `pnpm`                       | 解析 package.json 的`scripts.test:unit`    | 找到要执行的 Node.js 命令 |
| 2    | `Node.js`                    | 执行测试文件                               | 启动 JavaScript 运行环境  |
| 3    | `测试文件`                   | 导入工具库（TestRunner、Assert、Logger）   | 加载测试基础设施          |
| 4    | `mockBrowserEnvironment()`   | 创建`global.window`、`global.localStorage` | 模拟浏览器环境            |
| 5    | `await import()`             | 动态导入业务代码                           | 让业务代码看到 Mock 环境  |
| 6    | `new TopicTemplateManager()` | 实例化真实的业务类                         | 创建待测对象              |
| 7    | `TestRunner.run()`           | 执行所有测试用例                           | 循环运行每个 test()       |
| 8    | `Assert.equal()`             | 验证结果是否符合预期                       | 通过/失败（抛异常）       |
| 9    | `Logger.success/error()`     | 彩色输出测试结果                           | 终端显示绿色/红色日志     |
| 10   | `process.exit()`             | 返回退出码（0=成功，1=失败）               | 通知 CI/CD 测试状态       |

**示例输出**：

```bash
$ pnpm test:unit

> ground-station-web@0.0.3 test:unit
> node tests/unit/topic-template-manager.test.js && node tests/unit/message-router.test.js

============================================================
  测试套件: TopicTemplateManager 单元测试
============================================================

▶ 测试: 应该成功加载模板配置
[+108ms] [✓ SUCCESS] PASS: 应该成功加载模板配置

▶ 测试: 应该正确构建服务主题
[+209ms] [✓ SUCCESS] PASS: 应该正确构建服务主题

... (共 9 个测试)

============================================================
  测试结果
============================================================

[+821ms] [INFO] 总计: 9 个测试
[+821ms] [✓ SUCCESS] 通过: 9

============================================================
  测试套件: MessageRouter 单元测试
============================================================

... (共 14 个测试)

[+14ms] [INFO] 总计: 14 个测试
[+14ms] [✓ SUCCESS] 通过: 14
```

---

#### 2️⃣ 集成测试命令

```bash
pnpm test:cloud-auth 9N9CN2J0012CXY --host 192.168.31.116 --port 8083
```

**命令链路图**：

```plantuml
@startuml
!theme plain
skinparam backgroundColor #FEFEFE

actor 开发者 as dev
participant "pnpm" as pnpm
participant "cloud-control-auth.test.js" as test
participant "parseArgs()" as parse
participant "mqtt.connect()" as mqtt
participant "MQTT Broker\n192.168.31.116:8083" as broker
participant "DJI 设备\n9N9CN2J0012CXY" as device
participant "Logger" as logger
participant "终端输出" as output

dev -> pnpm : pnpm test:cloud-auth 9N9CN2J0012CXY \\\n  --host 192.168.31.116 --port 8083
activate pnpm

pnpm -> test : node tests/integration/cloud-control-auth.test.js \\\n  9N9CN2J0012CXY --host 192.168.31.116 --port 8083
activate test

test -> parse : parseArgs(process.argv)
activate parse
note right
  解析命令行参数:
  {
    sn: '9N9CN2J0012CXY',
    host: '192.168.31.116',
    port: 8083,
    userId: 'test_user_001',
    userCallsign: 'TestStation'
  }
end note
parse --> test : config 对象
deactivate parse

test -> logger : logger.info('正在连接 MQTT...')
logger -> output : [+0ms] [INFO] 正在连接 MQTT...
output --> dev : 蓝色日志

test -> mqtt : mqtt.connect('ws://192.168.31.116:8083/mqtt', {...})
activate mqtt

mqtt -> broker : WebSocket 连接请求
activate broker
broker --> mqtt : 连接成功 (CONNACK)
mqtt -> test : client.on('connect', ...)

test -> logger : logger.success('MQTT 连接成功')
logger -> output : [+120ms] [✓ SUCCESS] MQTT 连接成功
output --> dev : 绿色日志

test -> mqtt : client.subscribe('thing/product/9N9CN2J0012CXY/services_reply')
mqtt -> broker : SUBSCRIBE
broker --> mqtt : SUBACK
mqtt -> test : 订阅成功

test -> logger : logger.success('订阅成功: services_reply')
logger -> output : [+245ms] [✓ SUCCESS] 订阅成功
output --> dev : 绿色日志

test -> test : buildAuthRequestMessage(config)
note right
  构建 DJI 协议消息:
  {
    method: 'cloud_control_auth_request',
    data: {
      user_id: 'test_user_001',
      user_callsign: 'TestStation',
      control_keys: ['flight']
    },
    tid: 'tid_1704038400123_a1b2c3d4',
    bid: 'bid_1704038400123_e5f6g7h8',
    timestamp: 1704038400123
  }
end note

test -> mqtt : client.publish(\n  'thing/product/9N9CN2J0012CXY/services',\n  JSON.stringify(message)\n)
mqtt -> broker : PUBLISH
broker -> device : 转发授权请求消息
activate device

test -> logger : logger.success('消息已发送')
logger -> output : [+267ms] [✓ SUCCESS] 消息已发送\n[+269ms] [INFO] 等待回复...
output --> dev : 绿色 + 蓝色日志

note right of device
  DJI 设备处理:
  1. 收到授权请求
  2. 遥控器弹窗显示
  3. 用户点击"批准"
  4. 构建回复消息
end note

device -> broker : 回复消息 {\n  method: 'cloud_control_auth_request',\n  tid: 'tid_1704038400123_a1b2c3d4',\n  data: { result: 0, output: { status: 'ok' } }\n}
deactivate device

broker -> mqtt : PUBLISH (回复主题)
mqtt -> test : client.on('message', (topic, message) => {...})

test -> test : JSON.parse(message.toString())
test -> test : 验证 TID 是否匹配
note right
  if (reply.tid !== requestMessage.tid) {
    return; // 忽略不匹配的回复
  }
end note

test -> logger : logger.success('TID 匹配')
logger -> output : [+5123ms] [✓ SUCCESS] TID 匹配
output --> dev : 绿色日志

test -> test : 检查 result 和 status
note right
  const result = reply.data?.result;
  const status = reply.data?.output?.status;

  if (result === 0 && status === 'ok') {
    授权成功
  }
end note

test -> logger : logger.success('✓ 授权请求成功')
logger -> output : [+5423ms] [✓ SUCCESS] ✓ 授权请求成功\n🎉 云端控制授权已获批准！
output --> dev : 绿色日志 + 成功消息

test -> mqtt : client.end()
mqtt -> broker : DISCONNECT
deactivate broker
deactivate mqtt

test -> pnpm : process.exit(0)
deactivate test

pnpm --> dev : ✓ 测试通过
deactivate pnpm

@enduml
```

**作用链路说明**：


| 步骤 | 组件                        | 作用                                    | 输出               |
| ---- | --------------------------- | --------------------------------------- | ------------------ |
| 1    | `parseArgs()`               | 解析命令行参数（SN、host、port 等）     | 配置对象           |
| 2    | `mqtt.connect()`            | 创建真实 MQTT WebSocket 连接            | MQTT 客户端实例    |
| 3    | `client.on('connect')`      | 监听连接成功事件                        | 触发订阅和发送流程 |
| 4    | `client.subscribe()`        | 订阅设备回复主题                        | 准备接收回复       |
| 5    | `buildAuthRequestMessage()` | 构建 DJI 协议消息（包含 TID、BID）      | JSON 消息对象      |
| 6    | `client.publish()`          | 发送授权请求到设备服务主题              | MQTT PUBLISH 报文  |
| 7    | `DJI 设备`                  | 处理授权请求，用户批准/拒绝             | 构建回复消息       |
| 8    | `client.on('message')`      | 接收回复消息                            | 解析 JSON          |
| 9    | `验证 TID`                  | 检查回复的 TID 是否匹配请求             | 确保消息对应关系   |
| 10   | `检查 result`               | 验证`result === 0` 且 `status === 'ok'` | 判断授权是否成功   |
| 11   | `Logger`                    | 输出彩色日志                            | 终端显示测试过程   |
| 12   | `process.exit()`            | 返回退出码                              | 0=成功，1=失败     |

**命令行参数说明**：

```bash
node tests/integration/cloud-control-auth.test.js <SN> [options]

必需参数:
  <SN>                设备序列号（14位大写字母+数字，如 9N9CN2J0012CXY）

可选参数:
  --host <host>       MQTT Broker 主机地址（默认: 192.168.31.116）
  --port <port>       MQTT Broker WebSocket 端口（默认: 8083）
  --user-id <id>      用户 ID（默认: test_user_001）
  --callsign <name>   用户呼号（默认: TestStation）
  --timeout <ms>      超时时间（默认: 30000ms）

示例:
  # 使用默认配置
  pnpm test:cloud-auth 9N9CN2J0012CXY

  # 指定 MQTT Broker
  pnpm test:cloud-auth 9N9CN2J0012CXY --host 192.168.1.100 --port 8083

  # 完整配置
  pnpm test:cloud-auth 9N9CN2J0012CXY \
    --host 192.168.31.116 \
    --port 8083 \
    --user-id pilot_123 \
    --callsign "MyStation" \
    --timeout 60000
```

**示例输出**：

```bash
$ pnpm test:cloud-auth 9N9CN2J0012CXY --host 192.168.31.116

============================================================
  云端控制授权集成测试
============================================================

[+0ms] [INFO] 测试配置:
  设备 SN: 9N9CN2J0012CXY
  MQTT Broker: ws://192.168.31.116:8083/mqtt
  用户 ID: test_user_001
  用户呼号: TestStation

[+120ms] [✓ SUCCESS] MQTT 连接成功
[+245ms] [✓ SUCCESS] 订阅成功: thing/product/9N9CN2J0012CXY/services_reply
[+267ms] [✓ SUCCESS] 消息已发送
[+269ms] [INFO] 等待设备回复...

[+5123ms] [✓ SUCCESS] 收到回复消息
[+5125ms] [✓ SUCCESS] TID 匹配: tid_1704038400123_a1b2c3d4
[+5423ms] [✓ SUCCESS] ✓ 授权请求成功

============================================================
  测试结果
============================================================

🎉 云端控制授权已获批准！
📊 总耗时: 5.4 秒
```

---

#### 3️⃣ 直接运行测试文件

```bash
node tests/unit/topic-template-manager.test.js
```

**与 `pnpm test:unit` 的区别**：


| 方面         | `pnpm test:unit`            | `node tests/unit/...`  |
| ------------ | --------------------------- | ---------------------- |
| **执行范围** | 运行所有单元测试（2个文件） | 运行单个测试文件       |
| **使用场景** | 日常完整测试、CI/CD         | 开发调试、修复单个模块 |
| **退出码**   | 任一测试失败则返回 1        | 仅当前文件失败返回 1   |
| **速度**     | 较慢（运行所有测试）        | 较快（只运行一个）     |

**作用链路**：

```plantuml
@startuml
!theme plain

start

:开发者执行;
note right
  node tests/unit/topic-template-manager.test.js
end note

:Node.js 直接执行测试文件;

:导入 TestRunner、Assert、Logger;

:mockBrowserEnvironment();

:动态导入业务代码;
note right
  await import('../../src/lib/services.js')
end note

:运行 9 个测试用例;

if (所有测试通过?) then (yes)
  :输出绿色成功日志;
  :process.exit(0);
else (no)
  :输出红色失败日志;
  :process.exit(1);
endif

stop

@enduml
```

---

### 🎯 命令选择指南

根据不同场景选择合适的命令：

```plantuml
@startuml
!theme plain

skinparam activity {
  BackgroundColor #E8F5E9
  BorderColor #4CAF50
  FontSize 13
}

start

if (你想做什么?) then (日常开发 - 验证所有单元测试)
  :pnpm test;
  note right
    运行所有单元测试
    快速验证核心逻辑
  end note

elseif (调试单个模块) then (yes)
  :node tests/unit/xxx.test.js;
  note right
    只运行一个测试文件
    快速迭代修复
  end note

elseif (测试真实设备通信) then (yes)
  :pnpm test:cloud-auth <SN> --host xxx;
  note right
    端到端集成测试
    需要真实 MQTT 环境
  end note

elseif (CI/CD 自动化测试) then (yes)
  :pnpm test && pnpm test:integration;
  note right
    先运行单元测试
    再运行集成测试
    失败则中断
  end note
endif

stop

@enduml
```


| 场景             | 推荐命令                      | 理由                        |
| ---------------- | ----------------------------- | --------------------------- |
| **日常开发**     | `pnpm test`                   | 快速验证所有核心逻辑        |
| **调试单个模块** | `node tests/unit/xxx.test.js` | 只运行当前文件，速度快      |
| **端到端测试**   | `pnpm test:cloud-auth <SN>`   | 验证完整业务流程            |
| **CI/CD 自动化** | `pnpm test`                   | 失败时退出码非 0，CI 会捕获 |
| **提交前验证**   | `pnpm test`                   | 确保没有破坏现有功能        |

---

## 核心设计理念

这个测试体系采用了 **"自包含 + 业务代码复用"** 的混合架构：

```
测试体系 = 自有基础设施（helpers/fixtures） + 导入业务代码（src/lib/*）
```

### 设计目标

1. ✅ **零测试框架依赖** - 不依赖 Jest/Mocha/Chai
2. ✅ **业务代码复用** - 测试真实代码，而非 Mock 实现
3. ✅ **环境适配灵活** - 单元测试 Mock 环境，集成测试真实环境
4. ✅ **调试友好** - 彩色日志 + 透明代码
5. ✅ **易于扩展** - 清晰的工具库 API

---

## 三层架构

```plantuml
@startuml
!define RECTANGLE class

package "测试体系三层架构" {

  RECTANGLE "Layer 3: 测试文件" as L3 {
    + unit/topic-template-manager.test.js
    + unit/message-router.test.js
    + integration/cloud-control-auth.test.js
    --
    编写测试用例
    调用 helpers 和业务代码
  }

  RECTANGLE "Layer 2: 测试工具库" as L2 {
    + helpers/logger.js (彩色日志)
    + helpers/mock-helpers.js
    --
    - TestRunner (测试运行器)
    - Assert (断言工具)
    - MockLocalStorage
    - MockMQTTClient
    - mockBrowserEnvironment()
  }

  RECTANGLE "Layer 1: 业务代码" as L1 {
    + src/lib/services.js
    + src/lib/mqtt.js
    + src/lib/state.js
    --
    TopicTemplateManager
    MessageRouter
    TopicServiceManager
    MQTTConnectionManager
  }

  L3 --> L2 : 使用
  L3 --> L1 : 动态导入
  L2 ..> L1 : Mock 环境支持
}

note right of L3
  测试文件直接导入业务代码
  使用 helpers 提供的工具
  不需要安装测试框架
end note

note right of L2
  自包含的测试基础设施
  提供 Mock、断言、日志
  完全透明，易于调试
end note

note right of L1
  真实的业务逻辑代码
  测试验证的是实际运行的代码
  发现的 bug 就是业务 bug
end note

@enduml
```

### 目录结构

```
tests/
├── unit/                                    # 🧪 单元测试
│   ├── topic-template-manager.test.js      # 10个测试用例
│   └── message-router.test.js               # 14个测试用例
├── integration/                             # 🚀 集成测试
│   └── cloud-control-auth.test.js           # 端到端流程测试
├── helpers/                                 # 🛠️ 测试工具库
│   ├── logger.js                            # 彩色日志输出
│   └── mock-helpers.js                      # Mock + 断言 + 运行器
├── fixtures/                                # 📦 测试数据
│   └── topic-templates.json                 # 服务模板配置
├── README.md                                # 📖 使用文档
├── TEST-SUMMARY.md                          # 📋 测试总结
└── ARCHITECTURE.md                          # 📐 本文档
```

---

## 运作机制详解

### 1️⃣ 单元测试运作流程

#### 代码示例

```javascript
// ============ 步骤1: 导入测试工具 ============
import { TestRunner, Assert, mockBrowserEnvironment } from '../helpers/mock-helpers.js';
import { createLogger } from '../helpers/logger.js';

// ============ 步骤2: 创建测试运行器实例 ============
const logger = createLogger('[TopicTemplateManager单元测试]');
const runner = new TestRunner('TopicTemplateManager 单元测试');

// ============ 步骤3: 设置测试环境 ============
runner.beforeEach(() => {
  // 🔑 关键：模拟浏览器环境
  mockBrowserEnvironment();  // 创建 global.window, global.localStorage

  // 🔑 Mock fetch API（业务代码需要）
  global.fetch = async () => ({
    ok: true,
    json: async () => mockTemplates  // 返回测试数据
  });
});

runner.afterEach(() => {
  cleanupBrowserEnvironment();  // 清理环境，避免污染
  delete global.fetch;
});

// ============ 步骤4: 编写测试用例 ============
runner.test('应该成功加载模板配置', async () => {
  // 🔑 动态导入业务代码（因为需要先 mock 环境）
  const { TopicTemplateManager } = await import('../../src/lib/services.js');

  // 实例化真实的业务类
  const manager = new TopicTemplateManager();
  await manager.waitForLoad();

  // 使用断言验证行为
  Assert.true(manager.loaded, '模板应该加载完成');
});

// ============ 步骤5: 运行测试 ============
(async () => {
  const results = await runner.run(logger);  // 执行所有测试
  process.exit(results.failed > 0 ? 1 : 0);  // 返回退出码
})();
```

#### 流程图

```plantuml
@startuml
!theme plain
skinparam backgroundColor #FEFEFE
skinparam sequenceArrowThickness 2
skinparam roundcorner 10

actor Developer as dev
participant "topic-template-manager.test.js" as test
participant "TestRunner" as runner
participant "mockBrowserEnvironment()" as mock
participant "业务代码\nsrc/lib/services.js" as business
participant "TopicTemplateManager" as manager
participant "Assert" as assert
participant "Logger" as logger

dev -> test : node xxx.test.js
activate test

test -> runner : new TestRunner()
test -> logger : createLogger()

test -> runner : beforeEach(() => {...})
note right
  注册前置钩子
  每个测试前执行
end note

test -> runner : test('测试名', async () => {...})
note right
  注册测试用例
  定义测试逻辑
end note

test -> runner : run(logger)
activate runner

loop 每个测试用例
  runner -> mock : mockBrowserEnvironment()
  activate mock
  mock -> mock : 创建 global.window
  mock -> mock : 创建 global.localStorage
  mock -> mock : Mock DOM API
  mock --> runner : 环境就绪
  deactivate mock

  runner -> test : 执行测试函数
  activate test

  test -> business : await import('../../src/lib/services.js')
  activate business
  note right
    动态导入
    此时看到的是 Mock 环境
  end note
  business --> test : { TopicTemplateManager }
  deactivate business

  test -> manager : new TopicTemplateManager()
  activate manager
  note right
    真实的业务类实例
    使用 Mock 的 fetch
  end note
  manager -> manager : _loadTemplates()
  manager --> test : manager 实例
  deactivate manager

  test -> manager : manager.buildServiceMessage(...)
  activate manager
  manager --> test : 消息对象
  deactivate manager

  test -> assert : Assert.equal(actual, expected)
  activate assert
  alt 断言通过
    assert --> test : ✓ 通过
  else 断言失败
    assert --> test : ✗ 失败 (抛出异常)
  end
  deactivate assert

  deactivate test

  runner -> mock : cleanupBrowserEnvironment()
  activate mock
  mock -> mock : delete global.window
  mock -> mock : delete global.localStorage
  mock --> runner : 清理完成
  deactivate mock

  runner -> logger : logger.success('PASS: ...')
  logger --> dev : 🟢 彩色输出
end

runner --> test : { passed, failed, failures }
deactivate runner

test -> dev : process.exit(failed > 0 ? 1 : 0)
deactivate test

@enduml
```

#### 关键机制


| 机制                | 说明                               | 原因                                 |
| ------------------- | ---------------------------------- | ------------------------------------ |
| **动态 Import**     | `await import()` 而非顶部 `import` | 需要先 Mock 环境再导入代码           |
| **Mock 浏览器环境** | `mockBrowserEnvironment()`         | 业务代码依赖`window`、`localStorage` |
| **测试隔离**        | `beforeEach/afterEach`             | 确保每个测试独立，互不干扰           |
| **真实业务逻辑**    | 导入真实的`TopicTemplateManager`   | 测试的是生产代码，不是假实现         |

---

### 2️⃣ 集成测试运作流程

#### 代码示例

```javascript
#!/usr/bin/env node
// ============ 步骤1: 导入依赖 ============
import mqtt from 'mqtt';  // 🔑 真实的 MQTT 库（不是 Mock）
import { createLogger } from '../helpers/logger.js';  // 只用工具库

// ============ 步骤2: 解析命令行参数 ============
const config = parseArgs(process.argv);
// 例如：node xxx.test.js 9N9CN2J0012CXY --host 192.168.1.100

// ============ 步骤3: 验证参数 ============
if (!/^[A-Z0-9]{14}$/.test(config.sn)) {
  logger.error('无效的设备序列号');
  process.exit(1);
}

// ============ 步骤4: 创建真实 MQTT 客户端 ============
const client = mqtt.connect(`ws://${config.host}:${config.port}/mqtt`, {
  clientId: `station-${config.sn}`,  // 🔑 使用业务代码的命名规则
  keepalive: 60,
  clean: true
});

// ============ 步骤5: 构建消息（复用业务逻辑） ============
function buildAuthRequestMessage(config) {
  return {
    method: 'cloud_control_auth_request',  // 🔑 与 topic-templates.json 一致
    data: {
      user_id: config.userId,
      user_callsign: config.userCallsign,
      control_keys: ['flight']
    },
    tid: generateTid(),  // 🔑 复用业务代码的 TID 生成逻辑
    bid: generateBid(),
    timestamp: Date.now()
  };
}

// ============ 步骤6: 完整 MQTT 流程 ============
client.on('connect', () => {
  logger.success('MQTT 连接成功');

  // 订阅回复主题
  client.subscribe(`thing/product/${config.sn}/services_reply`, (err) => {
    // 发送授权请求
    const message = buildAuthRequestMessage(config);
    client.publish(`thing/product/${config.sn}/services`, JSON.stringify(message));
  });
});

// 处理回复
client.on('message', (topic, message) => {
  const reply = JSON.parse(message.toString());

  // 🔑 验证 TID 匹配（与业务代码逻辑一致）
  if (reply.tid !== requestMessage.tid) return;

  // 🔑 检查结果（与 TopicServiceManager 逻辑一致）
  if (reply.data?.result === 0 && reply.data?.output?.status === 'ok') {
    logger.success('✓ 授权请求成功');
    client.end();
  }
});
```

#### 流程图

```plantuml
@startuml
!theme plain
skinparam backgroundColor #FEFEFE
skinparam sequenceArrowThickness 2
skinparam roundcorner 10

actor Developer as dev
participant "cloud-control-auth.test.js" as test
participant "parseArgs()" as parser
participant "mqtt.connect()" as mqtt
participant "MQTT Broker" as broker
participant "DJI 设备" as device
participant "Logger" as logger

dev -> test : node xxx.test.js 9N9CN2J0012CXY\n--host 192.168.31.116
activate test

test -> parser : parseArgs(process.argv)
activate parser
parser -> parser : 解析命令行参数
parser --> test : config = {\n  sn: '9N9CN2J0012CXY',\n  host: '192.168.31.116',\n  port: 8083\n}
deactivate parser

test -> test : validateConfig(config)
note right
  验证 SN 格式
  检查必需参数
end note

test -> mqtt : mqtt.connect(\n  'ws://192.168.31.116:8083/mqtt',\n  { clientId: 'station-9N9CN2J0012CXY' }\n)
activate mqtt
mqtt -> broker : WebSocket 连接请求
activate broker
broker --> mqtt : 连接成功
mqtt -> test : client 实例
deactivate mqtt

mqtt -> logger : logger.success('MQTT 连接成功')
logger --> dev : 🟢 [+120ms] [✓ SUCCESS] MQTT 连接成功

test -> mqtt : client.subscribe(\n  'thing/product/9N9CN2J0012CXY/services_reply'\n)
activate mqtt
mqtt -> broker : SUBSCRIBE
broker --> mqtt : SUBACK
mqtt --> test : 订阅成功
deactivate mqtt

mqtt -> logger : logger.success('订阅成功: ...')
logger --> dev : 🟢 [+245ms] [✓ SUCCESS] 订阅成功

test -> test : buildAuthRequestMessage(config)
activate test
note right
  构建 DJI 协议消息:
  {
    method: 'cloud_control_auth_request',
    data: {
      user_id: 'test_user_001',
      user_callsign: 'TestStation',
      control_keys: ['flight']
    },
    tid: 'tid_1704038400123_a1b2c3d4',
    bid: 'bid_1704038400123_e5f6g7h8',
    timestamp: 1704038400123
  }
end note
test --> test : message
deactivate test

test -> mqtt : client.publish(\n  'thing/product/9N9CN2J0012CXY/services',\n  JSON.stringify(message)\n)
activate mqtt
mqtt -> broker : PUBLISH
broker -> device : 转发消息
activate device
mqtt --> test : 发送成功
deactivate mqtt

mqtt -> logger : logger.success('消息已发送')
logger --> dev : 🟢 [+267ms] [✓ SUCCESS] 消息已发送\n🔵 [+269ms] [INFO] 等待回复...

note right of device
  DJI 设备处理:
  1. 收到授权请求
  2. 遥控器显示弹窗
  3. 用户批准/拒绝
  4. 构建回复消息
end note

device -> broker : 回复消息 {\n  method: 'cloud_control_auth_request',\n  data: { result: 0, output: { status: 'ok' } },\n  tid: 'tid_1704038400123_a1b2c3d4'\n}
deactivate device

broker -> mqtt : PUBLISH (回复主题)
activate mqtt

mqtt -> test : client.on('message', (topic, message) => {...})
activate test

test -> test : JSON.parse(message.toString())
test -> test : 验证 TID 匹配
note right
  if (reply.tid !== requestMessage.tid)
    return; // 忽略不匹配的消息
end note

test -> test : 检查结果
note right
  if (result === 0 && status === 'ok')
    授权成功
  else
    授权失败
end note

test -> logger : logger.success('✓ 授权请求成功')
logger --> dev : 🟢 [+5423ms] [✓ SUCCESS] ✓ 授权请求成功\n🎉 云端控制授权已获批准！

test -> mqtt : client.end()
deactivate mqtt
deactivate test

test -> dev : process.exit(0)
deactivate test
deactivate broker

@enduml
```

#### 关键机制


| 机制             | 说明                        | 原因                       |
| ---------------- | --------------------------- | -------------------------- |
| **无 Mock**      | 使用真实的 MQTT 库          | 验证完整的网络通信流程     |
| **独立脚本**     | 不依赖浏览器环境            | 可以直接`node xxx.js` 运行 |
| **复用协议逻辑** | 消息格式与业务代码一致      | 测试的是真实的 DJI 协议    |
| **命令行参数**   | 通过`process.argv` 接收配置 | 灵活测试不同设备和环境     |

---

## 核心工具库

### helpers/logger.js - 彩色日志系统

#### 类图

```plantuml
@startuml
class TestLogger {
  - prefix: string
  - startTime: number
  - colors: object

  + constructor(prefix: string)
  - _timestamp(): string
  - _format(level, color, message, ...args)
  + info(message, ...args)
  + success(message, ...args)
  + error(message, ...args)
  + warn(message, ...args)
  + debug(message, ...args)
  + header(message)
  + section(message)
  + result(passed, message)
  + table(data)
}

note right of TestLogger::_timestamp
  计算相对时间
  返回 "[+120ms]" 格式
end note

note right of TestLogger::_format
  统一日志格式:
  [+120ms] [TEST] [✓ SUCCESS] message

  颜色映射:
  - info: 蓝色
  - success: 绿色
  - error: 红色
  - warn: 黄色
  - debug: 灰色
end note

@enduml
```

#### 实现原理

```javascript
class TestLogger {
  constructor(prefix) {
    this.prefix = prefix;
    this.startTime = Date.now();  // 🔑 记录开始时间
  }

  _timestamp() {
    const elapsed = Date.now() - this.startTime;
    return `${colors.gray}[+${elapsed}ms]${colors.reset}`;  // 🔑 显示相对时间
  }

  success(message, ...args) {
    const timestamp = this._timestamp();
    const prefix = `${colors.green}${this.prefix} [✓ SUCCESS]${colors.reset}`;
    console.log(`${timestamp} ${prefix}`, message, ...args);
  }
}
```

#### 为什么需要自己的日志系统？


| 特性         | console.log      | TestLogger                 |
| ------------ | ---------------- | -------------------------- |
| **颜色**     | ❌ 无            | ✅ 根据级别自动着色        |
| **时间戳**   | ❌ 无            | ✅ 显示相对时间（+120ms）  |
| **统一格式** | ❌ 自由格式      | ✅ 统一的前缀和级别标识    |
| **层级标题** | ❌ 无            | ✅ header/section 层级显示 |
| **表格输出** | ✅ console.table | ✅ 封装 console.table      |

---

### helpers/mock-helpers.js - Mock 工具集

#### 类图

```plantuml
@startuml
package "mock-helpers.js" {

  class MockLocalStorage {
    - store: Map
    + getItem(key): string | null
    + setItem(key, value)
    + removeItem(key)
    + clear()
    + length: number
    + key(index): string | null
  }

  class MockMQTTClient {
    - isConnected: boolean
    - subscriptions: Set
    - publishedMessages: Array
    - messageHandlers: Array

    + connect(): Promise<boolean>
    + disconnect()
    + subscribe(topic, callback)
    + publish(topic, message): Promise<boolean>
    + simulateMessage(topic, message)
    + getPublishedMessages(): Array
    + getLastPublishedMessage(): object
    + clearPublishedMessages()
  }

  class Assert {
    {static} + equal(actual, expected, message)
    {static} + deepEqual(actual, expected, message)
    {static} + true(value, message)
    {static} + false(value, message)
    {static} + notNull(value, message)
    {static} + throws(fn, message)
    {static} + resolves(promise, message)
    {static} + rejects(promise, message)
  }

  class TestRunner {
    - suiteName: string
    - tests: Array
    - beforeEachFn: function
    - afterEachFn: function

    + beforeEach(fn)
    + afterEach(fn)
    + test(name, fn)
    + run(logger): Promise<{passed, failed, failures}>
  }

  note right of MockLocalStorage
    模拟浏览器 localStorage
    使用 Map 实现存储
    API 完全兼容原生
  end note

  note right of MockMQTTClient
    模拟 MQTT 客户端
    记录所有发布的消息
    支持模拟接收消息
  end note

  note right of Assert
    断言工具
    失败时抛出异常
    TestRunner 会捕获
  end note

  note right of TestRunner
    测试运行器
    管理测试生命周期
    收集测试结果
  end note
}

TestRunner --> Assert : 捕获异常
TestRunner --> MockLocalStorage : 可选使用
TestRunner --> MockMQTTClient : 可选使用

@enduml
```

#### MockLocalStorage 实现

```javascript
export class MockLocalStorage {
  constructor() {
    this.store = new Map();  // 🔑 用 Map 模拟存储
  }

  getItem(key) {
    return this.store.get(key) || null;
  }

  setItem(key, value) {
    this.store.set(key, String(value));  // 🔑 转为字符串（与原生一致）
  }

  removeItem(key) {
    this.store.delete(key);
  }

  clear() {
    this.store.clear();
  }

  get length() {
    return this.store.size;
  }

  key(index) {
    return Array.from(this.store.keys())[index] || null;
  }
}
```

**为什么需要？**

业务代码使用了 `localStorage`，但 Node.js 环境没有：

```javascript
// src/lib/state.js (业务代码)
if (typeof window !== 'undefined') {
  localStorage.setItem('device_aliases', JSON.stringify(data));  // ❌ Node.js 报错
}
```

Mock 后可以正常运行：

```javascript
// 单元测试
mockBrowserEnvironment();  // 创建 global.localStorage
const { DeviceStateManager } = await import('../../src/lib/state.js');
// ✅ 业务代码现在可以正常运行了
```

---

#### mockBrowserEnvironment() 实现

```javascript
export function mockBrowserEnvironment() {
  global.window = {
    localStorage: new MockLocalStorage(),
    sessionStorage: new MockLocalStorage(),
    addEventListener: () => {},  // 🔑 Mock DOM API
    removeEventListener: () => {},
    dispatchEvent: () => {},
    CustomEvent: class CustomEvent {},
    mqttManager: null,  // 🔑 业务代码会设置这个
    deviceContext: null,
    deviceStateManager: null,
    cardStateManager: null
  };

  // 🔑 兼容直接访问 localStorage（不通过 window）
  global.localStorage = global.window.localStorage;
  global.sessionStorage = global.window.sessionStorage;
}
```

**创建了什么？**


| 对象                      | 用途           | 业务代码示例                                       |
| ------------------------- | -------------- | -------------------------------------------------- |
| `global.window`           | 检查浏览器环境 | `if (typeof window !== 'undefined')`               |
| `global.localStorage`     | 本地存储       | `localStorage.getItem('key')`                      |
| `global.addEventListener` | 事件监听       | `window.addEventListener('device-changed', ...)`   |
| `global.mqttManager`      | MQTT 管理器    | `window.mqttManager = new MQTTConnectionManager()` |

---

#### TestRunner 实现

```javascript
export class TestRunner {
  constructor(suiteName) {
    this.suiteName = suiteName;
    this.tests = [];  // 存储所有测试
    this.beforeEachFn = null;
    this.afterEachFn = null;
  }

  beforeEach(fn) {
    this.beforeEachFn = fn;  // 🔑 注册前置钩子
  }

  afterEach(fn) {
    this.afterEachFn = fn;  // 🔑 注册后置钩子
  }

  test(name, fn) {
    this.tests.push({ name, fn });  // 🔑 注册测试用例
  }

  async run(logger) {
    logger.header(`测试套件: ${this.suiteName}`);

    let passed = 0;
    let failed = 0;
    const failures = [];

    for (const { name, fn } of this.tests) {
      logger.section(`测试: ${name}`);

      try {
        // 🔑 执行测试生命周期
        if (this.beforeEachFn) await this.beforeEachFn();  // 前置
        await fn();  // 执行测试
        if (this.afterEachFn) await this.afterEachFn();  // 后置

        logger.success(`PASS: ${name}`);
        passed++;
      } catch (error) {
        logger.error(`FAIL: ${name}`);
        logger.error(`  ${error.message}`);
        failed++;
        failures.push({ name, error });
      }
    }

    logger.header('测试结果');
    logger.info(`总计: ${this.tests.length} 个测试`);
    logger.success(`通过: ${passed}`);
    if (failed > 0) {
      logger.error(`失败: ${failed}`);
    }

    return { total: this.tests.length, passed, failed, failures };
  }
}
```

**为什么不用 Jest/Mocha？**


| 方面         | Jest/Mocha       | TestRunner           |
| ------------ | ---------------- | -------------------- |
| **依赖**     | 需要安装大量依赖 | ✅ 零依赖，200行代码 |
| **配置**     | 需要配置文件     | ✅ 无需配置          |
| **学习曲线** | 需要学习框架 API | ✅ 纯 JS，易懂       |
| **调试**     | 框架黑盒         | ✅ 代码透明          |
| **定制**     | 受框架限制       | ✅ 完全自由          |
| **日志**     | 固定格式         | ✅ 自定义颜色和格式  |

---

## 执行流程

### 单元测试完整执行流程

```plantuml
@startuml
!theme plain
skinparam backgroundColor #FEFEFE

start

:开发者执行命令;
note right
  node tests/unit/topic-template-manager.test.js
end note

:Node.js 启动，执行测试文件;

:导入 mock-helpers.js, logger.js;
note right
  纯 JS 工具，无外部依赖
end note

:创建 TestRunner 和 Logger 实例;

:注册 beforeEach: mockBrowserEnvironment();
note right
  runner.beforeEach(() => {
    mockBrowserEnvironment();
    global.fetch = async () => ({...});
  });
end note

:注册测试用例;
note right
  runner.test('测试名', async () => {
    // 测试逻辑
  });
end note

:执行 runner.run(logger);

partition "循环执行每个测试" {
  :运行 beforeEach();

  :创建 global.window;
  :创建 global.localStorage;
  :Mock global.fetch;

  note right
    此时 Node.js 环境已模拟为浏览器环境
  end note

  :动态导入业务代码;
  note right
    await import('../../src/lib/services.js')
    此时业务代码看到的是 Mock 环境
  end note

  :实例化业务类;
  note right
    const manager = new TopicTemplateManager();
    这是真实的业务类，不是 Mock
  end note

  :调用业务方法;
  note right
    const result = manager.buildServiceMessage(...);
  end note

  :使用 Assert 验证结果;
  note right
    Assert.equal(result.method, 'cloud_control_auth_request');
  end note

  if (断言通过?) then (yes)
    :passed++;
    :logger.success('PASS: ...');
  else (no)
    :failed++;
    :logger.error('FAIL: ...');
  endif

  :运行 afterEach();

  :delete global.window;
  :delete global.localStorage;
  :delete global.fetch;

  note right
    清理环境，避免污染下一个测试
  end note
}

:输出测试报告;
note right
  ============================================================
    测试套件: TopicTemplateManager 单元测试
  ============================================================

  ▶ 测试: 应该成功加载模板配置
  [+120ms] [✓ SUCCESS] PASS: 应该成功加载模板配置

  ▶ 测试: 应该正确构建服务主题
  [+245ms] [✓ SUCCESS] PASS: 应该正确构建服务主题

  ...

  ============================================================
    测试结果
  ============================================================

  [+1250ms] [INFO] 总计: 10 个测试
  [+1251ms] [✓ SUCCESS] 通过: 10
end note

if (failed > 0?) then (yes)
  :process.exit(1);
  note right
    退出码 1 表示失败
    CI/CD 会捕获到失败
  end note
else (no)
  :process.exit(0);
  note right
    退出码 0 表示成功
  end note
endif

stop

@enduml
```

---

### 集成测试完整执行流程

```plantuml
@startuml
!theme plain
skinparam backgroundColor #FEFEFE

start

:开发者执行命令;
note right
  node tests/integration/cloud-control-auth.test.js \
    9N9CN2J0012CXY \
    --host 192.168.31.116 \
    --port 8083
end note

:Node.js 启动，执行测试脚本;

:导入 mqtt 库和 logger;
note right
  import mqtt from 'mqtt';  // 真实的 MQTT 库
  import { createLogger } from '../helpers/logger.js';
end note

:解析命令行参数;
note right
  parseArgs(process.argv)

  结果:
  {
    sn: '9N9CN2J0012CXY',
    host: '192.168.31.116',
    port: 8083,
    userId: 'test_user_001',
    userCallsign: 'TestStation',
    timeout: 30000
  }
end note

:验证参数格式;
note right
  - 检查 SN 是否为 14 位
  - 检查必需参数是否存在
end note

if (参数有效?) then (no)
  :logger.error('参数无效');
  :process.exit(1);
  stop
endif

:创建真实 MQTT 客户端;
note right
  const client = mqtt.connect(
    'ws://192.168.31.116:8083/mqtt',
    {
      clientId: 'station-9N9CN2J0012CXY',
      keepalive: 60,
      clean: true
    }
  );
end note

:设置超时定时器;
note right
  setTimeout(() => {
    logger.error('测试超时');
    client.end();
    process.exit(1);
  }, 30000);
end note

:监听 MQTT 事件;

partition "等待连接事件" {
  :client.on('connect', ...);

  :logger.success('MQTT 连接成功');

  :订阅回复主题;
  note right
    thing/product/9N9CN2J0012CXY/services_reply
  end note

  :logger.success('订阅成功: ...');

  :构建授权请求消息;
  note right
    buildAuthRequestMessage(config)

    返回:
    {
      method: 'cloud_control_auth_request',
      data: {
        user_id: 'test_user_001',
        user_callsign: 'TestStation',
        control_keys: ['flight']
      },
      tid: 'tid_1704038400123_a1b2c3d4',
      bid: 'bid_1704038400123_e5f6g7h8',
      timestamp: 1704038400123
    }
  end note

  :发布消息到 services 主题;
  note right
    client.publish(
      'thing/product/9N9CN2J0012CXY/services',
      JSON.stringify(message)
    );
  end note

  :logger.success('消息已发送');
  :logger.info('等待回复...');
}

partition "等待回复消息" {
  :client.on('message', (topic, message) => {...});

  :解析 JSON 消息;
  note right
    const reply = JSON.parse(message.toString());
  end note

  :验证 TID 是否匹配;
  note right
    if (reply.tid !== requestMessage.tid) {
      return; // 忽略不匹配的消息
    }
  end note

  if (TID 匹配?) then (no)
    :logger.warn('TID 不匹配，忽略');
    detach
  endif

  :logger.success('TID 匹配');

  :检查结果字段;
  note right
    const result = reply.data?.result;
    const status = reply.data?.output?.status;
  end note

  if (result === 0 && status === 'ok'?) then (yes)
    :logger.success('✓ 授权请求成功');
    :logger.info('🎉 云端控制授权已获批准！');

    :清除超时定时器;
    :client.end();
    :process.exit(0);
    stop
  else (no)
    :logger.error('✗ 授权请求失败');
    :logger.error('Result: ' + result);

    :清除超时定时器;
    :client.end();
    :process.exit(1);
    stop
  endif
}

:监听错误事件;
note right
  client.on('error', (error) => {
    logger.error('MQTT 连接错误: ' + error.message);
    process.exit(1);
  });
end note

@enduml
```

---

## 设计原则

### 核心原则对比

```plantuml
@startuml
!theme plain

package "传统测试框架" {
  [Jest/Mocha] as jest
  [Chai] as chai
  [Sinon] as sinon

  jest -down-> chai : 使用
  jest -down-> sinon : 使用

  note right of jest
    ❌ 需要安装大量依赖
    ❌ 需要配置文件
    ❌ 学习曲线陡峭
    ❌ 框架黑盒，难调试
    ❌ 日志格式固定
  end note
}

package "自建测试体系" {
  [TestRunner] as runner
  [Assert] as assert
  [Logger] as logger
  [Mock Helpers] as mock

  runner -down-> assert : 使用
  runner -down-> logger : 使用
  runner -down-> mock : 使用

  note right of runner
    ✅ 零测试框架依赖
    ✅ 无需配置
    ✅ 纯 JS，易理解
    ✅ 代码透明，易调试
    ✅ 完全自定义日志
  end note
}

package "业务代码" {
  [TopicTemplateManager] as manager
  [MessageRouter] as router
  [MQTTConnectionManager] as mqtt
}

runner -down-> manager : 动态导入
runner -down-> router : 动态导入
runner -down-> mqtt : 动态导入

note bottom of manager
  ✅ 测试真实代码
  ✅ 发现真实 bug
  ✅ 不需要重写逻辑
end note

@enduml
```

### 设计优势总结


| 方面         | 传统测试框架                   | 自建测试体系           | 优势                   |
| ------------ | ------------------------------ | ---------------------- | ---------------------- |
| **依赖管理** | 需要安装 Jest/Mocha/Chai/Sinon | ✅ 零测试框架依赖      | 减少 node_modules 体积 |
| **业务代码** | 通常需要重写或大量 Mock        | ✅ 直接导入真实代码    | 测试真实业务逻辑       |
| **环境隔离** | 自动沙箱                       | ✅ 手动 Mock（更透明） | 完全控制环境           |
| **日志格式** | 固定格式                       | ✅ 完全自定义          | 彩色输出 + 时间戳      |
| **学习曲线** | 需要学框架 API                 | ✅ 纯 JS，易理解       | 降低学习成本           |
| **调试体验** | 框架黑盒                       | ✅ 代码透明，易调试    | 快速定位问题           |
| **灵活性**   | 受框架限制                     | ✅ 完全自由            | 可随意定制             |
| **代码量**   | 框架本身数千行                 | ✅ 仅 500 行代码       | 轻量级                 |

---

### 数据流向图

#### 单元测试数据流

```plantuml
@startuml
!theme plain
skinparam linetype ortho

rectangle "命令行" as cli
rectangle "测试文件\ntopic-template-manager.test.js" as test
rectangle "TestRunner" as runner
rectangle "Mock 环境\nglobal.window\nglobal.localStorage" as mock
rectangle "业务代码\nsrc/lib/services.js" as business
rectangle "TopicTemplateManager 实例" as manager
rectangle "Assert 断言" as assert
rectangle "Logger 日志" as logger
rectangle "退出码\n0 或 1" as exit

cli -down-> test : node xxx.test.js
test -down-> runner : new TestRunner()\nbeforeEach/test/run
runner -down-> mock : mockBrowserEnvironment()
mock -down-> business : await import()
business -down-> manager : new TopicTemplateManager()
manager -down-> assert : Assert.equal(...)
assert -down-> logger : logger.success/error
logger -down-> exit : process.exit(code)

note right of mock
  🔑 关键步骤
  创建 global.window
  创建 global.localStorage
  Mock fetch API
end note

note right of business
  🔑 动态导入
  此时看到的是 Mock 环境
  可以正常实例化类
end note

note right of assert
  🔑 断言验证
  通过 → 继续
  失败 → 抛出异常
end note

@enduml
```

#### 集成测试数据流

```plantuml
@startuml
!theme plain
skinparam linetype ortho

rectangle "命令行" as cli
rectangle "测试脚本\ncloud-control-auth.test.js" as test
rectangle "参数解析\nparseArgs()" as parse
rectangle "真实 MQTT 客户端\nmqtt.connect()" as mqtt
rectangle "DJI 协议消息\nbuildAuthRequestMessage()" as msg
rectangle "MQTT Broker" as broker
rectangle "DJI 设备" as device
rectangle "回复验证\nTID 匹配 + result 检查" as verify
rectangle "Logger 日志" as logger
rectangle "退出码\n0 或 1" as exit

cli -down-> test : node xxx.test.js <SN> --host
test -down-> parse : process.argv
parse -down-> mqtt : mqtt.connect(brokerUrl)
mqtt -down-> msg : buildAuthRequestMessage(config)
msg -down-> broker : client.publish(topic, message)
broker -down-> device : 转发消息
device -up-> broker : 回复消息
broker -up-> verify : client.on('message', ...)
verify -down-> logger : logger.success/error
logger -down-> exit : process.exit(code)

note right of mqtt
  🔑 真实连接
  WebSocket MQTT
  无 Mock，真实网络
end note

note right of msg
  🔑 复用协议逻辑
  与业务代码一致的
  消息格式和 Topic
end note

note right of verify
  🔑 验证逻辑
  1. TID 匹配
  2. result === 0
  3. status === 'ok'
end note

@enduml
```

---

## 架构图表

### 整体架构图

```plantuml
@startuml
!theme plain

skinparam package {
  BackgroundColor #E8F5E9
  BorderColor #4CAF50
}

skinparam component {
  BackgroundColor #E3F2FD
  BorderColor #2196F3
}

package "测试体系" {

  package "测试文件层" {
    [单元测试\ntopic-template-manager.test.js] as unit1
    [单元测试\nmessage-router.test.js] as unit2
    [集成测试\ncloud-control-auth.test.js] as integration
  }

  package "工具库层" {
    [Logger\n彩色日志输出] as logger
    [TestRunner\n测试运行器] as runner
    [Assert\n断言工具] as assert
    [Mock Helpers\n环境模拟] as mock
  }

  package "测试数据层" {
    [fixtures\ntopic-templates.json] as fixtures
  }
}

package "业务代码" {
  [src/lib/services.js\nTopicTemplateManager\nMessageRouter] as services
  [src/lib/mqtt.js\nMQTTConnectionManager] as mqtt
  [src/lib/state.js\nDeviceStateManager] as state
}

package "外部依赖" {
  [mqtt 库\n真实 MQTT 客户端] as mqttlib
  [MQTT Broker\nEMQX] as broker
  [DJI 设备] as device
}

unit1 -down-> runner : 使用
unit1 -down-> logger : 使用
unit1 -down-> assert : 使用
unit1 -down-> mock : 使用
unit1 -down-> services : 动态导入

unit2 -down-> runner : 使用
unit2 -down-> logger : 使用
unit2 -down-> assert : 使用
unit2 -down-> mock : 使用
unit2 -down-> services : 动态导入

integration -down-> logger : 使用
integration -down-> mqttlib : 使用
integration -down-> fixtures : 读取

mock -down-> services : 创建环境
runner -down-> assert : 捕获异常

mqttlib -down-> broker : WebSocket 连接
broker -down-> device : MQTT 协议

note right of unit1
  🧪 单元测试
  - Mock 浏览器环境
  - 测试单个模块逻辑
  - 快速执行，无外部依赖
end note

note right of integration
  🚀 集成测试
  - 真实 MQTT 连接
  - 端到端流程验证
  - 需要真实设备
end note

note right of logger
  🎨 自定义工具
  - 彩色输出
  - 时间戳
  - 层级标题
end note

note right of services
  💼 业务代码
  - 真实的生产代码
  - 测试即验证实际逻辑
  - 发现的 bug 就是真 bug
end note

@enduml
```

---

### 单元测试 vs 集成测试对比

```plantuml
@startuml
!theme plain

left to right direction

package "单元测试" {
  component "测试文件" as ut_file
  component "TestRunner" as ut_runner
  component "Mock 环境" as ut_mock
  component "业务代码\n(导入)" as ut_business
  component "Assert" as ut_assert

  ut_file -down-> ut_runner
  ut_runner -down-> ut_mock
  ut_mock -down-> ut_business
  ut_business -down-> ut_assert

  note bottom of ut_mock
    ✅ Mock window
    ✅ Mock localStorage
    ✅ Mock fetch
    ✅ 无外部依赖
    ✅ 快速执行
  end note
}

package "集成测试" {
  component "测试脚本" as it_file
  component "参数解析" as it_parse
  component "真实 MQTT" as it_mqtt
  component "MQTT Broker" as it_broker
  component "DJI 设备" as it_device

  it_file -down-> it_parse
  it_parse -down-> it_mqtt
  it_mqtt -down-> it_broker
  it_broker -down-> it_device

  note bottom of it_mqtt
    ✅ 真实网络连接
    ✅ 真实协议验证
    ✅ 端到端流程
    ❌ 需要外部环境
    ❌ 执行较慢
  end note
}

@enduml
```

---

## 总结

### 测试体系的精髓

这个测试体系的核心设计理念可以总结为：

```plantuml
@startuml
!theme plain

skinparam card {
  BackgroundColor #FFF9C4
  BorderColor #F57C00
}

card "自包含工具" as tool {
  helpers/ 提供独立的测试基础设施
  - Logger: 彩色日志
  - TestRunner: 测试运行
  - Assert: 断言验证
  - Mock: 环境模拟
}

card "业务代码复用" as business {
  直接 import 真实代码
  - 不重写逻辑
  - 测试生产代码
  - 发现真实 bug
}

card "环境适配" as env {
  单元测试 Mock 浏览器
  集成测试用真实环境
  - 灵活切换
  - 完全控制
}

card "零测试框架" as zero {
  不依赖 Jest/Mocha
  - 完全自主实现
  - 代码透明
  - 易于定制
}

card "命令行友好" as cli {
  直接 node xxx.test.js 运行
  - 支持参数
  - 彩色输出
  - 退出码标准
}

tool -down-> business
business -down-> env
env -down-> zero
zero -down-> cli

@enduml
```

### 关键优势


| 特性         | 说明                   | 收益                       |
| ------------ | ---------------------- | -------------------------- |
| **自包含**   | 所有工具都在`helpers/` | 不依赖外部测试框架         |
| **真实代码** | 动态导入业务模块       | 测试生产代码，发现真实 bug |
| **环境隔离** | Mock 浏览器对象        | Node.js 可运行浏览器代码   |
| **彩色日志** | 自定义 Logger          | 快速识别成功/失败          |
| **透明调试** | 所有代码可见           | 易于理解和修改             |

### 适用场景

#### ✅ 适合使用这个测试体系的场景

- 项目不想引入重量级测试框架
- 需要测试浏览器代码（但在 Node.js 运行）
- 需要自定义测试流程和日志格式
- 希望测试代码易于理解和维护

#### ⚠️ 不适合的场景

- 需要浏览器真实 DOM 操作（考虑 Playwright/Cypress）
- 需要代码覆盖率报告（考虑 Istanbul）
- 团队已熟悉 Jest/Mocha（迁移成本高）

---

## 扩展阅读

### 相关文档

- [tests/README.md](./README.md) - 完整测试使用文档
- [tests/TEST-SUMMARY.md](./TEST-SUMMARY.md) - 测试总结
- [../CLAUDE.md](../CLAUDE.md) - 项目架构文档

### 最佳实践

1. **单元测试优先** - 先写单元测试验证核心逻辑
2. **隔离环境** - 使用 Mock，不依赖外部服务
3. **清晰命名** - 测试名称使用"应该..."格式
4. **一测一断言** - 每个测试只验证一个行为
5. **避免依赖** - 测试之间互不依赖
6. **彩色日志** - 便于快速定位问题
7. **记录步骤** - 集成测试记录详细执行步骤

### 未来改进

- [ ]  添加更多单元测试（CardStateManager、DeviceManager）
- [ ]  添加代码覆盖率统计
- [ ]  支持并行测试执行
- [ ]  添加性能基准测试
- [ ]  集成 CI/CD 自动化

---

**文档版本**: v1.0
**最后更新**: 2024-01-18
**作者**: Claude Code
