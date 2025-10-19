/**
 * DrcStateManager Mock版本 - 用于单元测试
 * 移除了对外部依赖的引用，专门用于测试环境
 */

export class DrcStateManager {
  constructor() {
    // DRC状态枚举
    this.DRC_STATES = {
      IDLE: 'idle',
      CHECKING: 'checking',
      CONFIGURING: 'configuring',
      ENTERING: 'entering',
      ACTIVE: 'active',
      EXITING: 'exiting',
      ERROR: 'error'
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

    // 频率配置
    this.osdFrequency = 10;
    this.hsiFrequency = 1;

    // 前置条件状态
    this.prerequisites = {
      cloudControlAuthorized: false,
      mqttConnected: false,
      configValid: false
    };
  }

  canEnterDrcMode() {
    return this.prerequisites.cloudControlAuthorized &&
           this.prerequisites.mqttConnected &&
           this.prerequisites.configValid &&
           this.drcStatus === this.DRC_STATES.IDLE;
  }

  checkCloudControlStatus(authStatus) {
    const wasAuthorized = this.prerequisites.cloudControlAuthorized;
    this.prerequisites.cloudControlAuthorized = authStatus === 'authorized';

    if (wasAuthorized && !this.prerequisites.cloudControlAuthorized) {
      if (this.drcStatus === this.DRC_STATES.ACTIVE) {
        this.resetDrcState();
      }
    }

    return this.prerequisites.cloudControlAuthorized;
  }

  updateMqttConnectionStatus(isConnected) {
    this.prerequisites.mqttConnected = isConnected;
  }

  setMqttBrokerConfig(config) {
    this.mqttBrokerConfig = {
      ...this.mqttBrokerConfig,
      ...config
    };
    this.validateMqttConfig();
  }

  validateMqttConfig() {
    const config = this.mqttBrokerConfig;
    const isValid = !!(config.address &&
                      config.client_id &&
                      config.username &&
                      config.password);

    this.prerequisites.configValid = isValid;

    if (!isValid) {
      this.lastError = 'MQTT中继配置不完整';
    }

    return isValid;
  }

  setFrequencyConfig(osdFreq, hsiFreq) {
    if (osdFreq >= 1 && osdFreq <= 30) {
      this.osdFrequency = osdFreq;
    }
    if (hsiFreq >= 1 && hsiFreq <= 30) {
      this.hsiFrequency = hsiFreq;
    }
  }

  startEnteringDrc(requestTid) {
    if (!this.canEnterDrcMode()) {
      throw new Error('不满足进入DRC模式的前置条件');
    }

    this.drcStatus = this.DRC_STATES.ENTERING;
    this.currentRequestTid = requestTid;
    this.lastError = null;
  }

  setDrcActive() {
    this.drcStatus = this.DRC_STATES.ACTIVE;
    this.enteredAt = Date.now();
    this.currentRequestTid = null;
  }

  startExitingDrc() {
    if (this.drcStatus !== this.DRC_STATES.ACTIVE) {
      throw new Error('当前不在DRC模式中');
    }
    this.drcStatus = this.DRC_STATES.EXITING;
  }

  setError(error) {
    this.drcStatus = this.DRC_STATES.ERROR;
    this.lastError = error;
    this.currentRequestTid = null;
  }

  resetDrcState() {
    this.drcStatus = this.DRC_STATES.IDLE;
    this.lastError = null;
    this.enteredAt = null;
    this.currentRequestTid = null;
  }

  isValidTid(tid) {
    return this.currentRequestTid === tid;
  }

  getDrcDuration() {
    if (!this.enteredAt) return 0;
    return Math.round((Date.now() - this.enteredAt) / 1000);
  }

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
        expire_time: this.mqttBrokerConfig.expire_time || Math.floor(Date.now() / 1000) + 3600,
        enable_tls: this.mqttBrokerConfig.enable_tls
      },
      osd_frequency: this.osdFrequency,
      hsi_frequency: this.hsiFrequency
    };
  }

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

  loadConfig() {
    // Mock implementation - do nothing
  }

  saveConfig() {
    // Mock implementation - do nothing
  }
}