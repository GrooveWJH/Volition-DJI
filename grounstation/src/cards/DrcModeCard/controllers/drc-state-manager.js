/**
 * DRC状态管理器 - 极简版
 * 负责配置的持久化
 */

import debugLogger from '#lib/debug.js';

export class DrcStateManager {
  constructor() {
    // MQTT配置
    this.mqttBrokerConfig = {
      address: '192.168.31.73:1883',
      client_id: '',
      username: 'admin',
      password: '',
      enable_tls: false,
      anonymous: false,
    };

    // 频率配置
    this.osdFrequency = 10;
    this.hsiFrequency = 1;

    // DRC状态
    this.isDrcActive = false;
    this.enteredAt = null;

    this.loadConfig();
  }

  loadConfig() {
    if (typeof window === 'undefined') return;

    try {
      const saved = localStorage.getItem('drc_config');
      if (saved) {
        const config = JSON.parse(saved);
        this.mqttBrokerConfig = { ...this.mqttBrokerConfig, ...config.mqtt };
        this.osdFrequency = config.osdFrequency || 10;
        this.hsiFrequency = config.hsiFrequency || 1;
        debugLogger.info('[DRC] 配置已从localStorage恢复');
      }
    } catch (error) {
      debugLogger.warn('[DRC] 加载配置失败:', error);
    }
  }

  saveConfig() {
    if (typeof window === 'undefined') return;

    try {
      const config = {
        mqtt: this.mqttBrokerConfig,
        osdFrequency: this.osdFrequency,
        hsiFrequency: this.hsiFrequency,
      };
      localStorage.setItem('drc_config', JSON.stringify(config));
    } catch (error) {
      debugLogger.warn('[DRC] 保存配置失败:', error);
    }
  }

  setDrcActive() {
    this.isDrcActive = true;
    this.enteredAt = Date.now();
  }

  resetDrcState() {
    this.isDrcActive = false;
    this.enteredAt = null;
  }

  getDrcDuration() {
    return this.enteredAt ? Math.floor((Date.now() - this.enteredAt) / 1000) : 0;
  }
}
