import CONFIG from '../config/app-config.js';

// 终端日志管理
export class TerminalLogger {
  constructor(terminalName) {
    this.terminalName = terminalName;
    // 确保选择的是terminal-content而不是其他元素
    this.terminal = document.querySelector(`[data-terminal="${terminalName}"].terminal-content`);
    this.logCount = 0;
    
    if (!this.terminal) {
      console.error(`Terminal not found: ${terminalName}`);
    }
  }
  
  log(message, type = 'info') {
    if (!this.terminal) return;
    
    const timestamp = new Date().toLocaleTimeString([], CONFIG.terminal.timestampFormat);
    const logLine = document.createElement('div');
    logLine.className = `log-line ${type}`;
    logLine.innerHTML = `<span class="timestamp">[${timestamp}]</span>${message}`;
    
    this.terminal.appendChild(logLine);
    this.logCount++;
    
    // 限制日志行数，防止内存溢出
    if (this.logCount > CONFIG.terminal.maxLogLines) {
      this.terminal.removeChild(this.terminal.firstChild);
      this.logCount--;
    }
    
    // 自动滚动到底部
    this.terminal.scrollTop = this.terminal.scrollHeight;
    
    // 调试模式下输出到控制台
    if (CONFIG.debug.verbose) {
      console.log(`[${this.terminalName}] ${message}`);
    }
  }
  
  clear() {
    if (this.terminal) {
      const timestamp = new Date().toLocaleTimeString([], CONFIG.terminal.timestampFormat);
      this.terminal.innerHTML = `<div class="log-line info"><span class="timestamp">[${timestamp}]</span>[System] 日志已清除</div>`;
      this.logCount = 1;
    }
  }
}