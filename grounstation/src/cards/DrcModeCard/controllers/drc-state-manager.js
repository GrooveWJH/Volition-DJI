/**
 * DRC模式状态管理器
 * 负责DRC模式的状态管理、前置条件检查和配置管理
 */

import debugLogger from '#lib/debug.js';

export class DrcStateManager {
  constructor() {
    // DRC状态枚举
    this.DRC_STATES = {
      IDLE: 'idle',                    // 空闲状态
      CHECKING: 'checking',            // 检查前置条件
      CONFIGURING: 'configuring',      // 配置中
      ENTERING: 'entering',            // 进入DRC模式中
      ACTIVE: 'active',                // DRC模式已激活
      EXITING: 'exiting',              // 退出DRC模式中
      ERROR: 'error'                   // 错误状态
    };

    // 当前状态
    this.drcStatus = this.DRC_STATES.IDLE;
    this.lastError = null;
    this.enteredAt = null;
    this.currentRequestTid = null;

    // MQTT中继配置
    this.mqttBrokerConfig = {
      address: '',
      client_id: '',
      username: '',
      password: '',
      expire_time: null,
      enable_tls: true
    };

    // 频率配置 (与测试保持一致)
    this.osdFrequency = 30;  // OSD频率 (1-500Hz)
    this.hsiFrequency = 10;  // HSI频率 (1-500Hz)

    // 前置条件状态
    this.prerequisites = {
      cloudControlAuthorized: false,
      mqttConnected: false,
      configValid: false
    };

    debugLogger.state('[DrcStateManager] 已初始化');
  }

  /**
   * 检查是否可以进入DRC模式
   */
  canEnterDrcMode() {
    return this.prerequisites.cloudControlAuthorized &&
           this.prerequisites.mqttConnected &&
           this.prerequisites.configValid &&
           this.drcStatus === this.DRC_STATES.IDLE;
  }

  /**
   * 检查CloudControl授权状态
   */
  checkCloudControlStatus(authStatus) {
    const wasAuthorized = this.prerequisites.cloudControlAuthorized;
    this.prerequisites.cloudControlAuthorized = authStatus === 'authorized';

    if (wasAuthorized && !this.prerequisites.cloudControlAuthorized) {
      // 授权丢失，需要重置DRC状态
      if (this.drcStatus === this.DRC_STATES.ACTIVE) {
        debugLogger.state('[DrcStateManager] CloudControl授权丢失，自动退出DRC模式');
        this.resetDrcState();
      }
    }

    debugLogger.state(`[DrcStateManager] CloudControl状态: ${authStatus}`);
    return this.prerequisites.cloudControlAuthorized;
  }

  /**
   * 更新MQTT连接状态
   */
  updateMqttConnectionStatus(isConnected) {
    this.prerequisites.mqttConnected = isConnected;
    debugLogger.state(`[DrcStateManager] MQTT连接状态: ${isConnected ? '已连接' : '未连接'}`);
  }

  /**
   * 设置MQTT中继配置
   */
  setMqttBrokerConfig(config) {
    this.mqttBrokerConfig = {
      ...this.mqttBrokerConfig,
      ...config
    };

    // 验证配置完整性
    this.validateMqttConfig();
    debugLogger.state('[DrcStateManager] MQTT中继配置已更新');
  }

  /**
   * 验证MQTT配置
   */
  validateMqttConfig() {
    const config = this.mqttBrokerConfig;
    const isValid = config.address && config.client_id;

    this.prerequisites.configValid = isValid;

    if (!isValid) {
      this.lastError = 'MQTT中继配置不完整：缺少服务器地址或客户端ID';
    }

    return isValid;
  }

  /**
   * 设置频率配置
   */
  setFrequencyConfig(osdFreq, hsiFreq) {
    if (osdFreq >= 1 && osdFreq <= 500) {
      this.osdFrequency = osdFreq;
    }
    if (hsiFreq >= 1 && hsiFreq <= 30) {
      this.hsiFrequency = hsiFreq;
    }
    debugLogger.state(`[DrcStateManager] 频率配置: OSD=${this.osdFrequency}Hz, HSI=${this.hsiFrequency}Hz`);
  }

  /**
   * 开始进入DRC模式
   */
  startEnteringDrc(requestTid) {
    if (!this.canEnterDrcMode()) {
      throw new Error('不满足进入DRC模式的前置条件');
    }

    this.drcStatus = this.DRC_STATES.ENTERING;
    this.currentRequestTid = requestTid;
    this.lastError = null;

    debugLogger.state(`[DrcStateManager] 开始进入DRC模式 (TID: ${requestTid})`);
  }

