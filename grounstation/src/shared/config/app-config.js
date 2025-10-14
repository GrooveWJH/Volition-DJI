/**
 * 主配置文件
 * 集成所有模块配置并提供统一接口
 */

import { MQTT_CONFIG, DRC_CONFIG } from './mqtt-config.js';
import { RTMP_CONFIG, WEBRTC_CONFIG, CONNECTION_CONFIG, STREAM_QUALITY_CONFIG, getVideoEnvironmentOverrides } from './video-config.js';

/**
 * 应用程序主配置对象
 */
export const CONFIG = {
  // RTMP服务器配置
  rtmp: RTMP_CONFIG,
  
  // MQTT配置 
  mqtt: MQTT_CONFIG,
  
  // DRC配置
  drc: DRC_CONFIG,
  
  // WebRTC配置
  webrtc: WEBRTC_CONFIG,
  
  // 连接测试配置
  connection: CONNECTION_CONFIG,
  
  // 流媒体质量配置
  streamQuality: STREAM_QUALITY_CONFIG,
  
  // 终端日志配置
  terminal: {
    // 最大日志条数
    maxLogLines: 100,
    
    // 日志颜色配置
    colors: {
      info: '#60a5fa',      // 蓝色
      success: '#34d399',   // 绿色
      warning: '#fbbf24',   // 黄色
      error: '#f87171'      // 红色
    },
    
    // 时间戳格式
    timestampFormat: {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }
  },
  
  // UI配置
  ui: {
    // 默认表单值
    defaultValues: {
      targetIp: '192.168.31.38',
      targetPort: 80
    },
    
    // 动画配置
    animations: {
      collapseTransition: '0.3s ease-out',
      hoverTransition: '0.2s'
    },
    
    // 响应式断点
    breakpoints: {
      mobile: '768px',
      tablet: '1024px'
    }
  },
  
  // 协议配置
  protocols: {
    // 禁用的协议列表
    disabled: [
      '态势感知信息',
      '无人机状态信息', 
      '无人机控制指令'
    ],
    
    // 活跃的协议
    active: [
      '视频媒体推流',
      'MQTT控制系统',
      'DRC远程控制'
    ]
  },
  
  // 开发/调试配置
  debug: {
    // 是否启用详细日志
    verbose: false,
    
    // 是否显示性能统计
    showPerformance: false,
    
    // WebRTC统计报告间隔(毫秒)
    statsInterval: 5000
  }
};

/**
 * 配置验证函数
 * @returns {Object} 验证结果
 */
export function validateConfig() {
  const errors = [];
  
  // 验证RTMP配置
  if (!CONFIG.rtmp.defaultHost) {
    errors.push('RTMP默认主机地址未配置');
  }
  
  // 验证端口范围
  if (CONFIG.rtmp.defaultPort < 1 || CONFIG.rtmp.defaultPort > 65535) {
    errors.push('RTMP端口范围无效');
  }
  
  if (CONFIG.webrtc.defaultPort < 1 || CONFIG.webrtc.defaultPort > 65535) {
    errors.push('WebRTC端口范围无效');
  }
  
  // 验证超时配置
  if (CONFIG.connection.timeoutMs < 1000) {
    errors.push('连接超时时间过短，建议至少1000ms');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * 环境配置覆盖
 */
export function loadEnvironmentConfig() {
  // 获取视频模块的环境变量覆盖
  const videoOverrides = getVideoEnvironmentOverrides();

  // 应用视频配置覆盖
  if (Object.keys(videoOverrides).length > 0) {
    if (videoOverrides.rtmp) mergeConfig(CONFIG.rtmp, videoOverrides.rtmp);
    if (videoOverrides.webrtc) mergeConfig(CONFIG.webrtc, videoOverrides.webrtc);
    if (videoOverrides.quality) mergeConfig(CONFIG.streamQuality, videoOverrides.quality);
  }

  // 通用环境变量覆盖
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);

    if (params.has('debug')) {
      CONFIG.debug.verbose = params.get('debug') === 'true';
    }
  }
}

/**
 * 深度合并配置对象
 * @param {Object} target - 目标对象
 * @param {Object} source - 源对象
 */
function mergeConfig(target, source) {
  for (const key in source) {
    if (source.hasOwnProperty(key)) {
      if (typeof source[key] === 'object' && source[key] !== null && !Array.isArray(source[key])) {
        if (!target[key]) target[key] = {};
        mergeConfig(target[key], source[key]);
      } else {
        target[key] = source[key];
      }
    }
  }
}

/**
 * 获取配置摘要信息
 * @returns {Object} 配置摘要
 */
export function getConfigSummary() {
  return {
    rtmp: {
      url: CONFIG.rtmp.getDefaultUrl(),
      host: CONFIG.rtmp.defaultHost,
      port: CONFIG.rtmp.defaultPort
    },
    mqtt: {
      url: CONFIG.mqtt.buildConnectionUrl(),
      host: CONFIG.mqtt.defaultHost,
      port: CONFIG.mqtt.defaultPort,
      currentDevice: CONFIG.mqtt.getCurrentGatewaySN()
    },
    webrtc: {
      port: CONFIG.webrtc.defaultPort,
      iceServers: CONFIG.webrtc.iceServers.length
    },
    drc: {
      timeout: CONFIG.drc.timeoutSeconds,
      retries: CONFIG.drc.maxRetries
    }
  };
}

// 导出默认配置
export default CONFIG;