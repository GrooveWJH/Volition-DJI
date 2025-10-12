/**
 * DRC工作流管理器
 * 管理DRC操作的工作流步骤和状态转换
 */

import { DrcWorkflowSteps } from './drc-enums.js';

/**
 * 工作流步骤定义
 */
export const WorkflowStepDefinitions = {
  [DrcWorkflowSteps.IDLE]: {
    title: '待机状态',
    description: '系统处于空闲状态，等待用户操作',
    icon: 'radio_button_unchecked',
    color: 'gray',
    allowedNextSteps: [DrcWorkflowSteps.AUTH_REQUEST],
    actions: ['start']
  },
  
  [DrcWorkflowSteps.AUTH_REQUEST]: {
    title: '请求授权',
    description: '正在向DJI服务器请求DRC授权',
    icon: 'sync',
    color: 'blue',
    allowedNextSteps: [DrcWorkflowSteps.AUTH_PENDING, DrcWorkflowSteps.ERROR],
    actions: ['cancel'],
    isLoading: true
  },
  
  [DrcWorkflowSteps.AUTH_PENDING]: {
    title: '等待确认',
    description: '授权请求已发送，等待手动确认',
    icon: 'pending',
    color: 'yellow',
    allowedNextSteps: [DrcWorkflowSteps.AUTH_CONFIRMED, DrcWorkflowSteps.IDLE],
    actions: ['confirm', 'cancel'],
    requiresUserAction: true
  },
  
  [DrcWorkflowSteps.AUTH_CONFIRMED]: {
    title: '授权确认',
    description: '授权已确认，准备进入DRC模式',
    icon: 'check_circle',
    color: 'green',
    allowedNextSteps: [DrcWorkflowSteps.ENTERING_DRC],
    actions: [],
    autoAdvance: true
  },
  
  [DrcWorkflowSteps.ENTERING_DRC]: {
    title: '进入DRC',
    description: '正在建立DRC连接并激活远程控制',
    icon: 'flight_takeoff',
    color: 'blue',
    allowedNextSteps: [DrcWorkflowSteps.DRC_ACTIVE, DrcWorkflowSteps.ERROR],
    actions: [],
    isLoading: true
  },
  
  [DrcWorkflowSteps.DRC_ACTIVE]: {
    title: 'DRC已激活',
    description: 'DRC模式已成功激活，可以进行远程控制',
    icon: 'radio_button_checked',
    color: 'green',
    allowedNextSteps: [DrcWorkflowSteps.EXITING_DRC],
    actions: ['exit'],
    isActive: true
  },
  
  [DrcWorkflowSteps.EXITING_DRC]: {
    title: '退出DRC',
    description: '正在退出DRC模式并断开连接',
    icon: 'flight_land',
    color: 'orange',
    allowedNextSteps: [DrcWorkflowSteps.IDLE, DrcWorkflowSteps.ERROR],
    actions: [],
    isLoading: true
  },
  
  [DrcWorkflowSteps.ERROR]: {
    title: '错误状态',
    description: '操作过程中发生错误',
    icon: 'error',
    color: 'red',
    allowedNextSteps: [DrcWorkflowSteps.IDLE],
    actions: ['retry', 'reset'],
    isError: true
  }
};

/**
 * DRC工作流管理器类
 */
export class DrcWorkflowManager {
  constructor() {
    this.currentStep = DrcWorkflowSteps.IDLE;
    this.stepHistory = [];
    this.listeners = new Set();
  }

  /**
   * 添加状态监听器
   * @param {Function} listener - 监听器函数
   */
  addListener(listener) {
    this.listeners.add(listener);
  }

  /**
   * 移除状态监听器
   * @param {Function} listener - 监听器函数
   */
  removeListener(listener) {
    this.listeners.delete(listener);
  }

  /**
   * 获取当前步骤定义
   * @returns {Object} 步骤定义
   */
  getCurrentStepDefinition() {
    return WorkflowStepDefinitions[this.currentStep];
  }

  /**
   * 获取步骤定义
   * @param {string} step - 步骤名称
   * @returns {Object} 步骤定义
   */
  getStepDefinition(step) {
    return WorkflowStepDefinitions[step];
  }

  /**
   * 检查是否可以转换到指定步骤
   * @param {string} targetStep - 目标步骤
   * @returns {boolean} 是否可以转换
   */
  canTransitionTo(targetStep) {
    const currentDef = this.getCurrentStepDefinition();
    return currentDef && currentDef.allowedNextSteps.includes(targetStep);
  }

  /**
   * 转换到指定步骤
   * @param {string} targetStep - 目标步骤
   * @param {Object} context - 上下文信息
   * @returns {boolean} 是否成功转换
   */
  transitionTo(targetStep, context = {}) {
    if (!this.canTransitionTo(targetStep)) {
      console.warn(`Cannot transition from ${this.currentStep} to ${targetStep}`);
      return false;
    }

    const oldStep = this.currentStep;
    this.currentStep = targetStep;
    
    // 记录历史
    this.stepHistory.push({
      from: oldStep,
      to: targetStep,
      timestamp: Date.now(),
      context
    });

    // 通知监听器
    this.notifyListeners(oldStep, targetStep, context);
    
    return true;
  }

