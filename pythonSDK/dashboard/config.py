"""
Dashboard 配置文件

所有可调参数集中在此，便于维护和调整。
"""
import os

# ========== MQTT 连接配置 ==========

MQTT_CONFIG = {
    'host': '81.70.222.38',
    # 'host': '192.168.31.73',  # 内网地址（可选）
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# ========== 无人机配置 ==========

# UAV 配置 - 9N9CN2J0012CXY (001) | 9N9CN8400164WH (002) | 9N9CN180011TJN (003)
# 每架无人机的完整配置（DJI、VRPN、IVAS）集中在一起
UAV_CONFIGS = [
    {
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot_1',
        'callsign': 'Pilot 1',
        'vrpn_device': 'Drone001@192.168.31.100',
        'ivas': {
            'device_code': 1,
            'account': 'ZSDX001',
            'password': '000000'
        }
    },
    {
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot_2',
        'callsign': 'Pilot 2',
        'vrpn_device': 'Drone002@192.168.31.100',
        'ivas': {
            'device_code': 2,
            'account': 'ZSDX002',
            'password': '000000'
        }
    },
    {
        'sn': '9N9CN180011TJN',
        'user_id': 'pilot_3',
        'callsign': 'Pilot 3',
        'vrpn_device': 'Drone003@192.168.31.100',
        'ivas': {
            'device_code': 3,
            'account': 'ZSDX003',
            'password': '000000'
        }
    },
]

# ========== DRC 连接配置 ==========

# 跳过 DRC 连接建立（适用于其他程序已经维持 DRC 状态的场景）
# 设置为 True 时，只连接 MQTT 订阅数据，不请求控制权和进入 DRC 模式
SKIP_DRC_SETUP = False

# OSD 数据频率（Hz）- 包含位置、速度、姿态、电池、GPS 等
OSD_FREQUENCY = 40

# 健康状态指标频率（Hz）- 包含传感器状态、错误码等
HSI_FREQUENCY = 10

# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 1.0

# ========== GUI 显示配置 ==========

# GUI 刷新频率（Hz）- 显式配置界面刷新率
GUI_REFRESH_RATE = 60

# 离线超时时间（秒）- 超过此时间无消息则认为无人机离线
OFFLINE_TIMEOUT = 2.0

# 启用 VRPN 动捕数据显示
# 设置为 True 时，显示动捕位置、速度、加速度数据
ENABLE_VRPN = False

# ========== IVAS 集成配置 ==========

# IVAS 功能总开关
ENABLE_IVAS = True

# IVAS 功能细粒度开关
IVAS_FEATURES = {
    'position_report': False,    # 无人机位置上报（实际执行，从真实MQTT获取数据）
    'target_report': False,      # 目标检测上报（暂不启用，无数据源）
    'task_receive': True,        # 任务接收（仅显示，不实际执行无人机控制）
}

# IVAS 服务器配置
# 支持环境变量切换测试/生产环境
# 测试模式: IVAS_BASE_URL=http://localhost:5001 python main.py
# 生产模式: python main.py (使用默认地址)
IVAS_SERVER = {
    'base_url': os.getenv('IVAS_BASE_URL', 'http://192.168.31.38:8888'),  # 可通过环境变量覆盖
    'report_hz': 5.0,   # 位置和目标上报频率 (Hz)
    'task_hz': 2.0,     # 任务轮询频率 (Hz) - 每 0.5 秒轮询一次
}

