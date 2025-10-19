/**
 * DRC模式错误处理器
 * 负责DRC模式相关的错误检测、验证、恢复建议和消息处理
 */

import { deviceContext } from '#lib/state.js';
import debugLogger from '#lib/debug.js';

export class ErrorHandler {
  constructor(logManager) {
    this.logManager = logManager;
  }

  /**
   * 检查是否可以进入DRC模式
   */
  validateDrcEntry(drcStateManager, authStatus, deviceSN) {
    const errors = [];

    // 检查CloudControl授权状态
    if (authStatus !== 'authorized') {
      errors.push({
        type: 'auth_required',
        message: '进入DRC模式前需要先完成云端控制授权'
      });
    }

    // 检查设备连接状态
    if (!deviceSN) {
      errors.push({
        type: 'device_required',
        message: '未选择设备'
      });
    } else if (!this.isDeviceOnline(deviceSN)) {
      errors.push({
        type: 'device_offline',
        message: '设备未连接，请检查MQTT连接状态'
      });
    }

    // 检查MQTT配置
    if (!drcStateManager.prerequisites.configValid) {
      errors.push({
        type: 'config_invalid',
        message: 'MQTT中继配置不完整或无效'
      });
    }

    // 检查DRC状态
    if (!drcStateManager.canEnterDrcMode()) {
      errors.push({
        type: 'drc_not_ready',
        message: `当前DRC状态(${drcStateManager.drcStatus})不允许进入DRC模式`
      });
    }

    return {
      isValid: errors.length === 0,
      errors: errors
    };
  }

  /**
   * 检查设备是否在线
   */
  isDeviceOnline(sn) {
    const connection = window.mqttManager?.getConnection(sn);
    return connection && connection.isConnected;
  }

  /**
   * 处理DRC进入请求回复
   */
  handleDrcEnterReply(msg, drcStateManager) {
    const result = msg.data?.result;

    // 验证是否是当前请求的回复
    if (!drcStateManager.isValidTid(msg.tid)) {
      this.logManager.addLog('调试', `收到其他请求的回复，忽略 (TID: ${msg.tid})`);
      return { shouldUpdateUI: false };
    }

    if (result === 0) {
      // 成功进入DRC模式
      drcStateManager.setDrcActive();
      const duration = drcStateManager.getDrcDuration();

      this.logManager.addLog('成功', '✓ 已成功进入DRC模式');
      this.logManager.addLog('信息', `DRC模式已激活，可以开始指令飞行控制`);
      return { shouldUpdateUI: true };

    } else {
      // 进入失败
      drcStateManager.setError(`DRC模式进入失败 (result: ${result})`);
      this.logManager.addLog('错误', `DRC模式进入失败 (result: ${result})`);

      // 提供具体的错误信息
      this.provideDrcErrorAdvice(result);
      return { shouldUpdateUI: true };
    }
  }

  /**
   * 处理DRC退出请求回复
   */
  handleDrcExitReply(msg, drcStateManager) {
    const result = msg.data?.result;

    if (result === 0) {
      // 成功退出DRC模式
      drcStateManager.resetDrcState();
      this.logManager.addLog('成功', '✓ 已退出DRC模式');
      this.logManager.addLog('信息', 'DRC模式已关闭');
      return { shouldUpdateUI: true };

    } else {
      // 退出失败
      this.logManager.addLog('错误', `DRC模式退出失败 (result: ${result})`);
      return { shouldUpdateUI: false };
    }
  }

  /**
   * 处理服务调用错误
   */
  handleServiceError(error, result) {
    let errorType = 'drc_failed';
    let message = `DRC操作失败: ${result?.error?.message || error?.message || '未知错误'}`;

    if (result?.error?.code === 'TIMEOUT' || error?.name === 'TimeoutError') {
      errorType = 'timeout';
      message = 'DRC请求超时，请检查网络连接和设备状态';
    } else if (result?.error?.code === 'CONNECTION_FAILED' || error?.name === 'NetworkError') {
      errorType = 'connection_failed';
      message = 'MQTT连接失败，无法发送DRC请求';
    }

    this.logManager.addLog('错误', message);
    this.showErrorAdvice(errorType);

    return { errorType, message };
  }

