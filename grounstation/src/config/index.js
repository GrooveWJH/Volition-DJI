// DJI Ground Station - 统一配置文件
// 合并: app-config.js + card-config.js + mqtt-config.js + video-config.js

// 应用配置
export const APP_CONFIG = {
  app: {
    name: 'DJI Ground Station',
    version: '2.0.0',
    description: 'DJI无人机地面站控制系统',
    author: 'DJI Team'
  },

  // RTMP视频流配置
  rtmp: {
    defaultHost: '127.0.0.1',
    defaultPort: 1935,
    streamPath: '/live/stream',
    getDefaultUrl() {
      return `rtmp://${this.defaultHost}:${this.defaultPort}${this.streamPath}`;
    },
    buildUrl(host, port, path) {
      return `rtmp://${host || this.defaultHost}:${port || this.defaultPort}${path || this.streamPath}`;
    }
  },

  // 云端控制配置
  cloudControl: {
    defaultUser: 'station_operator',
    defaultCallsign: 'STATION_001',
    authTimeout: 10000,
    controlKeys: ['flight', 'camera', 'gimbal']
  },

  // 开发配置
  dev: {
    debugMode: false,
    mockData: false,
    logLevel: 'info'
  }
};

// 卡片配置
export const CARD_CONFIG = {
  drcMode: {
    id: 'drc-mode',
    collapsed: false,
    title: 'DRC模式管理',
    description: '指令飞行控制模式配置',
    order: 2
  },

  drcControl: {
    id: 'drc-control',
    collapsed: false,
    title: 'DRC遥控',
    description: '无人机远程控制面板',
    order: 1
  },

  streaming: {
    id: 'streaming',
    collapsed: true,
    title: '视频流',
    description: '实时视频传输控制',
    order: 2
  },

  cloudControl: {
    id: 'cloud-control',
    collapsed: false,
    title: '云端控制',
    description: '云端权限申请与管理',
    order: 3
  },

  deviceInfo: {
    id: 'device-info',
    collapsed: true,
    title: '设备信息',
    description: '设备状态与参数显示',
    order: 4
  },

  flightPlan: {
    id: 'flight-plan',
    collapsed: true,
    title: '飞行计划',
    description: '航线规划与执行',
    order: 5
  }
};

// MQTT配置
export const MQTT_CONFIG = {
  // 连接配置
  connection: {
    keepalive: 60,
    connectTimeout: 30000,
    reconnectPeriod: 3000,
    maxReconnectAttempts: 5,
    clean: true
  },

  // 默认broker设置 (测试客户端连接)
  broker: {
    host: '192.168.18.130',
    port: 8083,
    protocol: 'ws',
    username: 'admin',
    password: '302811055wjhhz'
  },

  // DRC模式broker设置 (与测试保持一致)
  drcBroker: {
    host: '192.168.18.130',
    port: 1883,
    username: 'admin',
    password: '302811055wjhhz',
    expire_time: 1700000000
  },

  // 订阅配置
  subscriptions: {
    qos: 1,
    defaultTopics: [
      'thing/product/{sn}/services_reply',
      'thing/product/{sn}/events',
      'thing/product/{sn}/drc/up',
      'thing/product/{sn}/drc/down'
    ]
  },

  // 主题模板
  topicTemplates: {
    serviceCall: 'thing/product/{sn}/services',
    serviceReply: 'thing/product/{sn}/services_reply',
    drcUp: 'thing/product/{sn}/drc/up',
    drcDown: 'thing/product/{sn}/drc/down',
    events: 'thing/product/{sn}/events',
    properties: 'thing/product/{sn}/properties'
  },

  // 消息格式
  messageFormat: {
    service: {
      method: '',
      data: {},
      tid: '',
      bid: '',
      timestamp: 0
    },
    drc: {
      seq: 0,
      data: {},
      timestamp: 0
    }
  }
};

// 视频配置
export const VIDEO_CONFIG = {
  // WebRTC配置
  webrtc: {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ],
    sdpSemantics: 'unified-plan',
    bundlePolicy: 'max-bundle',
    rtcpMuxPolicy: 'require'
  },

  // 视频流配置
  stream: {
    defaultWidth: 1920,
    defaultHeight: 1080,
    defaultFramerate: 30,
    defaultBitrate: 2500000,
    codecPreference: ['H264', 'VP8', 'VP9'],
    formats: ['mp4', 'webm', 'flv']
  },

  // 播放器配置
  player: {
    autoplay: true,
    muted: true,
    controls: true,
    loop: false,
    preload: 'auto',
    poster: '/images/video-placeholder.jpg'
  },

  // RTMP推流配置
  rtmp: {
    defaultUrl: 'rtmp://127.0.0.1:1935/live/stream',
    timeout: 10000,
    reconnectAttempts: 3,
    reconnectDelay: 2000,
    bufferTime: 100,
    maxBufferTime: 3000
  },

  // 录制配置
  recording: {
    format: 'mp4',
    quality: 'high',
    maxDuration: 3600000, // 1小时
    autoSave: true,
    saveDirectory: '/recordings'
  },

  // 截图配置
  screenshot: {
    format: 'png',
    quality: 0.9,
    autoSave: false,
    saveDirectory: '/screenshots'
  }
};

// EMQX API配置
export const EMQX_CONFIG = {
  api: {
    defaultHost: '192.168.18.130',
    defaultPort: '18083',
    defaultApiKey: '9b8799abe2c3d581',
    defaultSecretKey: '8AotAV126dc9B7E8eMhfnbSlC6pTxtl0eLS29AWMi2DrC',
    basePath: '/api/v5',
    timeout: 10000
  },

  endpoints: {
    clients: '/clients',
    subscriptions: '/subscriptions',
    routes: '/routes',
    stats: '/stats'
  },

  polling: {
    interval: 3000,
    maxRetries: 3,
    retryDelay: 1000
  }
};

// 导出默认配置
export const CONFIG = {
  ...APP_CONFIG,
  cards: CARD_CONFIG,
  mqtt: MQTT_CONFIG,
  video: VIDEO_CONFIG,
  emqx: EMQX_CONFIG
};

export default CONFIG;