  /**
   * 设置DRC模式激活
   */
  setDrcActive() {
    this.drcStatus = this.DRC_STATES.ACTIVE;
    this.enteredAt = Date.now();
    this.currentRequestTid = null;
    debugLogger.state('[DrcStateManager] DRC模式已激活');
  }

  /**
   * 开始退出DRC模式
   */
  startExitingDrc() {
    if (this.drcStatus !== this.DRC_STATES.ACTIVE) {
      throw new Error('当前不在DRC模式中');
    }

    this.drcStatus = this.DRC_STATES.EXITING;
    debugLogger.state('[DrcStateManager] 开始退出DRC模式');
  }

  /**
   * 设置错误状态
   */
  setError(error) {
    this.drcStatus = this.DRC_STATES.ERROR;
    this.lastError = error;
    this.currentRequestTid = null;
    debugLogger.error(`[DrcStateManager] 错误: ${error}`);
  }

  /**
   * 重置DRC状态
   */
  resetDrcState() {
    this.drcStatus = this.DRC_STATES.IDLE;
    this.lastError = null;
    this.enteredAt = null;
    this.currentRequestTid = null;
    debugLogger.state('[DrcStateManager] DRC状态已重置');
  }

  /**
   * 验证TID是否匹配当前请求
   */
  isValidTid(tid) {
    return this.currentRequestTid === tid;
  }

  /**
   * 获取DRC模式持续时间
   */
  getDrcDuration() {
    if (!this.enteredAt) return 0;
    return Math.round((Date.now() - this.enteredAt) / 1000);
  }

  /**
   * 生成MQTT中继配置消息
   */
  buildMqttBrokerMessage() {
    if (!this.validateMqttConfig()) {
      throw new Error('MQTT配置无效');
    }

    return {
      mqtt_broker: {
        address: this.mqttBrokerConfig.address,
        client_id: this.mqttBrokerConfig.client_id,
        username: this.mqttBrokerConfig.username,
        password: this.mqttBrokerConfig.password,
        expire_time: this.mqttBrokerConfig.expire_time || Math.floor(Date.now() / 1000) + 3600, // 默认1小时过期
        enable_tls: this.mqttBrokerConfig.enable_tls
      },
      osd_frequency: this.osdFrequency,
      hsi_frequency: this.hsiFrequency
    };
  }

  /**
   * 获取状态摘要
   */
  getStatusSummary() {
    return {
      drcStatus: this.drcStatus,
      canEnterDrc: this.canEnterDrcMode(),
      prerequisites: { ...this.prerequisites },
      config: {
        osdFrequency: this.osdFrequency,
        hsiFrequency: this.hsiFrequency,
        mqttConfigured: this.prerequisites.configValid
      },
      duration: this.getDrcDuration(),
      lastError: this.lastError
    };
  }

  /**
   * 从localStorage加载配置
   */
  loadConfig() {
    try {
      const savedConfig = localStorage.getItem('drc_mode_config');
      if (savedConfig) {
        const config = JSON.parse(savedConfig);

        // 恢复MQTT配置（密码等敏感信息不保存）
        if (config.mqttBroker) {
          this.mqttBrokerConfig = {
            ...this.mqttBrokerConfig,
            address: config.mqttBroker.address || '',
            client_id: config.mqttBroker.client_id || '',
            username: config.mqttBroker.username || '',
            enable_tls: config.mqttBroker.enable_tls !== false
          };
        }

        // 恢复频率配置
        if (config.frequencies) {
          this.osdFrequency = config.frequencies.osd || 10;
          this.hsiFrequency = config.frequencies.hsi || 1;
        }

        this.validateMqttConfig();
        debugLogger.state('[DrcStateManager] 配置已从localStorage恢复');
      }
    } catch (error) {
      debugLogger.error('[DrcStateManager] 加载配置失败:', error);
    }
  }

  /**
   * 保存配置到localStorage
   */
  saveConfig() {
    try {
      const configToSave = {
        mqttBroker: {
          address: this.mqttBrokerConfig.address,
          client_id: this.mqttBrokerConfig.client_id,
          username: this.mqttBrokerConfig.username,
          enable_tls: this.mqttBrokerConfig.enable_tls
          // 注意：密码等敏感信息不保存到localStorage
        },
        frequencies: {
          osd: this.osdFrequency,
          hsi: this.hsiFrequency
        },
        lastSaved: Date.now()
      };

      localStorage.setItem('drc_mode_config', JSON.stringify(configToSave));
      debugLogger.state('[DrcStateManager] 配置已保存到localStorage');
    } catch (error) {
      debugLogger.error('[DrcStateManager] 保存配置失败:', error);
    }
  }
}