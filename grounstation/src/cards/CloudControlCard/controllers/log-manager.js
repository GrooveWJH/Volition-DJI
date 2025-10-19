/**
 * 云端控制日志管理器
 * 负责日志记录、过滤、显示和与中央调试系统的集成
 */

import { deviceContext } from '#lib/state.js';
import debugLogger from '#lib/debug.js';

export class LogManager {
  constructor() {
    this.logsHTML = '<div class="text-gray-500" data-log-type="系统">[系统] 云端控制授权卡片已初始化</div>';
    this.elements = null; // 将由主控制器设置
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
  addLog(type, message) {
    const timestamp = new Date().toLocaleTimeString();
    const logClass = this.getLogClass(type);

    const logEntry = `<div class="${logClass}" data-log-type="${type}">[${timestamp}] [${type}] ${message}</div>`;

    // 更新本地日志（自动保存到状态）
    this.logsHTML = (this.logsHTML || '') + logEntry;

    // 发送到中央调试系统
    this.sendToCentralDebug(type, message);

    // 更新DOM显示
    this.updateLogsDisplay();
  }

  /**
   * 获取日志样式类
   */
  getLogClass(type) {
    const classMap = {
      '成功': 'text-green-400',
      '错误': 'text-red-400',
      '警告': 'text-yellow-400',
      '帮助': 'text-blue-300',
      '提示': 'text-cyan-400',
      '信息': 'text-blue-400',
      '调试': 'text-gray-400',
      '系统': 'text-gray-500'
    };

    return classMap[type] || 'text-blue-400';
  }

  /**
   * 发送日志到中央调试系统
   */
  sendToCentralDebug(type, message) {
    const currentSN = deviceContext.getCurrentDevice();
    const logLevel = this.mapToDebugLevel(type);

    debugLogger[logLevel](`[CloudControl${currentSN ? `-${currentSN}` : ''}] ${message}`, {
      source: 'CloudControlCard',
      device: currentSN,
      type: type
    });
  }

  /**
   * 映射日志类型到调试级别
   */
  mapToDebugLevel(type) {
    const levelMap = {
      '错误': 'error',
      '警告': 'warn',
      '调试': 'debug',
      '成功': 'info',
      '信息': 'info',
      '帮助': 'info',
      '提示': 'info',
      '系统': 'info'
    };

    return levelMap[type] || 'info';
  }

  /**
   * 更新日志显示
   */
  updateLogsDisplay() {
    if (!this.elements?.logs) return;

    const filterValue = this.elements.logFilter?.value || 'all';

    if (filterValue === 'all') {
      this.elements.logs.innerHTML = this.logsHTML;
    } else {
      this.filterLogs(filterValue);
    }

    this.elements.logs.scrollTop = this.elements.logs.scrollHeight;
  }

  /**
   * 过滤日志显示
   */
  filterLogs(filterType) {
    if (!this.elements?.logs || !this.logsHTML) return;

    if (filterType === 'all') {
      this.elements.logs.innerHTML = this.logsHTML;
    } else {
      // 创建临时DOM来过滤
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = this.logsHTML;

      const filteredLogs = Array.from(tempDiv.children)
        .filter(log => log.getAttribute('data-log-type') === filterType)
        .map(log => log.outerHTML)
        .join('');

      this.elements.logs.innerHTML = filteredLogs ||
        `<div class="text-gray-500">没有找到 "${filterType}" 类型的日志</div>`;
    }

    this.elements.logs.scrollTop = this.elements.logs.scrollHeight;
  }

  /**
   * 清空日志
   */
  clearLogs() {
    this.logsHTML = '<div class="text-gray-500" data-log-type="系统">[系统] 日志已清空</div>';

    if (this.elements?.logs) {
      this.elements.logs.innerHTML = this.logsHTML;
    }

    debugLogger.info('[CloudControl] 日志已清空', { source: 'CloudControlCard' });
  }

  /**
   * 从状态恢复日志显示
   */
  restoreLogsFromState() {
    if (this.elements?.logs && this.logsHTML) {
      this.updateLogsDisplay();
    }
  }

  /**
   * 获取日志统计信息
   */
  getLogStats() {
    if (!this.logsHTML) return { total: 0 };

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = this.logsHTML;
    const logs = Array.from(tempDiv.children);

    const stats = {
      total: logs.length,
      错误: logs.filter(log => log.getAttribute('data-log-type') === '错误').length,
      警告: logs.filter(log => log.getAttribute('data-log-type') === '警告').length,
      成功: logs.filter(log => log.getAttribute('data-log-type') === '成功').length,
      信息: logs.filter(log => log.getAttribute('data-log-type') === '信息').length,
      帮助: logs.filter(log => log.getAttribute('data-log-type') === '帮助').length,
      提示: logs.filter(log => log.getAttribute('data-log-type') === '提示').length
    };

    return stats;
  }

  /**
   * 设置日志内容（用于状态恢复）
   */
  setLogsHTML(html) {
    this.logsHTML = html;
    this.updateLogsDisplay();
  }

  /**
   * 获取日志内容（用于状态保存）
   */
  getLogsHTML() {
    return this.logsHTML;
  }

  /**
   * 导出日志为文本
   */
  exportLogs() {
    if (!this.logsHTML) return '';

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = this.logsHTML;

    return Array.from(tempDiv.children)
      .map(log => log.textContent)
      .join('\n');
  }

  /**
   * 添加批量日志
   */
  addBatchLogs(logs) {
    logs.forEach(({ type, message }) => {
      this.addLog(type, message);
    });
  }
}