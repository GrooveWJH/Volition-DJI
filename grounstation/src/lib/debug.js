// DJI Ground Station - 调试日志系统
// 重新导出debug-logger.js的功能

// DJI Ground Station - 集中调试日志系统
class DebugLogger {
  constructor() {
    this.logs = [];
    this.maxLogs = 500; // 减少到1000条以防止内存溢出
    this.enabled = true;
    this.listeners = new Set();
    this.lastSaveTime = 0; // 用于限制保存频率
    this.logLevels = {
      DEBUG: { priority: 0, color: '#6b7280', icon: '🔍' },
      INFO: { priority: 1, color: '#3b82f6', icon: 'ℹ️' },
      WARN: { priority: 2, color: '#f59e0b', icon: '⚠️' },
      ERROR: { priority: 3, color: '#ef4444', icon: '❌' },
      MQTT: { priority: 1, color: '#10b981', icon: '📡' },
      STATE: { priority: 1, color: '#8b5cf6', icon: '📊' },
      SERVICE: { priority: 1, color: '#06b6d4', icon: '🔧' }
    };

    this._initStorage();
    this._interceptConsole();
  }

  _initStorage() {
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('dji_debug_logs');
        if (stored) {
          this.logs = JSON.parse(stored).slice(-this.maxLogs);
        }
      } catch (e) {
        console.warn('无法加载调试日志:', e);
      }
    }
  }

  _interceptConsole() {
    if (typeof window !== 'undefined') {
      const originalLog = console.log;
      const originalError = console.error;
      const originalWarn = console.warn;
      const originalInfo = console.info;

      console.log = (...args) => {
        this.log('INFO', ...args);
        originalLog.apply(console, args);
      };

      console.error = (...args) => {
        this.log('ERROR', ...args);
        originalError.apply(console, args);
      };

      console.warn = (...args) => {
        this.log('WARN', ...args);
        originalWarn.apply(console, args);
      };

      console.info = (...args) => {
        this.log('INFO', ...args);
        originalInfo.apply(console, args);
      };
    }
  }

  log(level, ...args) {
    if (!this.enabled) return;

    // 支持自定义level：如果第一个参数是对象且包含level，则使用自定义level
    let actualLevel = level;
    let logArgs = args;

    // 检查是否传入了自定义level参数
    if (args.length > 0 && typeof args[0] === 'object' && args[0] !== null && !Array.isArray(args[0]) && args[0].level) {
      actualLevel = args[0].level;
      logArgs = args.slice(1);
    }

    // 检查第一个参数是否是来源标识
    let source = null;

    if (logArgs.length > 0 && typeof logArgs[0] === 'string' && logArgs[0].startsWith('[') && logArgs[0].endsWith(']')) {
      source = { file: logArgs[0].slice(1, -1), function: 'unknown', line: 0 };
      logArgs = logArgs.slice(1);
    }

    // 确保level在已定义的levels中，如果不存在则添加为自定义level
    if (!this.logLevels[actualLevel]) {
      this.logLevels[actualLevel] = {
        priority: 1, // 默认优先级
        color: '#6b7280', // 默认灰色
        icon: '📝' // 默认图标
      };
    }

    const timestamp = new Date();
    const logEntry = {
      id: Date.now() + Math.random(),
      timestamp,
      level: actualLevel,
      args: logArgs.map(arg => this._serializeArg(arg)),
      stack: this._getStack(),
      source: source || this._getSource()
    };

    this.logs.push(logEntry);

    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }

    this._saveToStorage();
    this._notifyListeners(logEntry);
  }

  _serializeArg(arg) {
    if (arg === null) return 'null';
    if (arg === undefined) return 'undefined';
    if (typeof arg === 'string') return arg;
    if (typeof arg === 'number' || typeof arg === 'boolean') return arg;

    try {
      return JSON.stringify(arg, null, 2);
    } catch (e) {
      return arg.toString();
    }
  }

  _getStack() {
    try {
      const stack = new Error().stack;
      const lines = stack.split('\n');
      return lines.slice(3, 5).map(line => line.trim());
    } catch (e) {
      return [];
    }
  }

  _getSource() {
    try {
      const stack = new Error().stack;
      const lines = stack.split('\n');
      const caller = lines[4] || '';
      const match = caller.match(/at\s+(.+?)\s+\((.+?):(\d+):(\d+)\)/);
      if (match) {
        return {
          function: match[1],
          file: match[2].split('/').pop(),
          line: parseInt(match[3])
        };
      }
    } catch (e) {
      // Ignore
    }
    return null;
  }

  _saveToStorage() {
    if (typeof window !== 'undefined') {
      // 限制保存频率，避免过度写入
      const now = Date.now();
      if (this.lastSaveTime && (now - this.lastSaveTime) < 1000) {
        return; // 1秒内不重复保存
      }
      this.lastSaveTime = now;

      try {
        // 只保存最新的500条日志到localStorage
        const logsToSave = this.logs.slice(-500);
        localStorage.setItem('dji_debug_logs', JSON.stringify(logsToSave));

        // 触发自定义事件通知其他页面
        if (typeof window !== 'undefined' && window.dispatchEvent) {
          window.dispatchEvent(new CustomEvent('debug-log-changed', {
            detail: { type: 'debug-log-update', count: logsToSave.length }
          }));
        }
      } catch (e) {
        // Storage full, try to save even fewer logs
        try {
          const minimalLogs = this.logs.slice(-100);
          localStorage.setItem('dji_debug_logs', JSON.stringify(minimalLogs));
        } catch (e2) {
          // If still failing, clear the storage and save minimal logs
          try {
            localStorage.removeItem('dji_debug_logs');
            const emergencyLogs = this.logs.slice(-50);
            localStorage.setItem('dji_debug_logs', JSON.stringify(emergencyLogs));
          } catch (e3) {
            // Complete failure, disable localStorage saving
            console.warn('localStorage完全不可用，禁用日志持久化');
          }
        }
      }
    }
  }

  _notifyListeners(logEntry) {
    this.listeners.forEach(listener => {
      try {
        listener(logEntry);
      } catch (e) {
        console.error('调试日志监听器错误:', e);
      }
    });
  }

  // 公共接口
  getLogs(filter = {}) {
    let filtered = this.logs;

    if (filter.level) {
      filtered = filtered.filter(log => log.level === filter.level);
    }

    if (filter.source) {
      filtered = filtered.filter(log =>
        log.source && log.source.file && log.source.file.includes(filter.source)
      );
    }

    if (filter.search) {
      const searchLower = filter.search.toLowerCase();
      filtered = filtered.filter(log =>
        log.args.some(arg =>
          String(arg).toLowerCase().includes(searchLower)
        )
      );
    }

    if (filter.since) {
      const since = new Date(filter.since);
      filtered = filtered.filter(log => new Date(log.timestamp) >= since);
    }

    return filtered;
  }

  addListener(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  clear() {
    this.logs = [];
    this._saveToStorage();
    this._notifyListeners({ type: 'clear' });
  }

  export() {
    const data = {
      exported: new Date().toISOString(),
      deviceInfo: this._getDeviceInfo(),
      logs: this.logs
    };
    return JSON.stringify(data, null, 2);
  }

  _getDeviceInfo() {
    if (typeof window === 'undefined') return {};

    return {
      userAgent: navigator.userAgent,
      url: window.location.href,
      timestamp: new Date().toISOString(),
      localStorage: this._getStorageInfo()
    };
  }

  _getStorageInfo() {
    try {
      const keys = Object.keys(localStorage).filter(key => key.startsWith('dji_'));
      return keys.reduce((info, key) => {
        info[key] = localStorage.getItem(key)?.length || 0;
        return info;
      }, {});
    } catch (e) {
      return {};
    }
  }

  // 便捷方法
  debug(...args) { this.log('DEBUG', ...args); }
  info(...args) { this.log('INFO', ...args); }
  warn(...args) { this.log('WARN', ...args); }
  error(...args) { this.log('ERROR', ...args); }
  mqtt(...args) { this.log('MQTT', ...args); }
  state(...args) { this.log('STATE', ...args); }
  service(...args) { this.log('SERVICE', ...args); }
}

// 全局单例
const debugLogger = typeof window !== 'undefined' && window.DJIDebugLogger
  ? window.DJIDebugLogger
  : new DebugLogger();

if (typeof window !== 'undefined') {
  window.DJIDebugLogger = debugLogger;
}

export default debugLogger;