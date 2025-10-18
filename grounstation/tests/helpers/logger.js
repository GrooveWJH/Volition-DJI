/**
 * 测试日志工具 - 带颜色输出
 */

const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  gray: '\x1b[90m',
};

class TestLogger {
  constructor(prefix = '[TEST]') {
    this.prefix = prefix;
    this.startTime = Date.now();
  }

  _timestamp() {
    const elapsed = Date.now() - this.startTime;
    return `${colors.gray}[+${elapsed}ms]${colors.reset}`;
  }

  _format(level, color, message, ...args) {
    const timestamp = this._timestamp();
    const prefix = `${color}${this.prefix} [${level}]${colors.reset}`;
    console.log(`${timestamp} ${prefix}`, message, ...args);
  }

  info(message, ...args) {
    this._format('INFO', colors.blue, message, ...args);
  }

  success(message, ...args) {
    this._format('✓ SUCCESS', colors.green, message, ...args);
  }

  error(message, ...args) {
    this._format('✗ ERROR', colors.red, message, ...args);
  }

  warn(message, ...args) {
    this._format('⚠ WARN', colors.yellow, message, ...args);
  }

  debug(message, ...args) {
    this._format('DEBUG', colors.gray, message, ...args);
  }

  header(message) {
    const line = '='.repeat(60);
    console.log(`\n${colors.cyan}${line}`);
    console.log(`  ${message}`);
    console.log(`${line}${colors.reset}\n`);
  }

  section(message) {
    console.log(`\n${colors.magenta}▶ ${message}${colors.reset}`);
  }

  result(passed, message) {
    if (passed) {
      this.success(message);
    } else {
      this.error(message);
    }
  }

  table(data) {
    console.table(data);
  }
}

export function createLogger(prefix) {
  return new TestLogger(prefix);
}

export default TestLogger;
