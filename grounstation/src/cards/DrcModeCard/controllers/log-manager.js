/**
 * DRC模式日志管理器
 * 负责DRC模式相关的日志记录、过滤、显示和与中央调试系统的集成
 */

import debugLogger from '#lib/debug.js';

export class LogManager {
  constructor() {
    this.logs = [];
    this.maxLogs = 100; // 最大日志条数
    this.elements = null; // DOM元素引用
    this.currentFilter = 'all'; // 当前过滤条件

    // 日志类型配置
    this.logTypes = {
      '系统': { color: 'text-gray-500', icon: 'info' },
      '信息': { color: 'text-blue-600', icon: 'info' },
      '成功': { color: 'text-green-600', icon: 'check_circle' },
      '警告': { color: 'text-yellow-600', icon: 'warning' },
      '错误': { color: 'text-red-600', icon: 'error' },
      '调试': { color: 'text-purple-600', icon: 'bug_report' },
      '帮助': { color: 'text-cyan-600', icon: 'help' },
      '提示': { color: 'text-indigo-600', icon: 'lightbulb' }
    };

    debugLogger.state('[DrcLogManager] 已初始化');
  }

  /**
   * 设置DOM元素引用
   */
  setElements(elements) {
    this.elements = elements;
  }

  /**
   * 添加日志
   */
  addLog(type, message, metadata = {}) {
    const logEntry = {
      id: Date.now() + Math.random(),
      type: type,
      message: message,
      timestamp: Date.now(),
      metadata: metadata
    };

    this.logs.push(logEntry);

    // 限制日志数量
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }

    // 同步到中央调试系统
    this.syncToCentralLogger(logEntry);

    // 更新UI显示
    this.updateLogsDisplay();