  /**
   * 重置工作流
   */
  reset() {
    const oldStep = this.currentStep;
    this.currentStep = DrcWorkflowSteps.IDLE;
    this.stepHistory = [];
    this.notifyListeners(oldStep, this.currentStep, { reset: true });
  }

  /**
   * 获取可用操作
   * @returns {string[]} 可用操作列表
   */
  getAvailableActions() {
    const currentDef = this.getCurrentStepDefinition();
    return currentDef ? currentDef.actions : [];
  }

  /**
   * 检查是否需要用户操作
   * @returns {boolean} 是否需要用户操作
   */
  requiresUserAction() {
    const currentDef = this.getCurrentStepDefinition();
    return currentDef ? !!currentDef.requiresUserAction : false;
  }

  /**
   * 检查是否处于加载状态
   * @returns {boolean} 是否处于加载状态
   */
  isLoading() {
    const currentDef = this.getCurrentStepDefinition();
    return currentDef ? !!currentDef.isLoading : false;
  }

  /**
   * 检查是否处于错误状态
   * @returns {boolean} 是否处于错误状态
   */
  isError() {
    const currentDef = this.getCurrentStepDefinition();
    return currentDef ? !!currentDef.isError : false;
  }

  /**
   * 检查是否处于活动状态
   * @returns {boolean} 是否处于活动状态
   */
  isActive() {
    const currentDef = this.getCurrentStepDefinition();
    return currentDef ? !!currentDef.isActive : false;
  }

  /**
   * 获取步骤进度百分比
   * @returns {number} 进度百分比 (0-100)
   */
  getProgressPercentage() {
    const stepOrder = [
      DrcWorkflowSteps.IDLE,
      DrcWorkflowSteps.AUTH_REQUEST,
      DrcWorkflowSteps.AUTH_PENDING,
      DrcWorkflowSteps.AUTH_CONFIRMED,
      DrcWorkflowSteps.ENTERING_DRC,
      DrcWorkflowSteps.DRC_ACTIVE
    ];
    
    const currentIndex = stepOrder.indexOf(this.currentStep);
    if (currentIndex === -1) return 0;
    
    return Math.round((currentIndex / (stepOrder.length - 1)) * 100);
  }

  /**
   * 获取工作流状态摘要
   * @returns {Object} 状态摘要
   */
  getStatusSummary() {
    const currentDef = this.getCurrentStepDefinition();
    
    return {
      currentStep: this.currentStep,
      definition: currentDef,
      availableActions: this.getAvailableActions(),
      requiresUserAction: this.requiresUserAction(),
      isLoading: this.isLoading(),
      isError: this.isError(),
      isActive: this.isActive(),
      progress: this.getProgressPercentage(),
      stepHistory: this.stepHistory.slice(-5) // 最近5个步骤
    };
  }

  /**
   * 通知所有监听器
   * @private
   */
  notifyListeners(oldStep, newStep, context) {
    for (const listener of this.listeners) {
      try {
        listener(oldStep, newStep, context);
      } catch (error) {
        console.error('Error in workflow listener:', error);
      }
    }
  }
}

/**
 * 创建步骤进度指示器的HTML
 * @param {string} currentStep - 当前步骤
 * @returns {string} HTML字符串
 */
export function createStepProgressHTML(currentStep) {
  const steps = [
    DrcWorkflowSteps.IDLE,
    DrcWorkflowSteps.AUTH_REQUEST,
    DrcWorkflowSteps.AUTH_PENDING,
    DrcWorkflowSteps.AUTH_CONFIRMED,
    DrcWorkflowSteps.ENTERING_DRC,
    DrcWorkflowSteps.DRC_ACTIVE
  ];

  const currentIndex = steps.indexOf(currentStep);
  
  return steps.map((step, index) => {
    const def = WorkflowStepDefinitions[step];
    const isActive = step === currentStep;
    const isCompleted = index < currentIndex;
    
    let statusClass = 'text-gray-400';
    if (isCompleted) statusClass = 'text-green-500';
    else if (isActive) statusClass = `text-${def.color}-500`;
    
    return `
      <div class="flex items-center ${index < steps.length - 1 ? 'mb-2' : ''}">
        <div class="flex-shrink-0 w-8 h-8 rounded-full border-2 ${
          isActive ? `border-${def.color}-500 bg-${def.color}-100` :
          isCompleted ? 'border-green-500 bg-green-100' :
          'border-gray-300 bg-gray-100'
        } flex items-center justify-center">
          <span class="material-symbols-outlined text-sm ${statusClass}">
            ${isCompleted ? 'check' : def.icon}
          </span>
        </div>
        <div class="ml-3 flex-1">
          <div class="text-sm font-medium ${isActive ? `text-${def.color}-900` : 'text-gray-900'}">
            ${def.title}
          </div>
          ${isActive ? `<div class="text-xs text-${def.color}-600">${def.description}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');
}