/**
 * 卡片配置管理
 * 统一管理所有卡片的默认展开/折叠状态
 */

export const CARD_CONFIG = {
  // 视频推流服务卡片
  streaming: {
    id: 'streaming-card',
    collapsed: true,
    title: '视频推流服务',
    description: '实时视频推送与播放',
  },

  // 云端控制授权卡片
  cloudControl: {
    id: 'cloud-control-card',
    collapsed: false,
    title: '云端控制授权',
    description: '请求和释放无人机云端飞行控制权',
  },

  // 其他协议模块卡片
  disabledModules: {
    id: 'disabled-modules-card',
    collapsed: true,
    title: '其他协议模块',
    description: '暂时禁用的协议模块',
  },

  // 未来可以继续添加更多卡片配置...
  // example: {
  //   id: 'example-card',
  //   collapsed: false,
  //   title: '示例卡片',
  //   description: '这是一个示例',
  // },
};

/**
 * 获取指定卡片的配置
 * @param {string} cardKey - 卡片配置键名
 * @returns {Object} 卡片配置对象
 */
export function getCardConfig(cardKey) {
  return CARD_CONFIG[cardKey] || { collapsed: false };
}

/**
 * 获取指定卡片的默认折叠状态
 * @param {string} cardKey - 卡片配置键名
 * @returns {boolean} 是否折叠
 */
export function isCardCollapsed(cardKey) {
  const config = getCardConfig(cardKey);
  return config.collapsed || false;
}

/**
 * 获取所有卡片配置
 * @returns {Object} 所有卡片配置
 */
export function getAllCardConfigs() {
  return CARD_CONFIG;
}
