/**
 * 协议测试系统配置文件
 * 集中管理所有默认设置、端口、IP地址等配置项
 */

export const CONFIG = {
  // RTMP服务器配置
  rtmp: {
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
  },
  
  // WebRTC配置
  webrtc: {
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
  },
  
  // 连接测试配置
  connection: {
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
        `${baseUrl}:${CONFIG.webrtc.defaultPort}/`,  // WebRTC端口
        `${baseUrl}/`  // 基本HTTP测试
      ];
    }
  },
  
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
      '视频媒体推流'
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

// 配置验证函数
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

// 环境配置覆盖
export function loadEnvironmentConfig() {
  // 从URL参数读取配置覆盖
  const params = new URLSearchParams(window.location.search);
  
  if (params.has('rtmp_host')) {
    CONFIG.rtmp.defaultHost = params.get('rtmp_host');
  }
  
  if (params.has('rtmp_port')) {
    CONFIG.rtmp.defaultPort = parseInt(params.get('rtmp_port'), 10);
  }
  
  if (params.has('webrtc_port')) {
    CONFIG.webrtc.defaultPort = parseInt(params.get('webrtc_port'), 10);
  }
  
  if (params.has('debug')) {
    CONFIG.debug.verbose = params.get('debug') === 'true';
  }
  
  // 从localStorage读取用户自定义配置
  try {
    const userConfig = localStorage.getItem('protocol_test_config');
    if (userConfig) {
      const parsed = JSON.parse(userConfig);
      // 深度合并配置
      mergeConfig(CONFIG, parsed);
    }
  } catch (error) {
    console.warn('无法加载用户配置:', error);
  }
}

// 深度合并配置对象
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

// 保存用户配置到localStorage
export function saveUserConfig(configOverrides) {
  try {
    localStorage.setItem('protocol_test_config', JSON.stringify(configOverrides));
    return true;
  } catch (error) {
    console.error('无法保存用户配置:', error);
    return false;
  }
}

// 重置配置到默认值
export function resetConfig() {
  localStorage.removeItem('protocol_test_config');
  window.location.reload();
}

// 导出配置供其他模块使用
export default CONFIG;