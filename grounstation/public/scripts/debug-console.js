// Debug Console UI Class
class DebugConsoleUI {
  constructor() {
    this.autoScroll = true;
    this.autoCollapse = true;
    this.filters = {
      search: '',
      levels: new Set(['ALL']),
      sources: new Set(),
      timeRange: 'today'
    };
    this.logger = null;
    this.logs = [];
    this.filteredLogs = [];
    this.removeListener = null;
    this.pollInterval = null; // 用于轮询日志更新

    this.initializeElements();
    this.setupEventListeners();
    this.initializeLogger();
    this.updateDisplay();
  }

  initializeElements() {
    this.elements = {
      logContainer: document.getElementById('log-container'),
      logList: document.getElementById('log-list'),
      logCount: document.getElementById('log-count'),
      connectionStatus: document.getElementById('connection-status'),
      autoScrollBtn: document.getElementById('auto-scroll-btn'),
      autoCollapseBtn: document.getElementById('auto-collapse-btn'),
      clearLogsBtn: document.getElementById('clear-logs'),
      exportLogsBtn: document.getElementById('export-logs'),
      searchInput: document.getElementById('search-input'),
      levelFilters: document.querySelectorAll('.level-filter'),
      sourceFilters: document.getElementById('source-filters'),
      timeRange: document.getElementById('time-range'),
      logStats: document.getElementById('log-stats'),
      visibleCount: document.getElementById('visible-count'),
      totalCount: document.getElementById('total-count'),
      lastUpdate: document.getElementById('last-update')
    };
  }

  setupEventListeners() {
    this.elements.autoScrollBtn.addEventListener('click', () => this.toggleAutoScroll());
    this.elements.autoCollapseBtn.addEventListener('click', () => this.toggleAutoCollapse());
    this.elements.clearLogsBtn.addEventListener('click', () => this.clearLogs());
    this.elements.exportLogsBtn.addEventListener('click', () => this.exportLogs());

    this.elements.searchInput.addEventListener('input', (e) => {
      this.filters.search = e.target.value;
      this.applyFilters();
    });

    this.elements.levelFilters.forEach(filter => {
      filter.addEventListener('change', (e) => {
        // 将事件对象存储为全局变量供updateLevelFilters使用
        window._currentFilterEvent = e;
        this.updateLevelFilters();
        delete window._currentFilterEvent;
      });
    });

    this.elements.timeRange.addEventListener('change', (e) => {
      this.filters.timeRange = e.target.value;
      this.applyFilters();
    });
  }

  async initializeLogger() {
    try {
      // 尝试多种方式获取logger实例
      let logger = null;

      // 方法1: 检查全局变量
      if (typeof window !== 'undefined' && window.DJIDebugLogger) {
        logger = window.DJIDebugLogger;
        console.log('Found logger via global window.DJIDebugLogger');
      }

      // 方法2: 动态导入
      if (!logger) {
        try {
          const module = await import('/src/lib/debug.js');
          logger = module.default;
          console.log('Found logger via dynamic import');
        } catch (importError) {
          console.warn('Failed to import debug.js:', importError);
        }
      }

      // 方法3: 创建新实例并设置为全局
      if (!logger) {
        // 如果都失败了，创建临时的localStorage-based logger
        logger = {
          logs: [],
          listeners: new Set(),
          getLogs: () => {
            try {
              const stored = localStorage.getItem('debug_logs');
              return stored ? JSON.parse(stored) : [];
            } catch (e) {
              return [];
            }
          },
          addListener: (callback) => {
            logger.listeners.add(callback);
            return () => logger.listeners.delete(callback);
          },
          clear: () => {
            localStorage.removeItem('debug_logs');
            logger.logs = [];
            logger.listeners.forEach(listener => {
              try {
                listener({ type: 'clear' });
              } catch (e) {
                console.error('Listener error:', e);
              }
            });
          },
          export: () => {
            return JSON.stringify({
              exported: new Date().toISOString(),
              logs: logger.getLogs()
            }, null, 2);
          }
        };
        console.log('Created fallback logger instance');
      }

      this.logger = logger;

      // Load existing logs - 限制加载数量以防止内存溢出
      const allLogs = this.logger.getLogs();
      this.logs = allLogs.slice(-500); // 只加载最新的500条，与maxLogs保持一致
      console.log(`Loaded ${this.logs.length} existing logs (limited from ${allLogs.length} total)`);

      // Listen for new logs
      this.removeListener = this.logger.addListener((logEntry) => {
        if (logEntry.type === 'clear') {
          this.logs = [];
        } else {
          this.logs.push(logEntry);
          // 限制内存中的日志数量，只保留最新的500条，与DebugLogger.maxLogs一致
          if (this.logs.length > 500) {
            this.logs = this.logs.slice(-500);
          }
        }
        this.applyFilters();
        this.updateStats();
      });

      // 使用localStorage作为跨标签页通信机制
      this.setupCrossTabCommunication();

      this.elements.connectionStatus.textContent = 'Connected';
      this.elements.connectionStatus.className = 'filter-badge bg-green-900 text-green-200';

      this.applyFilters();
      this.updateStats();
    } catch (error) {
      console.error('Failed to initialize logger:', error);
      this.elements.connectionStatus.textContent = 'Failed';
      this.elements.connectionStatus.className = 'filter-badge bg-red-900 text-red-200';
    }
  }