    debugLogger.info(`[DRC][${type}] ${message}`, metadata);
  }

  /**
   * 同步到中央调试系统
   */
  syncToCentralLogger(logEntry) {
    const logLevel = this.getDebugLogLevel(logEntry.type);
    const message = `[DRC] ${logEntry.message}`;

    switch (logLevel) {
      case 'error':
        debugLogger.error(message, logEntry.metadata);
        break;
      case 'warn':
        debugLogger.warn(message, logEntry.metadata);
        break;
      case 'info':
        debugLogger.info(message, logEntry.metadata);
        break;
      default:
        debugLogger.debug(message, logEntry.metadata);
    }
  }

  /**
   * 映射日志类型到调试级别
   */
  getDebugLogLevel(logType) {
    const mapping = {
      '错误': 'error',
      '警告': 'warn',
      '成功': 'info',
      '信息': 'info',
      '系统': 'debug',
      '调试': 'debug',
      '帮助': 'info',
      '提示': 'info'
    };
    return mapping[logType] || 'debug';
  }

  /**
   * 清空日志
   */
  clearLogs() {
    this.logs = [];
    this.updateLogsDisplay();
    debugLogger.state('[DrcLogManager] 日志已清空');
  }

  /**
   * 过滤日志
   */
  filterLogs(filterType) {
    this.currentFilter = filterType;
    this.updateLogsDisplay();
    debugLogger.state(`[DrcLogManager] 日志过滤器设置为: ${filterType}`);
  }

  /**
   * 获取过滤后的日志
   */
  getFilteredLogs() {
    if (this.currentFilter === 'all') {
      return this.logs;
    }
    return this.logs.filter(log => log.type === this.currentFilter);
  }

  /**
   * 更新日志显示
   */
  updateLogsDisplay() {
    if (!this.elements?.logs) return;

    const filteredLogs = this.getFilteredLogs();
    const logsHTML = this.generateLogsHTML(filteredLogs);

    this.elements.logs.innerHTML = logsHTML;

    // 自动滚动到底部
    this.scrollToBottom();
  }

  /**
   * 生成日志HTML
   */
  generateLogsHTML(logs) {
    if (logs.length === 0) {
      return '<div class="text-gray-500 text-center py-4">暂无日志记录</div>';
    }

    return logs.map(log => this.formatLogEntry(log)).join('');
  }

  /**
   * 格式化单条日志
   */
  formatLogEntry(log) {
    const typeConfig = this.logTypes[log.type] || this.logTypes['信息'];
    const timestamp = this.formatTimestamp(log.timestamp);

    // 转义HTML以防止XSS
    const safeMessage = this.escapeHtml(log.message);

    return `
      <div class="log-entry ${typeConfig.color} mb-1" data-log-type="${log.type}" data-timestamp="${log.timestamp}">
        <span class="text-xs opacity-70">[${timestamp}]</span>
        <span class="text-xs opacity-70">[${log.type}]</span>
        <span class="font-mono">${safeMessage}</span>
      </div>
    `;
  }

  /**
   * 格式化时间戳
   */
  formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
  }

  /**
   * HTML转义
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * 滚动到底部
   */
  scrollToBottom() {
    if (this.elements?.logs) {
      this.elements.logs.scrollTop = this.elements.logs.scrollHeight;
    }
  }

  /**
   * 获取日志统计
   */
  getLogStats() {
    const stats = {};
    Object.keys(this.logTypes).forEach(type => {
      stats[type] = this.logs.filter(log => log.type === type).length;
    });
    stats.total = this.logs.length;
    return stats;
  }

  /**
   * 导出日志
   */
  exportLogs(format = 'text') {
    if (format === 'json') {
      return JSON.stringify(this.logs, null, 2);
    }

    // 文本格式
    return this.logs.map(log => {
      const timestamp = this.formatTimestamp(log.timestamp);
      return `[${timestamp}][${log.type}] ${log.message}`;
    }).join('\n');
  }

  /**
   * 从状态恢复日志（状态管理器调用）
   */
  restoreLogsFromState() {
    if (this.logs.length > 0) {
      this.updateLogsDisplay();
      debugLogger.state('[DrcLogManager] 日志显示已从状态恢复');
    }
  }

  /**
   * 获取日志HTML（供状态管理器使用）
   */
  getLogsHTML() {
    return this.generateLogsHTML(this.getFilteredLogs());
  }

  /**
   * 添加DRC特定的系统日志
   */
  addSystemLog(message, level = 'info') {
    const typeMapping = {
      'info': '系统',
      'success': '成功',
      'warning': '警告',
      'error': '错误'
    };

    this.addLog(typeMapping[level] || '系统', message);
  }

  /**
   * 添加DRC状态变更日志
   */
  addStateChangeLog(oldState, newState, details = '') {
    const message = `DRC状态变更: ${oldState} → ${newState}${details ? ` (${details})` : ''}`;
    this.addLog('系统', message, { stateChange: true, oldState, newState });
  }

  /**
   * 添加配置变更日志
   */
  addConfigChangeLog(configType, changes) {
    const message = `${configType}配置已更新`;
    this.addLog('信息', message, { configChange: true, changes });
  }

  /**
   * 添加操作日志
   */
  addOperationLog(operation, result, duration = null) {
    const durationText = duration ? ` (耗时: ${duration}ms)` : '';
    const message = `${operation}: ${result}${durationText}`;
    const type = result.includes('成功') ? '成功' :
                 result.includes('失败') ? '错误' : '信息';

    this.addLog(type, message, { operation: true, operationName: operation });
  }

  /**
   * 搜索日志
   */
  searchLogs(query) {
    if (!query || query.trim() === '') {
      return this.logs;
    }

    const searchTerm = query.toLowerCase().trim();
    return this.logs.filter(log =>
      log.message.toLowerCase().includes(searchTerm) ||
      log.type.toLowerCase().includes(searchTerm)
    );
  }

  /**
   * 获取最近的错误日志
   */
  getRecentErrors(limit = 5) {
    return this.logs
      .filter(log => log.type === '错误')
      .slice(-limit)
      .reverse();
  }

  /**
   * 检查是否有错误日志
   */
  hasErrors() {
    return this.logs.some(log => log.type === '错误');
  }

  /**
   * 获取最后一条日志
   */
  getLastLog() {
    return this.logs.length > 0 ? this.logs[this.logs.length - 1] : null;
  }
}