  /**
   * 处理MQTT连接变化
   */
  handleMqttConnectionChange(connectionInfo, drcStateManager) {
    if (!connectionInfo) return { shouldUpdateUI: false };

    const currentSN = deviceContext.getCurrentDevice();
    if (connectionInfo.sn !== currentSN) return { shouldUpdateUI: false };

    // 更新连接状态
    drcStateManager.updateMqttConnectionStatus(connectionInfo.connected);

    if (connectionInfo.connected) {
      this.logManager.addLog('信息', `设备 ${currentSN} MQTT连接已建立`);
    } else {
      this.logManager.addLog('警告', `设备 ${currentSN} MQTT连接已断开`);

      // 如果在DRC模式中断开连接，记录警告
      if (drcStateManager.drcStatus === 'active') {
        this.logManager.addLog('警告', 'DRC模式运行期间连接断开，可能影响指令传输');
      } else if (drcStateManager.drcStatus === 'entering') {
        this.logManager.addLog('错误', 'DRC模式进入期间连接断开，已取消操作');
        drcStateManager.setError('连接断开');
        return { shouldUpdateUI: true };
      }
    }

    return { shouldUpdateUI: true };
  }

  /**
   * 提供DRC特定的错误建议
   */
  provideDrcErrorAdvice(result) {
    const adviceMap = {
      1: '设备拒绝了DRC模式请求，请检查设备状态',
      2: '设备不支持DRC模式功能',
      3: '设备当前状态不允许进入DRC模式',
      4: 'MQTT中继配置无效，请检查配置参数',
      5: '设备资源不足，无法启动DRC模式'
    };

    const advice = adviceMap[result];
    if (advice) {
      this.logManager.addLog('提示', advice);
    }
  }

  /**
   * 获取错误恢复建议
   */
  getErrorRecoveryAdvice(errorType) {
    const advice = {
      'auth_required': [
        '1. 先到云端控制授权卡片完成授权',
        '2. 确认授权状态显示为"已授权"',
        '3. 再回到DRC模式管理进行操作'
      ],
      'device_offline': [
        '1. 确认设备电源已开启',
        '2. 检查设备网络连接',
        '3. 确认MQTT连接状态正常'
      ],
      'config_invalid': [
        '1. 检查MQTT中继服务器地址格式',
        '2. 确认用户名和密码正确',
        '3. 使用"测试连接"验证配置'
      ],
      'drc_failed': [
        '1. 检查设备是否支持DRC模式',
        '2. 确认设备当前状态正常',
        '3. 重新尝试进入DRC模式'
      ],
      'timeout': [
        '1. 检查网络连接质量',
        '2. 确认设备响应正常',
        '3. 适当增加超时时间后重试'
      ],
      'connection_failed': [
        '1. 检查MQTT连接状态',
        '2. 确认网络连接正常',
        '3. 重新连接设备后重试'
      ]
    };

    return advice[errorType] || ['请联系技术支持获取帮助'];
  }

  /**
   * 显示错误恢复建议
   */
  showErrorAdvice(errorType) {
    // 删除故障排除建议，避免日志过于冗长
    // const advice = this.getErrorRecoveryAdvice(errorType);
    // this.logManager.addLog('帮助', '故障排除建议:');
    // advice.forEach(tip => {
    //   this.logManager.addLog('提示', tip);
    // });
  }

  /**
   * 验证MQTT中继配置
   */
  validateMqttBrokerConfig(config) {
    const errors = [];

    if (!config.address) {
      errors.push({ type: 'config_invalid', message: 'MQTT服务器地址不能为空' });
    }

    if (!config.client_id) {
      errors.push({ type: 'config_invalid', message: '客户端ID不能为空' });
    }

    // 支持匿名模式，用户名和密码可选
    // if (!config.username) {
    //   errors.push({ type: 'config_invalid', message: 'MQTT用户名不能为空' });
    // }

    // if (!config.password) {
    //   errors.push({ type: 'config_invalid', message: 'MQTT密码不能为空' });
    // }

    // 验证地址格式
    if (config.address && !/^[\w\-\.]+:\d{1,5}$/.test(config.address)) {
      errors.push({ type: 'config_invalid', message: 'MQTT服务器地址格式不正确' });
    }

    return {
      isValid: errors.length === 0,
      errors: errors
    };
  }

  /**
   * 检查CloudControl授权状态变化的影响
   */
  checkCloudControlStatusChange(oldStatus, newStatus, drcStateManager) {
    // 如果授权丢失且正在DRC模式中，需要警告
    if (oldStatus === 'authorized' && newStatus !== 'authorized') {
      if (drcStateManager.drcStatus === 'active') {
        this.logManager.addLog('警告', '云端控制授权已失效，建议退出DRC模式');
        return { shouldShowWarning: true };
      } else if (drcStateManager.drcStatus === 'entering') {
        this.logManager.addLog('错误', '云端控制授权丢失，DRC进入操作已取消');
        drcStateManager.setError('授权丢失');
        return { shouldUpdateUI: true };
      }
    }

    return { shouldUpdateUI: false };
  }
}