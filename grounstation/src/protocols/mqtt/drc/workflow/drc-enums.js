/**
 * DRC工作流步骤和状态枚举
 * 定义DRC流程中的所有步骤和状态常量
 */

/**
 * DRC工作流步骤枚举
 */
export const DrcWorkflowSteps = {
  IDLE: 'idle',
  AUTH_REQUEST: 'auth_request',
  AUTH_PENDING: 'auth_pending', 
  AUTH_CONFIRMED: 'auth_confirmed',
  ENTERING_DRC: 'entering_drc',
  DRC_ACTIVE: 'drc_active',
  EXITING_DRC: 'exiting_drc',
  ERROR: 'error'
};

/**
 * DRC状态枚举
 */
export const DrcStatus = {
  INACTIVE: 'inactive',
  REQUESTING: 'requesting',
  PENDING: 'pending',
  ACTIVE: 'active',
  ERROR: 'error'
};

/**
 * DRC错误类型
 */
export const DrcErrorTypes = {
  CONFIG_INVALID: 'config_invalid',
  AUTH_FAILED: 'auth_failed',
  TIMEOUT: 'timeout',
  NETWORK_ERROR: 'network_error',
  DEVICE_ERROR: 'device_error'
};

/**
 * DRC超时配置
 */
export const DrcTimeouts = {
  AUTH_REQUEST: 30000,
  MANUAL_CONFIRM: 60000,
  DRC_ENTER: 15000,
  DRC_EXIT: 10000
};