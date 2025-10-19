/**
 * 云端控制错误处理器
 * 负责错误检测、恢复建议和设备状态验证
 */

import { deviceContext } from '#lib/state.js';
import debugLogger from '#lib/debug.js';

export class ErrorHandler {
  constructor(logManager) {
    this.logManager = logManager;
  }

  /**
   * 检查设备是否在线
   */
  isDeviceOnline(sn) {
    const connection = window.mqttManager?.getConnection(sn);
    return connection && connection.isConnected;
  }

  /**
   * 检查设备是否支持云端控制
   */
  async checkDeviceCapabilities(sn) {
    // 这里可以实现设备能力检测逻辑
    // 暂时返回true，后续可以根据实际需求扩展
    return true;
  }

  /**
   * 验证授权请求参数
   */
  validateAuthRequest(userId, userCallsign, deviceSN) {
    const errors = [];

    if (!deviceSN) {
      errors.push({ type: 'device_offline', message: '未选择设备' });
    }

    if (!userId || !userCallsign) {
      errors.push({ type: 'invalid_params', message: '请填写用户ID和用户呼号' });
    }

    if (deviceSN && !this.isDeviceOnline(deviceSN)) {
      errors.push({ type: 'device_offline', message: '设备未连接，请检查MQTT连接状态' });
    }

    return {
      isValid: errors.length === 0,
      errors: errors
    };
  }

  /**
   * 处理MQTT连接变化
   */
  handleMqttConnectionChange(connectionInfo, authStateManager) {
    if (!connectionInfo) return;

    const currentSN = deviceContext.getCurrentDevice();
    if (connectionInfo.sn !== currentSN) return;

    if (connectionInfo.connected) {
      this.logManager.addLog('信息', `设备 ${currentSN} MQTT连接已建立`);
    } else {
      this.logManager.addLog('警告', `设备 ${currentSN} MQTT连接已断开`);

      // 如果在请求授权时断开连接，自动重置状态
      if (authStateManager.authStatus === 'requesting') {
        this.logManager.addLog('错误', '授权请求期间连接断开，已取消请求');
        authStateManager.resetAuth();
        return { shouldUpdateUI: true };
      }
    }

    return { shouldUpdateUI: false };
  }

  /**
   * 处理服务调用错误
   */
  handleServiceError(error, result) {
    let errorType = 'auth_rejected';
    let message = `发送失败: ${result?.error?.message || error?.message || '未知错误'}`;

    if (result?.error?.code === 'TIMEOUT' || error?.name === 'TimeoutError') {
      errorType = 'timeout';
    } else if (result?.error?.code === 'CONNECTION_FAILED' || error?.name === 'NetworkError') {
      errorType = 'connection_failed';
    }

    this.logManager.addLog('错误', message);
    this.showErrorAdvice(errorType);

    return { errorType, message };
  }

  /**
   * 处理授权回复消息
   */
  handleAuthReply(msg, authStateManager) {
    const result = msg.data?.result;
    const status = msg.data?.output?.status;

    // 验证是否是当前请求的回复
    if (!authStateManager.isValidTid(msg.tid)) {
      this.logManager.addLog('调试', `收到其他请求的回复，忽略 (TID: ${msg.tid})`);
      return { shouldUpdateUI: false };
    }

    if (result === 0 && status === 'ok') {
      authStateManager.setAuthorized();
      const duration = authStateManager.getAuthDuration();
      this.logManager.addLog('成功', '✓ 云端控制授权已批准');
      this.logManager.addLog('信息', `授权用户: ${authStateManager.userCallsign} (耗时: ${duration}秒)`);
      return { shouldUpdateUI: true };

    } else if (result === 0 && status === 'in_progress') {
      this.logManager.addLog('成功', '✓ 授权请求已发送到遥控器');
      this.logManager.addLog('信息', '📱 遥控器屏幕应该已显示授权弹窗');
      this.logManager.addLog('提示', '请在遥控器上点击"同意"后，点击页面上的"确认已在遥控器上授权"按钮');

      return { shouldUpdateUI: true };

    } else {
      authStateManager.resetAuth();
      this.logManager.addLog('错误', `授权请求失败 (result: ${result}, status: ${status || 'unknown'})`);

      // 提供具体的错误信息
      this.provideSpecificErrorAdvice(result);
      return { shouldUpdateUI: true };
    }
  }

  /**
   * 提供具体的错误恢复建议
   */
  provideSpecificErrorAdvice(result) {
    if (result === 1) {
      this.logManager.addLog('提示', '可能原因: 遥控器用户拒绝了授权请求');
    } else if (result === 2) {
      this.logManager.addLog('提示', '可能原因: 设备不支持云端控制功能');
    } else if (result === 3) {
      this.logManager.addLog('提示', '可能原因: 设备当前状态不允许授权');
    }
  }

  /**
   * 获取错误恢复建议
   */
  getErrorRecoveryAdvice(errorType) {
    const advice = {
      'connection_failed': [
        '1. 检查网络连接是否正常',
        '2. 确认MQTT Broker地址和端口正确',
        '3. 检查防火墙设置是否阻止连接'
      ],
      'device_offline': [
        '1. 确认设备电源已开启',
        '2. 检查设备网络连接',
        '3. 重启设备并重新连接'
      ],
      'auth_rejected': [
        '1. 确认在遥控器上点击了"同意"',
        '2. 检查用户ID和呼号是否正确',
        '3. 确认设备支持云端控制功能'
      ],
      'timeout': [
        '1. 检查网络延迟是否过高',
        '2. 重新发送授权请求',
        '3. 确认设备处于正常工作状态'
      ]
    };

    return advice[errorType] || ['请联系技术支持获取帮助'];
  }

  /**
   * 显示错误恢复建议
   */
  showErrorAdvice(errorType) {
    const advice = this.getErrorRecoveryAdvice(errorType);
    this.logManager.addLog('帮助', '故障排除建议:');
    advice.forEach(tip => {
      this.logManager.addLog('提示', tip);
    });
  }
}