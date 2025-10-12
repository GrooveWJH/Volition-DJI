/**
 * 调试页面日志工具
 * 处理日志记录和状态更新
 */

export class DebugLogger {
  constructor() {
    this.logsElement = null;
    this.statusElement = null;
  }

  initialize() {
    this.logsElement = document.getElementById('logs');
    this.statusElement = document.getElementById('connection-status');
  }

  log(message, type = 'info') {
    if (!this.logsElement) this.initialize();
    
    const time = new Date().toLocaleTimeString();
    const logLine = document.createElement('div');
    logLine.className = `log-${type}`;
    logLine.textContent = `[${time}] ${message}`;
    
    this.logsElement.appendChild(logLine);
    this.logsElement.scrollTop = this.logsElement.scrollHeight;
    
    console.log(`[${type.toUpperCase()}] ${message}`);
  }

  clearLogs() {
    if (!this.logsElement) this.initialize();
    this.logsElement.innerHTML = '';
  }

  updateStatus(status, text) {
    if (!this.statusElement) this.initialize();
    this.statusElement.className = `status status-${status}`;
    this.statusElement.textContent = text;
  }
}

// 全局实例
export const debugLogger = new DebugLogger();