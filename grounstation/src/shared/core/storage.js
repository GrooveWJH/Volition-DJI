/**
 * 地面站localStorage管理工具
 * 统一管理所有输入框的本地存储功能
 */

class GroundStationStorage {
  constructor() {
    this.PREFIX = 'groundstation_';
    this.initialized = false;
  }

  // 初始化所有具有storage-key的输入框
  initialize() {
    if (this.initialized) return;
    
    document.addEventListener('DOMContentLoaded', () => {
      this.setupAutoSave();
      this.loadSavedValues();
      this.initialized = true;
      console.log('GroundStation localStorage initialized');
    });
  }

  // 设置自动保存监听器
  setupAutoSave() {
    const inputs = document.querySelectorAll('[data-storage-key]');
    
    inputs.forEach(input => {
      const key = this.getStorageKey(input.getAttribute('data-storage-key'));
      
      // 监听输入变化，自动保存
      input.addEventListener('input', () => {
        this.saveValue(key, input.value);
        this.triggerCustomEvents(input);
      });
      
      // 监听失焦事件，确保完整性
      input.addEventListener('blur', () => {
        this.saveValue(key, input.value);
      });
    });
  }

  // 加载所有保存的值
  loadSavedValues() {
    const inputs = document.querySelectorAll('[data-storage-key]');
    
    inputs.forEach(input => {
      const key = this.getStorageKey(input.getAttribute('data-storage-key'));
      const savedValue = this.getValue(key);
      
      if (savedValue !== null) {
        input.value = savedValue;
        this.triggerCustomEvents(input);
      }
    });
  }

  // 触发自定义事件（如URL预览更新等）
  triggerCustomEvents(input) {
    const storageKey = input.getAttribute('data-storage-key');
    
    // HTTP端口变化时更新URL预览
    if (storageKey === 'http-port') {
      const urlPreview = document.getElementById('login-url-preview');
      if (urlPreview) {
        urlPreview.textContent = `http://localhost:${input.value}/login`;
      }
    }
    
    // 视频主机变化时可以触发其他更新
    if (storageKey === 'video-host') {
      // 可以在这里添加其他相关更新
      const playerId = input.getAttribute('data-player-id');
      if (window.updateHostConfig && playerId) {
        window.updateHostConfig(playerId, input.value);
      }
    }
  }

  // 构建完整的存储键名
  getStorageKey(key) {
    return `${this.PREFIX}${key}`;
  }

  // 保存值到localStorage
  saveValue(key, value) {
    try {
      localStorage.setItem(key, value);
      return true;
    } catch (error) {
      console.error('Failed to save to localStorage:', error);
      return false;
    }
  }

  // 从localStorage获取值
  getValue(key) {
    try {
      return localStorage.getItem(key);
    } catch (error) {
      console.error('Failed to get from localStorage:', error);
      return null;
    }
  }

  // 删除特定键
  removeValue(key) {
    try {
      localStorage.removeItem(this.getStorageKey(key));
      return true;
    } catch (error) {
      console.error('Failed to remove from localStorage:', error);
      return false;
    }
  }

  // 清除特定类别的配置
  clearCategory(category) {
    const prefix = `${this.PREFIX}${category}`;
    const keys = Object.keys(localStorage).filter(key => key.startsWith(prefix));
    
    keys.forEach(key => localStorage.removeItem(key));
    return keys.length;
  }

  // 清除所有地面站配置
  clearAll() {
    const keys = Object.keys(localStorage).filter(key => key.startsWith(this.PREFIX));
    keys.forEach(key => localStorage.removeItem(key));
    return keys.length;
  }

  // 导出所有配置
  exportConfig() {
    const config = {};
    const keys = Object.keys(localStorage).filter(key => key.startsWith(this.PREFIX));
    
    keys.forEach(key => {
      const shortKey = key.replace(this.PREFIX, '');
      config[shortKey] = localStorage.getItem(key);
    });
    
    return config;
  }

  // 导入配置
  importConfig(config) {
    let imported = 0;
    
    Object.entries(config).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        this.saveValue(this.getStorageKey(key), value);
        imported++;
      }
    });
    
    // 重新加载页面应用配置
    if (imported > 0) {
      window.location.reload();
    }
    
    return imported;
  }

  // 获取存储统计信息
  getStats() {
    const keys = Object.keys(localStorage).filter(key => key.startsWith(this.PREFIX));
    const categories = {};
    
    keys.forEach(key => {
      const shortKey = key.replace(this.PREFIX, '');
      const category = shortKey.split('-')[0];
      
      if (!categories[category]) {
        categories[category] = 0;
      }
      categories[category]++;
    });
    
    return {
      total: keys.length,
      categories: categories,
      size: new Blob([JSON.stringify(this.exportConfig())]).size
    };
  }
}

// 创建全局实例
window.GroundStationStorage = new GroundStationStorage();

// 自动初始化
window.GroundStationStorage.initialize();

// 提供便捷的全局函数
window.clearAllConfig = function() {
  const count = window.GroundStationStorage.clearAll();
  alert(`已清除 ${count} 项配置，即将刷新页面`);
  window.location.reload();
};

window.exportConfig = function() {
  const config = window.GroundStationStorage.exportConfig();
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = `groundstation-config-${new Date().toISOString().split('T')[0]}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

window.importConfig = function() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  
  input.onchange = function(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
      try {
        const config = JSON.parse(e.target.result);
        const count = window.GroundStationStorage.importConfig(config);
        alert(`已导入 ${count} 项配置`);
      } catch (error) {
        alert('配置文件格式错误');
      }
    };
    reader.readAsText(file);
  };
  
  input.click();
};

window.showStorageStats = function() {
  const stats = window.GroundStationStorage.getStats();
  console.log('地面站存储统计:', stats);
  alert(`存储统计:\n总计: ${stats.total} 项\n分类: ${Object.entries(stats.categories).map(([k,v]) => `${k}(${v})`).join(', ')}\n大小: ${stats.size} 字节`);
};

// 导出给其他模块使用
export const globalStorage = window.GroundStationStorage;