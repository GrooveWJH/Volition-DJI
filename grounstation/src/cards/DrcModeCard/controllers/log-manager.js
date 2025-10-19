/**
 * DRC模式日志管理器 - 极简版
 */

import debugLogger from '#lib/debug.js';
import { deviceContext } from '#lib/state.js';

export class LogManager {
  constructor() {
    this.logsHTML = '<div class="text-gray-500" data-log-type="系统">[系统] DRC模式管理卡片已初始化</div>';
    this.elements = null;
  }

  setElements(elements) {
    this.elements = elements;
  }

  addLog(type, message) {
    const timestamp = new Date().toLocaleTimeString();
    const colorClass = this.getColorClass(type);

    const logEntry = `<div class="${colorClass}" data-log-type="${type}">[${timestamp}] [${type}] ${message}</div>`;
    this.logsHTML = (this.logsHTML || '') + logEntry;

    // 发送到调试系统
    const currentSN = deviceContext.getCurrentDevice();
    const level = type === '错误' ? 'error' : type === '警告' ? 'warn' : 'info';
    debugLogger[level](`[DRC${currentSN ? `-${currentSN}` : ''}] ${message}`);

    // 更新DOM
    this.updateDisplay();
  }

  getColorClass(type) {
    const map = {
      '成功': 'text-green-400',
      '错误': 'text-red-400',
      '警告': 'text-yellow-400',
      '信息': 'text-blue-400',
      '调试': 'text-gray-400',
      '心跳': 'text-purple-400',
      '系统': 'text-gray-500'
    };
    return map[type] || 'text-blue-400';
  }

  updateDisplay() {
    if (!this.elements?.logs) return;

    const filterValue = this.elements.logFilter?.value || 'all';

    if (filterValue === 'all') {
      this.elements.logs.innerHTML = this.logsHTML;
    } else {
      const temp = document.createElement('div');
      temp.innerHTML = this.logsHTML;
      const filtered = Array.from(temp.children)
        .filter(log => log.getAttribute('data-log-type') === filterValue)
        .map(log => log.outerHTML)
        .join('');
      this.elements.logs.innerHTML = filtered || `<div class="text-gray-500">没有 "${filterValue}" 类型的日志</div>`;
    }

    this.elements.logs.scrollTop = this.elements.logs.scrollHeight;
  }

  clearLogs() {
    this.logsHTML = '<div class="text-gray-500" data-log-type="系统">[系统] 日志已清空</div>';
    if (this.elements?.logs) {
      this.elements.logs.innerHTML = this.logsHTML;
    }
  }

  getLogsHTML() {
    return this.logsHTML;
  }
}
