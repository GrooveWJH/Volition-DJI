"""
配置参数模块
所有可调参数集中在此文件
"""

# ========== 无人机配置 ==========
GATEWAY_SN = '9N9CN2J0012CXY'
VRPN_DEVICE = 'Drone001@192.168.31.100'

# ========== MQTT配置 ==========
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# ========== 数据记录配置 ==========
ENABLE_DATA_LOGGING = True   # 是否启用数据记录

# ========== 核心控制参数（所有模式共享）==========
# 航点配置
WAYPOINTS = [
    (0, 0),
    (-1, 1),
]

# 目标角度配置
TARGET_YAWS = [
    0,      # 正北（初始朝向）
    90,     # 正东（逆时针90°）
    180,    # 正南（逆时针180°）
    -90,    # 正西（顺时针90°，等价于逆时针270°）
]

# PID增益（所有模式复用）
KP_XY = 200.0   # XY平面比例增益
KI_XY = 30.0    # XY平面积分增益
KD_XY = 70.0   # XY平面微分增益

KP_YAW = 12.0   # Yaw角比例增益
KI_YAW = 5.0    # Yaw角积分增益
KD_YAW = 1.0    # Yaw角微分增益

# 控制参数（所有模式复用）
CONTROL_FREQUENCY = 50       # 控制频率（Hz）
TOLERANCE_XY = 0.10          # XY平面到达阈值（米）
TOLERANCE_YAW = 2.0          # Yaw角到达阈值（度）
MAX_STICK_OUTPUT = 500       # XY平面最大杆量输出限幅（半杆量）
MAX_YAW_STICK_OUTPUT = 660   # Yaw最大杆量输出限幅（满杆量）
NEUTRAL = 1024               # 杆量中值

# ========== 平面+Yaw复合控制配置 ==========
ARRIVAL_STABLE_TIME = 1.0    # 到达稳定时间（秒）

# ========== 平面位置单独控制配置 ==========
# 注：PID参数、控制频率、阈值等复用核心参数
# 注：航点复用 WAYPOINTS

# 到达稳定时间（独立配置）
PLANE_ARRIVAL_STABLE_TIME = 1.0  # 到达稳定时间（秒）

# 自动控制模式
PLANE_AUTO_NEXT_WAYPOINT = False  # 到达航点后自动前往下一个航点（无需按Enter）

# 随机航点生成
PLANE_USE_RANDOM_WAYPOINTS = False  # 使用随机生成的航点（替代WAYPOINTS）
PLANE_RANDOM_MIN_DISTANCE = 0.5     # 随机航点最小距离（米）
PLANE_RANDOM_MAX_DISTANCE = 2.0     # 随机航点最大距离（米）

# 高级控制特性
PLANE_GAIN_SCHEDULING_CONFIG = {
    'enabled': True,        # 启用增益调度（距离自适应PID）
    'distance_far': 1.0,    # 远距离阈值（米）
    'distance_near': 0.5,   # 近距离阈值（米）
    'profile': {            # PID比例/微分增益缩放
        'far': {
            'kp_scale': 1.0,
            'kd_scale': 0.5,
        },
        'near': {
            'kp_scale': 0.4,
            'kd_scale': 1.5,
        }
    }
}

PLANE_SMITH_PREDICTOR_CONFIG = {
    'enabled': True,        # 启用Smith预测器（延迟补偿）
    'estimated_delay': 0.5, # 估计系统延迟（秒）
    'response_gain': 0.0015 # 杆量到速度的响应增益（m/s per stick unit）
}

# 兼容旧命名（逐步淘汰）
PLANE_ENABLE_GAIN_SCHEDULING = PLANE_GAIN_SCHEDULING_CONFIG['enabled']
PLANE_DISTANCE_FAR = PLANE_GAIN_SCHEDULING_CONFIG['distance_far']
PLANE_DISTANCE_NEAR = PLANE_GAIN_SCHEDULING_CONFIG['distance_near']
PLANE_GAIN_SCHEDULING_PROFILE = PLANE_GAIN_SCHEDULING_CONFIG['profile']
PLANE_ENABLE_SMITH_PREDICTOR = PLANE_SMITH_PREDICTOR_CONFIG['enabled']
PLANE_ESTIMATED_DELAY = PLANE_SMITH_PREDICTOR_CONFIG['estimated_delay']
PLANE_RESPONSE_GAIN = PLANE_SMITH_PREDICTOR_CONFIG['response_gain']

# ========== Yaw单独控制配置 ==========
# 注：PID参数复用核心参数 KP_YAW, KI_YAW, KD_YAW
# 注：控制频率、阈值、最大输出复用核心参数
# 注：目标角度复用 TARGET_YAWS

# 到达稳定时间（独立配置）
YAW_ARRIVAL_STABLE_TIME = 0.5  # 到达稳定时间（秒）

# I项启动区间
YAW_I_ACTIVATION_ERROR = 70    # I项启动阈值（度）

# Yaw杆量死区
YAW_DEADZONE = 0               # Yaw杆量死区（小于此值输出为0）

# 自动控制模式
AUTO_NEXT_TARGET = True        # 到达目标后自动前往下一个目标（无需按Enter）

# 随机角度生成
USE_RANDOM_ANGLES = True       # 使用随机生成的目标角度（替代TARGET_YAWS）
RANDOM_ANGLE_MIN_DIFF = 45     # 随机角度与当前目标的最小角度差（度）