  setupCrossTabCommunication() {
    // 监听localStorage变化事件，实现跨标签页实时通信
    this.storageListener = (e) => {
      if (e.key === 'dji_debug_logs') {
        try {
          const newLogs = JSON.parse(e.newValue || '[]');
          // console.log(`Storage event: logs updated to ${newLogs.length} entries`);
          this.logs = newLogs.slice(-500); // 限制加载数量
          this.applyFilters();
          this.updateStats();
        } catch (error) {
          console.warn('Failed to parse logs from storage event:', error);
        }
      }
    };

    window.addEventListener('storage', this.storageListener);

    // 也监听自定义事件（用于同一标签页内的通信）
    this.customEventListener = (e) => {
      if (e.detail && e.detail.type === 'debug-log-update') {
        // console.log('Custom event: debug logs updated');
        const currentLogs = this.logger.getLogs();
        this.logs = currentLogs.slice(-500);
        this.applyFilters();
        this.updateStats();
      }
    };

    window.addEventListener('debug-log-changed', this.customEventListener);
  }

  updateLevelFilters() {
    const allFilter = document.querySelector('.level-filter[value="ALL"]');
    const otherFilters = Array.from(document.querySelectorAll('.level-filter:not([value="ALL"])'));
    const event = window._currentFilterEvent;

    // 如果点击的是ALL复选框
    if (event && event.target === allFilter) {
      if (allFilter.checked) {
        // ALL被选中时，选择所有其他选项
        otherFilters.forEach(filter => filter.checked = true);
      } else {
        // ALL被取消时，取消所有其他选项
        otherFilters.forEach(filter => filter.checked = false);
      }
    } else if (event && otherFilters.includes(event.target)) {
      // 如果点击的是其他选项
      const checkedOthers = otherFilters.filter(f => f.checked);

      // 如果所有其他选项都被选中，则自动选中ALL
      if (checkedOthers.length === otherFilters.length) {
        allFilter.checked = true;
      }
      // 如果有任何其他选项被取消，则取消ALL
      else {
        allFilter.checked = false;
      }
    }

    // 更新filters.levels
    this.filters.levels = new Set();

    // 如果ALL被选中，添加ALL到filters
    if (allFilter.checked) {
      this.filters.levels.add('ALL');
    }

    // 添加所有被选中的具体级别
    otherFilters.forEach(filter => {
      if (filter.checked) {
        this.filters.levels.add(filter.value);
      }
    });

    // 如果没有选择任何level，则默认选择ALL和所有其他选项
    if (this.filters.levels.size === 0) {
      allFilter.checked = true;
      otherFilters.forEach(filter => filter.checked = true);
      this.filters.levels.add('ALL');
      otherFilters.forEach(filter => {
        this.filters.levels.add(filter.value);
      });
    }

    this.applyFilters();
  }

