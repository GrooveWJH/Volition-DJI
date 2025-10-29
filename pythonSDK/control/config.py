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

# ========== 航点配置 ==========
WAYPOINTS = [
    (0, 0),
    (-1, 1),
]

# ========== PID参数 ==========
# XY平面控制
KP_XY = 150.0  # 比例增益
KI_XY = 35.0   # 积分增益
KD_XY = 180.0  # 微分增益

# Yaw角控制
KP_YAW = 200.0  # Yaw比例增益（角度控制需要更强响应）
KI_YAW = 20.0   # Yaw积分增益
KD_YAW = 150.0  # Yaw微分增益

# ========== 控制参数 ==========
CONTROL_FREQUENCY = 50       # 控制频率（Hz）
TOLERANCE_XY = 0.08          # XY平面到达阈值（米）
TOLERANCE_YAW = 5.0          # Yaw角到达阈值（度）
ARRIVAL_STABLE_TIME = 2.0    # 到达稳定时间（秒）
MAX_STICK_OUTPUT = 330       # 最大杆量输出限幅（半杆量）
NEUTRAL = 1024               # 杆量中值

# ========== 数据记录配置 ==========
ENABLE_DATA_LOGGING = True   # 是否启用数据记录
