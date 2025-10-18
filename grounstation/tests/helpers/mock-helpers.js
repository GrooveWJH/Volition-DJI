/**
 * 测试 Mock 工具库
 * 用于模拟浏览器环境和外部依赖
 */

/**
 * 模拟 localStorage
 */
export class MockLocalStorage {
  constructor() {
    this.store = new Map();
  }

  getItem(key) {
    return this.store.get(key) || null;
  }

  setItem(key, value) {
    this.store.set(key, String(value));
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

/**
 * 模拟浏览器 window 对象
 */
export function mockBrowserEnvironment() {
  global.window = {
    localStorage: new MockLocalStorage(),
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
    mqttManager: null,
    deviceContext: null,
    deviceStateManager: null,
    cardStateManager: null,
  };
  global.localStorage = global.window.localStorage;
}

/**
 * 清理浏览器环境 Mock
 */
export function cleanupBrowserEnvironment() {
  delete global.window;
  delete global.localStorage;
}

/**
 * 模拟 MQTT 客户端
 */
export class MockMQTTClient {
  constructor() {
    this.isConnected = false;
    this.subscriptions = new Set();
    this.publishedMessages = [];
    this.messageHandlers = [];
  }

  connect() {
    this.isConnected = true;
    return Promise.resolve(true);
  }

  disconnect() {
    this.isConnected = false;
    this.subscriptions.clear();
  }

  subscribe(topic, callback) {
    this.subscriptions.add(topic);
    if (callback) {
      this.messageHandlers.push({ topic, callback });
    }
    return true;
  }

  publish(topic, message) {
    this.publishedMessages.push({ topic, message, timestamp: Date.now() });
    return Promise.resolve(true);
  }

  // 模拟接收消息
  simulateMessage(topic, message) {
    this.messageHandlers
      .filter(h => h.topic === topic)
      .forEach(h => h.callback(topic, message));
  }

  getPublishedMessages() {
    return [...this.publishedMessages];
  }

  getLastPublishedMessage() {
    return this.publishedMessages[this.publishedMessages.length - 1];
  }

  clearPublishedMessages() {
    this.publishedMessages = [];
  }
}

/**
 * 断言工具
 */
export class Assert {
  static equal(actual, expected, message = '') {
    if (actual !== expected) {
      throw new Error(
        `Assertion failed: ${message}\n  Expected: ${expected}\n  Actual: ${actual}`
      );
    }
  }

  static deepEqual(actual, expected, message = '') {
    const actualStr = JSON.stringify(actual);
    const expectedStr = JSON.stringify(expected);
    if (actualStr !== expectedStr) {
      throw new Error(
        `Assertion failed: ${message}\n  Expected: ${expectedStr}\n  Actual: ${actualStr}`
      );
    }
  }

  static true(value, message = '') {
    if (value !== true) {
      throw new Error(`Assertion failed: ${message}\n  Expected: true\n  Actual: ${value}`);
    }
  }

  static false(value, message = '') {
    if (value !== false) {
      throw new Error(`Assertion failed: ${message}\n  Expected: false\n  Actual: ${value}`);
    }
  }

  static notNull(value, message = '') {
    if (value === null || value === undefined) {
      throw new Error(`Assertion failed: ${message}\n  Value should not be null/undefined`);
    }
  }

  static throws(fn, message = '') {
    let threw = false;
    try {
      fn();
    } catch (e) {
      threw = true;
    }
    if (!threw) {
      throw new Error(`Assertion failed: ${message}\n  Function should have thrown an error`);
    }
  }

  static async resolves(promise, message = '') {
    try {
      await promise;
    } catch (e) {
      throw new Error(`Assertion failed: ${message}\n  Promise should have resolved: ${e.message}`);
    }
  }

  static async rejects(promise, message = '') {
    let rejected = false;
    try {
      await promise;
    } catch (e) {
      rejected = true;
    }
    if (!rejected) {
      throw new Error(`Assertion failed: ${message}\n  Promise should have rejected`);
    }
  }
}

/**
 * 测试运行器
 */
export class TestRunner {
  constructor(suiteName) {
    this.suiteName = suiteName;
    this.tests = [];
    this.beforeEachFn = null;
    this.afterEachFn = null;
  }

  beforeEach(fn) {
    this.beforeEachFn = fn;
  }

  afterEach(fn) {
    this.afterEachFn = fn;
  }

  test(name, fn) {
    this.tests.push({ name, fn });
  }

  async run(logger) {
    logger.header(`测试套件: ${this.suiteName}`);

    let passed = 0;
    let failed = 0;
    const failures = [];

    for (const { name, fn } of this.tests) {
      logger.section(`测试: ${name}`);

      try {
        if (this.beforeEachFn) await this.beforeEachFn();
        await fn();
        if (this.afterEachFn) await this.afterEachFn();

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
      failures.forEach(({ name, error }) => {
        logger.error(`\n  ✗ ${name}`);
        logger.error(`    ${error.stack || error.message}`);
      });
    }

    return { total: this.tests.length, passed, failed, failures };
  }
}