  buildSourceFilters() {
    // 基于当前过滤后的日志（而不是全部日志）来构建source filters
    const sources = new Set();
    this.filteredLogs.forEach(log => {
      if (log.source && log.source.file) {
        sources.add(log.source.file);
      }
    });

    // 如果没有sources，清空显示
    if (sources.size === 0) {
      this.elements.sourceFilters.innerHTML = '<div class="text-gray-500 text-xs">No sources in current view</div>';
      this.filters.sources = new Set();
      return;
    }

    this.elements.sourceFilters.innerHTML = Array.from(sources)
      .sort()
      .map(source => `
        <label class="flex items-center">
          <input type="checkbox" class="source-filter mr-2" value="${source}" checked />
          <span class="truncate">${source}</span>
        </label>
      `).join('');

    this.elements.sourceFilters.querySelectorAll('.source-filter').forEach(filter => {
      filter.addEventListener('change', () => {
        this.filters.sources = new Set(
          Array.from(this.elements.sourceFilters.querySelectorAll('.source-filter:checked'))
            .map(f => f.value)
        );
        this.applyFilters();
      });
    });

    // 重置source filters为当前可见的所有sources
    this.filters.sources = sources;
  }

  applyFilters() {
    let filtered = this.logs;

    // Time filter
    if (this.filters.timeRange !== 'all') {
      const now = new Date();
      let cutoff;

      switch (this.filters.timeRange) {
        case '1m':
          cutoff = new Date(now.getTime() - 60 * 1000);
          break;
        case '5m':
          cutoff = new Date(now.getTime() - 5 * 60 * 1000);
          break;
        case '1h':
          cutoff = new Date(now.getTime() - 60 * 60 * 1000);
          break;
        case 'today':
          cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          break;
      }

      if (cutoff) {
        filtered = filtered.filter(log => new Date(log.timestamp) >= cutoff);
      }
    }

    // Level filter
    if (!this.filters.levels.has('ALL')) {
      filtered = filtered.filter(log => this.filters.levels.has(log.level));
    }

    // Source filter
    if (this.filters.sources.size > 0) {
      filtered = filtered.filter(log =>
        !log.source || !log.source.file || this.filters.sources.has(log.source.file)
      );
    }

    // Search filter
    if (this.filters.search) {
      const searchLower = this.filters.search.toLowerCase();
      filtered = filtered.filter(log =>
        log.args.some(arg =>
          String(arg).toLowerCase().includes(searchLower)
        ) ||
        (log.source && log.source.file && log.source.file.toLowerCase().includes(searchLower))
      );
    }

    this.filteredLogs = filtered;
    this.updateDisplay();
  }

  updateDisplay() {
    const logList = this.elements.logList;

    if (this.filteredLogs.length === 0) {
      logList.innerHTML = `
        <div class="text-gray-500 text-center py-8">
          <div class="text-4xl mb-2">🔍</div>
          <div>No logs match current filters</div>
          <div class="text-sm mt-2">Try adjusting your filters or clear them</div>
        </div>
      `;
    } else {
      logList.innerHTML = this.filteredLogs
        .slice(-500) // 默认显示最后500条日志
        .map(log => this.renderLogEntry(log))
        .join('');
    }

    const displayedLogs = this.filteredLogs.slice(-500); // 实际显示的日志数量

    this.elements.visibleCount.textContent = displayedLogs.length;
    this.elements.totalCount.textContent = this.filteredLogs.length;
    this.elements.logCount.textContent = `${displayedLogs.length}/${this.filteredLogs.length} logs`;
    this.elements.lastUpdate.textContent = new Date().toLocaleTimeString();

    // 在显示更新后，基于当前显示的日志重新构建source filters
    this.buildSourceFilters();

    if (this.autoScroll) {
      this.scrollToBottom();
    }
  }

