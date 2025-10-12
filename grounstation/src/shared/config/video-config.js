/**
 * 视频流相关配置
 * 包含RTMP、WebRTC、连接测试等配置
 */

/**
 * RTMP服务器配置
 */
export const RTMP_CONFIG = {
  // 默认服务器地址 - MediaMTX运行在macOS上
  defaultHost: '192.168.31.14',
  defaultPort: 1935,
  defaultApp: 'live',
  defaultStream: 'cam',
  
  // 构建完整RTMP URL
  getDefaultUrl() {
    return `rtmp://${this.defaultHost}:${this.defaultPort}/${this.defaultApp}/${this.defaultStream}`;
  },
  
  // 解析RTMP URL
  parseUrl(rtmpUrl) {
    try {
      const url = new URL(rtmpUrl.replace('rtmp://', 'http://'));
      const pathParts = url.pathname.split('/').filter(p => p);
      return {
        host: url.hostname,
        port: url.port || '1935',
        app: pathParts[0] || 'live',
        stream: pathParts[1] || 'cam',
        streamPath: pathParts.join('/')
      };
    } catch (error) {
      throw new Error(`无效的RTMP URL: ${rtmpUrl}`);
    }
  }
};

/**
 * WebRTC配置
 */
export const WEBRTC_CONFIG = {
  // MediaMTX WebRTC端口
  defaultPort: 8889,
  
  // STUN服务器配置
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' }
  ],
  
  // 低延迟优化配置
  rtcConfiguration: {
    bundlePolicy: 'max-bundle',
    rtcpMuxPolicy: 'require'
  },
  
  // WHEP协议路径
  whepPath: '/whep',
  
  // 构建WebRTC URL
  buildUrl(host, streamPath) {
    return `http://${host}:${this.defaultPort}/${streamPath}${this.whepPath}`;
  }
};

/**
 * 连接测试配置
 */
export const CONNECTION_CONFIG = {
  // 测试超时时间(毫秒)
  timeoutMs: 3000,
  
  // MediaMTX API测试端点
  testEndpoints: [
    '/api/v1/config',     // MediaMTX API v1
    '/api/v2/config',     // MediaMTX API v2
    '/api/v3/config'      // MediaMTX API v3
  ],
  
  // 构建测试URL列表
  buildTestUrls(host) {
    const baseUrl = `http://${host}`;
    return [
      // API端点测试
      ...this.testEndpoints.map(endpoint => `${baseUrl}${endpoint}`),
      // 其他服务端口测试
      `${baseUrl}:${WEBRTC_CONFIG.defaultPort}/`,  // WebRTC端口
      `${baseUrl}/`  // 基本HTTP测试
    ];
  }
};

/**
 * 流媒体质量配置
 */
export const STREAM_QUALITY_CONFIG = {
  // 预设质量配置
  presets: {
    low: {
      bitrate: '500k',
      resolution: '640x480',
      framerate: 15,
      description: '低质量 (节省带宽)'
    },
    medium: {
      bitrate: '1500k',
      resolution: '1280x720',
      framerate: 30,
      description: '中等质量 (平衡)'
    },
    high: {
      bitrate: '3000k',
      resolution: '1920x1080',
      framerate: 30,
      description: '高质量 (推荐)'
    },
    ultra: {
      bitrate: '6000k',
      resolution: '3840x2160',
      framerate: 60,
      description: '超高质量 (需要强力网络)'
    }
  },
  
  // 默认质量
  defaultPreset: 'high'
};

/**
 * 验证RTMP配置
 * @param {Object} config - 配置对象
 * @returns {Object} 验证结果
 */
export function validateRtmpConfig(config = RTMP_CONFIG) {
  const errors = [];
  
  // 验证主机地址
  if (!config.defaultHost) {
    errors.push('RTMP默认主机地址未配置');
  }
  
  // 验证端口范围
  if (config.defaultPort < 1 || config.defaultPort > 65535) {
    errors.push('RTMP端口范围无效(1-65535)');
  }
  
  // 验证应用和流名称
  if (!config.defaultApp) {
    errors.push('RTMP应用名称未配置');
  }
  
  if (!config.defaultStream) {
    errors.push('RTMP流名称未配置');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * 验证WebRTC配置
 * @param {Object} config - 配置对象
 * @returns {Object} 验证结果
 */
export function validateWebrtcConfig(config = WEBRTC_CONFIG) {
  const errors = [];
  
  // 验证端口范围
  if (config.defaultPort < 1 || config.defaultPort > 65535) {
    errors.push('WebRTC端口范围无效(1-65535)');
  }
  
  // 验证ICE服务器配置
  if (!config.iceServers || config.iceServers.length === 0) {
    errors.push('ICE服务器配置缺失');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * 验证连接配置
 * @param {Object} config - 配置对象
 * @returns {Object} 验证结果
 */
export function validateConnectionConfig(config = CONNECTION_CONFIG) {
  const errors = [];
  
  // 验证超时配置
  if (config.timeoutMs < 1000) {
    errors.push('连接超时时间过短，建议至少1000ms');
  }
  
  if (config.timeoutMs > 30000) {
    errors.push('连接超时时间过长，建议不超过30000ms');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * 流状态枚举
 */
export const StreamState = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  PLAYING: 'playing',
  BUFFERING: 'buffering',
  ERROR: 'error',
  DISCONNECTED: 'disconnected'
};

/**
 * 获取视频配置的环境变量覆盖
 */
export function getVideoEnvironmentOverrides() {
  const overrides = {};
  
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    
    if (params.has('rtmp_host')) {
      overrides.rtmp = { defaultHost: params.get('rtmp_host') };
    }
    
    if (params.has('rtmp_port')) {
      overrides.rtmp = { 
        ...overrides.rtmp,
        defaultPort: parseInt(params.get('rtmp_port'), 10) 
      };
    }
    
    if (params.has('webrtc_port')) {
      overrides.webrtc = { 
        defaultPort: parseInt(params.get('webrtc_port'), 10) 
      };
    }
    
    if (params.has('quality')) {
      const quality = params.get('quality');
      if (STREAM_QUALITY_CONFIG.presets[quality]) {
        overrides.quality = { defaultPreset: quality };
      }
    }
  }
  
  return overrides;
}