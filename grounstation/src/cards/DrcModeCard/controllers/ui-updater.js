/**
 * DRC模式UI更新器
 * 负责所有DRC UI元素的更新和状态显示
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
  updateUI(drcStateManager) {
    this.updateButtonStates(drcStateManager);
    this.updateConfigurationDisplay(drcStateManager);
  }

  /**
   * 更新DRC状态显示
   */
  updateDrcStatusDisplay(drcStateManager) {
    if (!this.elements?.drcStatusText) return;

    const statusTexts = {
      'idle': '空闲',
      'checking': '检查中...',
      'configuring': '配置中...',
      'entering': '进入中...',
      'active': '已激活',
      'exiting': '退出中...',
      'error': '错误'
    };

    this.elements.drcStatusText.textContent = statusTexts[drcStateManager.drcStatus] || drcStateManager.drcStatus;

    // 更新颜色
    this.updateDrcStatusColor(drcStateManager.drcStatus);

    // 更新状态描述
    this.updateDrcStatusDescription(drcStateManager);

    // 显示/隐藏加载动画
    this.updateLoadingSpinner(drcStateManager.drcStatus);
  }

  /**
   * 更新DRC状态颜色
   */
  updateDrcStatusColor(drcStatus) {
    if (!this.elements?.drcStatus) return;

    this.elements.drcStatus.classList.remove(
      'text-gray-600', 'text-blue-600', 'text-yellow-600',
      'text-green-600', 'text-red-600'
    );

    const colorMap = {
      'idle': 'text-gray-600',
      'checking': 'text-blue-600',
      'configuring': 'text-blue-600',
      'entering': 'text-yellow-600',
      'active': 'text-green-600',
      'exiting': 'text-yellow-600',
      'error': 'text-red-600'
    };

    const colorClass = colorMap[drcStatus] || 'text-gray-600';
    this.elements.drcStatus.classList.add(colorClass);
  }

  /**
   * 更新DRC状态描述
   */
  updateDrcStatusDescription(drcStateManager) {
    if (!this.elements?.drcStatusDescription) return;

    const descriptions = {
      'idle': '准备就绪，等待进入DRC模式',
      'checking': '正在检查前置条件...',
      'configuring': '正在配置MQTT中继参数...',
      'entering': '正在发送DRC模式进入请求...',
      'active': `DRC模式已激活 (运行时间: ${drcStateManager.getDrcDuration()}秒)`,
      'exiting': '正在退出DRC模式...',
      'error': `错误: ${drcStateManager.lastError || '未知错误'}`
    };

    this.elements.drcStatusDescription.textContent = descriptions[drcStateManager.drcStatus] || '';
  }

  /**
   * 更新加载动画
   */
  updateLoadingSpinner(drcStatus) {
    if (!this.elements?.drcStatusSpinner) return;

    const showSpinner = ['checking', 'configuring', 'entering', 'exiting'].includes(drcStatus);

    if (showSpinner) {
      this.elements.drcStatusSpinner.classList.remove('hidden');
    } else {
      this.elements.drcStatusSpinner.classList.add('hidden');
    }
  }

  /**
   * 更新按钮显示状态
   */
  updateButtonStates(drcStateManager) {
    // 更新进入按钮文本
    if (this.elements?.enterBtnText) {
      this.elements.enterBtnText.textContent =
        drcStateManager.drcStatus === 'entering' ? '进入中...' : '进入DRC模式';
    }

    // 更新进入按钮加载状态
    const isEntering = drcStateManager.drcStatus === 'entering';
    if (isEntering) {
      this.showElement(this.elements?.enterBtnSpinner);
      this.hideElement(this.elements?.enterBtnIcon);
    } else {
      this.hideElement(this.elements?.enterBtnSpinner);
      this.showElement(this.elements?.enterBtnIcon);
    }

    // 更新退出按钮显示
    if (drcStateManager.drcStatus === 'active') {
      this.showElement(this.elements?.exitDrcBtn);
      if (this.elements?.exitBtnText) {
        this.elements.exitBtnText.textContent = '退出DRC模式';
      }
    } else {
      this.hideElement(this.elements?.exitDrcBtn);
    }
  }

  /**
   * 更新配置显示
   */
  updateConfigurationDisplay(drcStateManager) {
    this.updateMqttConfigDisplay(drcStateManager);
    this.updateFrequencyDisplay(drcStateManager);
  }

  /**
   * 更新MQTT配置显示
   */
  updateMqttConfigDisplay(drcStateManager) {
    const config = drcStateManager.mqttBrokerConfig;

    // 更新各个输入框的值
    if (this.elements?.mqttAddressInput) {
      this.elements.mqttAddressInput.value = config.address || '';
    }

    if (this.elements?.mqttClientIdInput) {
      this.elements.mqttClientIdInput.value = config.client_id || '';
    }

    if (this.elements?.mqttUsernameInput) {
      this.elements.mqttUsernameInput.value = config.username || '';
    }

    if (this.elements?.mqttPasswordInput) {
      this.elements.mqttPasswordInput.value = config.password || '';
    }

    if (this.elements?.mqttTlsToggle) {
      this.elements.mqttTlsToggle.checked = config.enable_tls !== false;
    }

    if (this.elements?.mqttAnonymousToggle) {
      this.elements.mqttAnonymousToggle.checked = config.anonymous === true;

      // 更新匿名模式状态
      this.updateAnonymousFieldsState(config.anonymous === true);
    }
  }

  /**
   * 更新匿名模式字段状态
   */
  updateAnonymousFieldsState(isAnonymous) {
    if (this.elements?.mqttUsernameInput) {
      this.elements.mqttUsernameInput.disabled = isAnonymous;
      if (isAnonymous) {
        this.elements.mqttUsernameInput.classList.add('bg-gray-100');
      } else {
        this.elements.mqttUsernameInput.classList.remove('bg-gray-100');
      }
    }

    if (this.elements?.mqttPasswordInput) {
      this.elements.mqttPasswordInput.disabled = isAnonymous;
      if (isAnonymous) {
        this.elements.mqttPasswordInput.classList.add('bg-gray-100');
      } else {
        this.elements.mqttPasswordInput.classList.remove('bg-gray-100');
      }
    }
  }

  /**
   * 更新频率显示
   */
  updateFrequencyDisplay(drcStateManager) {
    if (this.elements?.osdFrequencySlider) {
      this.elements.osdFrequencySlider.value = drcStateManager.osdFrequency;
    }

    if (this.elements?.osdFrequencyValue) {
      this.elements.osdFrequencyValue.textContent = `${drcStateManager.osdFrequency}Hz`;
    }

    if (this.elements?.hsiFrequencySlider) {
      this.elements.hsiFrequencySlider.value = drcStateManager.hsiFrequency;
    }

    if (this.elements?.hsiFrequencyValue) {
      this.elements.hsiFrequencyValue.textContent = `${drcStateManager.hsiFrequency}Hz`;
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
   * 更新客户端ID建议
   */
  updateClientIdSuggestion(deviceSN) {
    if (deviceSN && this.elements?.mqttClientIdInput && !this.elements.mqttClientIdInput.value) {
      this.elements.mqttClientIdInput.value = `drc-${deviceSN}`;
    }
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
   * 显示操作结果提示
   */
  showOperationResult(success, message) {
    if (!this.elements?.operationResult) return;

    this.elements.operationResult.textContent = message;
    this.elements.operationResult.classList.remove('hidden', 'text-green-600', 'text-red-600');
    this.elements.operationResult.classList.add(success ? 'text-green-600' : 'text-red-600');

    // 3秒后自动隐藏
    setTimeout(() => {
      this.hideElement(this.elements.operationResult);
    }, 3000);
  }

}