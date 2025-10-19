/**
 * 云端控制UI更新器
 * 负责所有UI元素的更新和状态显示
 */

import { deviceContext } from '#lib/state.js';

export class UIUpdater {
  constructor() {
    this.elements = null; // 将由主控制器设置
  }

  /**
   * 设置DOM元素引用
   */
  setElements(elements) {
    this.elements = elements;
  }

  /**
   * 更新所有UI显示
   */
  updateUI(authStateManager) {
    this.updateStatusDisplay(authStateManager);
    this.updateControlKeysDisplay(authStateManager);
    this.updateButtonStates(authStateManager);
    this.updateMqttStatus();
  }

  /**
   * 更新状态显示和动画
   */
  updateStatusDisplay(authStateManager) {
    if (!this.elements?.statusText || !this.elements?.statusSpinner) return;

    const statusText = {
      'unauthorized': '未授权',
      'requesting': '请求中...',
      'authorized': '已授权'
    };

    this.elements.statusText.textContent = statusText[authStateManager.authStatus] || authStateManager.authStatus;

    // 显示/隐藏加载动画
    if (authStateManager.authStatus === 'requesting') {
      this.elements.statusSpinner.classList.remove('hidden');
    } else {
      this.elements.statusSpinner.classList.add('hidden');
    }

    // 更新颜色
    this.updateStatusColor(authStateManager.authStatus);
  }

  /**
   * 更新状态颜色
   */
  updateStatusColor(authStatus) {
    if (!this.elements?.cloudStatus) return;

    this.elements.cloudStatus.classList.remove('text-gray-600', 'text-yellow-600', 'text-green-600');

    if (authStatus === 'authorized') {
      this.elements.cloudStatus.classList.add('text-green-600');
    } else if (authStatus === 'requesting') {
      this.elements.cloudStatus.classList.add('text-yellow-600');
    } else {
      this.elements.cloudStatus.classList.add('text-gray-600');
    }
  }

  /**
   * 更新控制权显示
   */
  updateControlKeysDisplay(authStateManager) {
    if (!this.elements?.controlKeysDisplay) return;

    this.elements.controlKeysDisplay.textContent =
      authStateManager.controlKeys.length > 0 ? authStateManager.controlKeys.join(', ') : '-';
  }

  /**
   * 更新按钮状态和显示
   */
  updateButtonStates(authStateManager) {
    this.updateButtonVisibility(authStateManager.authStatus);
    this.updateRequestButtonState(authStateManager.authStatus);
  }

  /**
   * 更新按钮可见性
   */
  updateButtonVisibility(authStatus) {
    if (authStatus === 'authorized') {
      // 已授权：隐藏所有控制按钮
      this.hideElement(this.elements?.requestBtn);
      this.hideElement(this.elements?.confirmBtn);

    } else if (authStatus === 'requesting') {
      // 请求中：显示确认按钮，隐藏请求按钮
      this.hideElement(this.elements?.requestBtn);
      this.showElement(this.elements?.confirmBtn);

    } else {
      // 未授权：显示请求按钮，隐藏确认按钮
      this.showElement(this.elements?.requestBtn);
      this.hideElement(this.elements?.confirmBtn);
    }
  }

  /**
   * 更新请求按钮的加载状态
   */
  updateRequestButtonState(authStatus) {
    if (!this.elements?.requestBtn) return;

    const isRequesting = authStatus === 'requesting';
    this.elements.requestBtn.disabled = isRequesting;

    // 更新按钮内容和动画
    if (this.elements.requestBtnSpinner && this.elements.requestBtnIcon && this.elements.requestBtnText) {
      if (isRequesting) {
        this.showElement(this.elements.requestBtnSpinner);
        this.hideElement(this.elements.requestBtnIcon);
        this.elements.requestBtnText.textContent = '发送中...';
      } else {
        this.hideElement(this.elements.requestBtnSpinner);
        this.showElement(this.elements.requestBtnIcon);
        this.elements.requestBtnText.textContent = '请求云端控制授权';
      }
    }
  }

  /**
   * 更新MQTT连接状态显示
   */
  updateMqttStatus() {
    if (!this.elements?.mqttStatus) return;

    const currentSN = deviceContext.getCurrentDevice();

    if (!currentSN) {
      this.elements.mqttStatus.textContent = '未选择设备';
      this.elements.mqttStatus.classList.remove('text-green-600');
      this.elements.mqttStatus.classList.add('text-gray-600');
      return;
    }

    const connection = window.mqttManager?.getConnection(currentSN);

    if (connection && connection.isConnected) {
      this.elements.mqttStatus.textContent = '已连接';
      this.elements.mqttStatus.classList.add('text-green-600');
      this.elements.mqttStatus.classList.remove('text-gray-600');
    } else {
      this.elements.mqttStatus.textContent = '未连接';
      this.elements.mqttStatus.classList.add('text-gray-600');
      this.elements.mqttStatus.classList.remove('text-green-600');
    }
  }

  /**
   * 恢复输入框状态
   */
  restoreInputsFromState(authStateManager) {
    const userIdValue = authStateManager.userId || 'cloud_user_001';
    const userCallsignValue = authStateManager.userCallsign || 'CloudPilot';

    if (this.elements?.userIdInput) {
      this.elements.userIdInput.value = userIdValue;
    }

    if (this.elements?.userCallsignInput) {
      this.elements.userCallsignInput.value = userCallsignValue;
    }

    authStateManager.userId = userIdValue;
    authStateManager.userCallsign = userCallsignValue;
  }

  /**
   * 显示元素
   */
  showElement(element) {
    element?.classList.remove('hidden');
  }

  /**
   * 隐藏元素
   */
  hideElement(element) {
    element?.classList.add('hidden');
  }

  /**
   * 设置元素文本
   */
  setElementText(element, text) {
    if (element) {
      element.textContent = text;
    }
  }

  /**
   * 设置元素HTML
   */
  setElementHTML(element, html) {
    if (element) {
      element.innerHTML = html;
    }
  }

  /**
   * 切换元素类
   */
  toggleElementClass(element, className, condition) {
    if (!element) return;

    if (condition) {
      element.classList.add(className);
    } else {
      element.classList.remove(className);
    }
  }

  /**
   * 获取UI状态摘要（用于调试）
   */
  getUIStateSummary() {
    return {
      elementsFound: {
        requestBtn: !!this.elements?.requestBtn,
        confirmBtn: !!this.elements?.confirmBtn,
        cloudStatus: !!this.elements?.cloudStatus,
        mqttStatus: !!this.elements?.mqttStatus,
        logs: !!this.elements?.logs
      },
      visibility: {
        requestBtn: !this.elements?.requestBtn?.classList.contains('hidden'),
        confirmBtn: !this.elements?.confirmBtn?.classList.contains('hidden')
      }
    };
  }
}