  renderLogEntry(log) {
    const timestamp = new Date(log.timestamp).toLocaleTimeString();

    // 动态获取level配置，支持自定义level
    const getLevelColor = (level) => {
      if (this.logger && this.logger.logLevels && this.logger.logLevels[level]) {
        const color = this.logger.logLevels[level].color;
        // 将hex颜色转换为Tailwind类名
        const colorMap = {
          '#6b7280': 'text-gray-400',
          '#3b82f6': 'text-blue-400',
          '#f59e0b': 'text-yellow-400',
          '#ef4444': 'text-red-400',
          '#10b981': 'text-green-400',
          '#8b5cf6': 'text-purple-400',
          '#06b6d4': 'text-cyan-400'
        };
        return colorMap[color] || 'text-gray-400';
      }
      // 回退到默认配置
      const fallbackColors = {
        DEBUG: 'text-gray-400',
        INFO: 'text-blue-400',
        WARN: 'text-yellow-400',
        ERROR: 'text-red-400',
        MQTT: 'text-green-400',
        STATE: 'text-purple-400',
        SERVICE: 'text-cyan-400'
      };
      return fallbackColors[level] || 'text-gray-400';
    };

    const getLevelIcon = (level) => {
      if (this.logger && this.logger.logLevels && this.logger.logLevels[level]) {
        return this.logger.logLevels[level].icon;
      }
      // 回退到默认配置
      const fallbackIcons = {
        DEBUG: '🔍',
        INFO: 'ℹ️',
        WARN: '⚠️',
        ERROR: '❌',
        MQTT: '📡',
        STATE: '📊',
        SERVICE: '🔧'
      };
      return fallbackIcons[level] || '📝';
    };

    const sourceInfo = log.source ?
      `${log.source.file}:${log.source.line}` :
      'unknown';

    const content = log.args.map(arg => {
      if (typeof arg === 'string') return arg;
      return JSON.stringify(arg, null, 2);
    }).join(' ');

    const hasJson = /\{[\s\S]*?:[\s\S]*?\}/.test(content) || /\[[\s\S]*?[,\{\[][\s\S]*?\]/.test(content);
    const shouldCollapse = this.autoCollapse && hasJson;
    const firstLine = content.split('\n')[0];

    // 使用表格式布局确保完美对齐
    if (shouldCollapse) {
      return `<div class="log-entry log-level-${log.level} pl-3 py-1 hover:bg-gray-800 rounded-sm log-collapsible log-collapsed" onclick="this.classList.toggle('log-collapsed'); this.classList.toggle('log-expanded');">
  <div class="log-table-layout">
    <div class="log-table-row">
      <div class="log-table-cell timestamp text-gray-500 text-xs">${timestamp}</div>
      <div class="log-table-cell level ${getLevelColor(log.level)} text-sm">${getLevelIcon(log.level)} ${log.level}</div>
      <div class="log-table-cell source text-gray-500 text-xs" title="${sourceInfo}">${sourceInfo}</div>
      <div class="log-table-cell content text-gray-200">
        <div class="log-preview">
          <span class="json-tag">JSON</span><span class="collapse-indicator">[+]</span>${this.escapeHtml(firstLine)}
        </div>
        <div class="log-full">${this.escapeHtml(content)}</div>
      </div>
    </div>
  </div>
</div>`;
    } else {
      return `<div class="log-entry log-level-${log.level} pl-3 py-1 hover:bg-gray-800 rounded-sm">
  <div class="log-table-layout">
    <div class="log-table-row">
      <div class="log-table-cell timestamp text-gray-500 text-xs">${timestamp}</div>
      <div class="log-table-cell level ${getLevelColor(log.level)} text-sm">${getLevelIcon(log.level)} ${log.level}</div>
      <div class="log-table-cell source text-gray-500 text-xs" title="${sourceInfo}">${sourceInfo}</div>
      <div class="log-table-cell content text-gray-200 whitespace-pre-wrap">${this.escapeHtml(content)}</div>
    </div>
  </div>
</div>`;
    }
  }

  toggleAutoCollapse() {
    this.autoCollapse = !this.autoCollapse;
    this.elements.autoCollapseBtn.textContent = `Auto Collapse: ${this.autoCollapse ? 'ON' : 'OFF'}`;
    this.elements.autoCollapseBtn.className = this.autoCollapse ?
      'filter-badge bg-purple-900 text-purple-200 hover:bg-purple-800 cursor-pointer' :
      'filter-badge bg-gray-700 text-gray-300 hover:bg-gray-600 cursor-pointer';

    this.updateDisplay();
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  updateStats() {
    const stats = {};
    this.logs.forEach(log => {
      stats[log.level] = (stats[log.level] || 0) + 1;
    });

    const totalLogs = this.logs.length;
    const statsList = Object.entries(stats)
      .sort(([,a], [,b]) => b - a)
      .map(([level, count]) => {
        const percentage = totalLogs > 0 ? Math.round((count / totalLogs) * 100) : 0;

        // 动态获取level颜色配置
        const getLevelColorForStats = (level) => {
          if (this.logger && this.logger.logLevels && this.logger.logLevels[level]) {
            const color = this.logger.logLevels[level].color;
            // 将hex颜色转换为Tailwind类名
            const colorMap = {
              '#6b7280': 'text-gray-400',
              '#3b82f6': 'text-blue-400',
              '#f59e0b': 'text-yellow-400',
              '#ef4444': 'text-red-400',
              '#10b981': 'text-green-400',
              '#8b5cf6': 'text-purple-400',
              '#06b6d4': 'text-cyan-400'
            };
            return colorMap[color] || 'text-gray-400';
          }
          // 回退到默认配置
          const fallbackColors = {
            ERROR: 'text-red-400',
            WARN: 'text-yellow-400',
            INFO: 'text-blue-400',
            DEBUG: 'text-gray-400',
            MQTT: 'text-green-400',
            STATE: 'text-purple-400',
            SERVICE: 'text-cyan-400'
          };
          return fallbackColors[level] || 'text-gray-400';
        };

        return `
          <div class="flex justify-between">
            <span class="${getLevelColorForStats(level)}">${level}</span>
            <span class="text-gray-300">${count} (${percentage}%)</span>
          </div>
        `;
      }).join('');

    this.elements.logStats.innerHTML = statsList || '<div class="text-gray-500">No logs yet</div>';
  }

  toggleAutoScroll() {
    this.autoScroll = !this.autoScroll;
    this.elements.autoScrollBtn.textContent = `Auto Scroll: ${this.autoScroll ? 'ON' : 'OFF'}`;
    this.elements.autoScrollBtn.className = this.autoScroll ?
      'filter-badge bg-green-900 text-green-200 hover:bg-green-800 cursor-pointer' :
      'filter-badge bg-gray-700 text-gray-300 hover:bg-gray-600 cursor-pointer';

    if (this.autoScroll) {
      this.scrollToBottom();
    }
  }

  scrollToBottom() {
    requestAnimationFrame(() => {
      this.elements.logContainer.scrollTop = this.elements.logContainer.scrollHeight;
    });
  }

  clearLogs() {
    if (confirm('Clear all debug logs? This action cannot be undone.')) {
      // 方法1: 通过logger清除
      if (this.logger && typeof this.logger.clear === 'function') {
        this.logger.clear();
      }

      // 方法2: 直接清除localStorage
      try {
        localStorage.removeItem('debug_logs');
        localStorage.removeItem('dji_debug_logs');
      } catch (e) {
        console.warn('无法清除localStorage中的日志:', e);
      }

      // 方法3: 清除内存中的日志
      this.logs = [];
      this.filteredLogs = [];

      // 方法4: 如果全局logger存在，也清除它
      if (typeof window !== 'undefined' && window.DJIDebugLogger) {
        try {
          if (typeof window.DJIDebugLogger.clear === 'function') {
            window.DJIDebugLogger.clear();
          }
          if (window.DJIDebugLogger.logs) {
            window.DJIDebugLogger.logs = [];
          }
        } catch (e) {
          console.warn('无法清除全局logger:', e);
        }
      }

      console.log('All logs cleared');
      this.updateDisplay();
      this.updateStats();
    }
  }

  exportLogs() {
    if (!this.logger) return;

    const data = this.logger.export();
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `dji-debug-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  destroy() {
    if (this.removeListener) {
      this.removeListener();
    }
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
    if (this.storageListener) {
      window.removeEventListener('storage', this.storageListener);
    }
    if (this.customEventListener) {
      window.removeEventListener('debug-log-changed', this.customEventListener);
    }
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.debugConsole = new DebugConsoleUI();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (window.debugConsole) {
    window.debugConsole.destroy();
  }
});