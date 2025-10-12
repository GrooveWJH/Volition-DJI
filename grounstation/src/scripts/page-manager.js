/**
 * 主页面管理脚本
 * 处理页面交互和配置管理功能
 */

/**
 * 切换禁用模块显示
 */
export function toggleDisabledModules() {
  const content = document.getElementById('disabledModulesContent');
  const header = document.getElementById('disabledModulesHeader');
  const icon = document.getElementById('toggleIcon');

  if (!content || !header || !icon) {
    console.warn('Disabled modules toggle elements missing');
    return;
  }
  
  if (content.classList.contains('hidden')) {
    content.classList.remove('hidden');
    header.classList.add('bg-gray-50');
    icon.style.transform = 'rotate(180deg)';
  } else {
    content.classList.add('hidden');
    header.classList.remove('bg-gray-50');
    icon.style.transform = 'rotate(0deg)';
  }
}

/**
 * 显示配置管理菜单
 */
export function showConfigMenu() {
  const menu = `
    <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; align-items: center; justify-content: center;" onclick="this.remove()">
      <div style="background: white; padding: 24px; border-radius: 8px; max-width: 400px; width: 90%; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);" onclick="event.stopPropagation()">
        <h3 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #1f2937;">配置管理</h3>
        
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <button onclick="showStorageStats()" style="width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
            📊 查看存储统计
          </button>
          
          <button onclick="exportConfig()" style="width: 100%; padding: 12px; background: #10b981; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
            📥 导出配置
          </button>
          
          <button onclick="importConfig()" style="width: 100%; padding: 12px; background: #8b5cf6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
            📤 导入配置
          </button>
          
          <button onclick="if(confirm('确定要清除所有保存的配置吗？')) clearAllConfig()" style="width: 100%; padding: 12px; background: #ef4444; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
            🗑️ 清除所有配置
          </button>
          
          <button onclick="this.closest('[style*=\"position: fixed\"]').remove()" style="width: 100%; padding: 12px; background: #6b7280; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
            关闭
          </button>
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', menu);
}

/**
 * 初始化页面管理器
 */
export function initializePageManager() {
  // 将函数暴露到全局作用域以便HTML onclick使用
  window.toggleDisabledModules = toggleDisabledModules;
  window.showConfigMenu = showConfigMenu;
  
  console.log('页面管理器已初始化');
}

// 自动初始化
if (typeof window !== 'undefined') {
  initializePageManager();
}