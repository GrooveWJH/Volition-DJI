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
        'flight_height': 90.0,  # 起飞和航点飞行高度（米）
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
        'flight_height': 100.0,  # 起飞和航点飞行高度（米）
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
        'flight_height': 110.0,  # 起飞和航点飞行高度（米）
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
ENABLE_IVAS = False

# IVAS 功能细粒度开关
IVAS_FEATURES = {
    'position_report': True,      # 无人机位置上报（实际执行，从真实MQTT获取数据）
    'target_report': False,       # 目标检测上报（暂不启用，无数据源）
    'fake_target_report': True,   # 假目标上报（跟随无人机GPS，生成假数据）
    'task_receive': True,         # 任务接收
}

# IVAS 服务器配置
# 支持环境变量切换测试/生产环境
# 测试模式: IVAS_BASE_URL=http://localhost:5001 python main.py
# 生产模式: python main.py (使用默认地址)
IVAS_SERVER = {
    'base_url': os.getenv('IVAS_BASE_URL', 'http://192.168.31.38:8888'),  # 可通过环境变量覆盖
    'report_hz': 1.0,   # 位置上报频率 (Hz) - 推荐 1Hz
    'task_hz': 2.0,     # 任务轮询频率 (Hz) - 每 0.5 秒轮询一次
}

# IVAS 高级配置
IVAS_ADVANCED = {
    'require_gps': False,              # 位置上报是否要求GPS有效（False时无GPS也上报，lat/lon=0）
    'enable_task_execution': True,    # 是否执行任务分发（False时仅监视，不执行）
    'position_log_duration': 5.0,      # 位置上报日志打印时长（秒，前N秒打印）
}

# IVAS 假目标上报配置（用于测试和演示）
IVAS_FAKE_TARGET = {
    'enabled': True,                   # 总开关（与 IVAS_FEATURES['fake_target_report'] 配合使用）
    'report_hz': 0.5,                  # 上报频率（Hz）- 每 2 秒上报一次
    'range_meters': 10.0,              # 范围说明（米）- 用于文档
    'lat_offset': 0.0001,              # 纬度偏移（度）≈ 11m
    'lon_offset': 0.0001,              # 经度偏移（度）≈ 8-10m（中纬度）
    'target_count': 1,                 # 每次上报的目标数量
    'altitude': 0.0,                   # 目标高度（固定值，代表地面目标）
    'require_gps': True,               # 是否要求GPS有效（False时GPS无效也上报）
    'target_classes': [0, 1],          # 目标类别列表（0:人, 1:车）
    'target_class_weights': [0.1, 0.9],  # 目标类别权重（10% 人，90% 车）
    'max_targets_per_uav': 10,         # 每个 UAV 最多 10 个循环目标
    'report_after_waypoint': True,     # 仅在到达航点后上报
    'report_duration': 20.0,           # 到达航点后上报持续时间（秒）
    'enable_debug_log': False,         # 是否打印调试日志（启动、航点、上报数据）
}

# ========== 室内系统配置 (UWB + IVAS) ==========

# 室内指挥端系统配置（indoor_commander.py）
INDOOR_SYSTEM = {
    # 系统总开关
    'enabled': True,                   # 室内系统是否启用
    'use_dry_run': False,              # False=真实 IVAS 连接, True=Dry-run 模式（仅打印）

    # UWB 室内定位配置
    'uwb': {
        'subscribe_topic': 'uwb/position',  # UWB 位置订阅主题

        # 坐标变换参数（UWB 坐标系 → IVAS 坐标系）
        # 公式: transformed = (raw + offset) * scale
        'transform': {
            'x_offset': -3.13,         # x 轴平移（米）
            'y_offset': +0.04,         # y 轴平移（米）
            'x_scale': 0.90,           # x 轴缩放系数
            'y_scale': 1.0,            # y 轴缩放系数
        },

        # 高度处理配置
        'use_altitude': False,         # 是否使用 UWB 实时高度（False 则使用固定高度）
        'fixed_altitude_base': 10001.3,  # 固定高度基础值（米）
                                          # 说明：IVAS 虚拟高度平面，用于 2D 平面投影
                                          # 室内系统不需要真实高度，使用固定值简化处理
        'fixed_altitude_range': 0.05,  # 固定高度随机波动范围（±米）
                                        # 说明：模拟 GPS 噪声，使 IVAS 前端显示更真实
    },

    # 目标检测配置（MQTT 订阅）
    'detection': {
        'subscribe_topic': 'indoor/target/detection',  # 目标检测订阅主题
                                                       # 说明：收到此消息时，激活当前触发区域内的目标
                                                       # 消息格式：{"detected": true, "timestamp": 1234567890}
    },

    # 上报频率配置
    'reporting': {
        'position_hz': 1.0,            # 位置上报频率（Hz）- 推荐 1Hz
        'task_hz': 2.0,                # 任务轮询频率（Hz）- 每 0.5 秒轮询一次
        'target_hz': 2.0,              # 目标上报频率（Hz）- 每 0.5 秒上报一次
        'position_log_duration': 0.0,  # 位置上报日志打印时长（秒，0=不打印）
        'target_log_duration': 1000.0, # 目标上报日志打印时长（秒，1000=长期打印）
    },

    # 目标触发配置（基于 UWB 位置的触发区域）
    'targets': {
        'enabled': True,               # 目标上报功能总开关

        # 触发区域定义（矩形区域，基于变换后的坐标）
        # 格式: {target_id: {'x_min', 'x_max', 'y_min', 'y_max'}}
        # 说明：无人机进入区域后，对应目标永久激活（即使离开区域也持续上报）
        'trigger_areas': {
            1: {  # 目标1触发区域（东北角货架区）
                'x_min': -2.92,        # 矩形对角顶点 x_a
                'y_min': 4.35,         # 矩形对角顶点 y_a
                'x_max': -1.5,         # 矩形对角顶点 x_b
                'y_max': 6.45          # 矩形对角顶点 y_b
            },
            2: {  # 目标2触发区域（中部通道区）
                'x_min': -2.60,        # 矩形对角顶点 x_c
                'y_min': 9.09,         # 矩形对角顶点 y_c
                'x_max': -0.68,        # 矩形对角顶点 x_d
                'y_max': 10.97         # 矩形对角顶点 y_d
            },
            3: {  # 目标3触发区域（西南角工作区）
                'x_min': 1.11,         # 矩形对角顶点 x_e
                'y_min': 10.81,        # 矩形对角顶点 y_e
                'x_max': 2.79,         # 矩形对角顶点 x_f
                'y_max': 12.21         # 矩形对角顶点 y_f
            },
        },

        # 目标位置定义（固定位置）
        # 格式: {target_id: {'id', 'cls', 'gis'}}
        # 说明：gis=[纬度, 经度, 高度]（lat, lon, alt）
        'positions': {
            1: {'id': 1, 'cls': 0, 'gis': [-1.68, 1.70, 10000]},    # 目标1（人）- lat, lon, alt
            2: {'id': 2, 'cls': 0, 'gis': [-2.37, 17.03, 10000]},   # 目标2（人）- lat, lon, alt
            3: {'id': 3, 'cls': 0, 'gis': [0.5, 10.99, 10000]},     # 目标3（人）- lat, lon, alt
        }
    },

    # 任务转发配置
    'task': {
        'publish_topic': 'ivas/task/command',  # MQTT 任务转发主题
        'mission_filter': 1,                   # 只转发特定 mission 类型
                                               # 1=起飞, 2=降落, 3=返航, 4=前往指定点
    },

    # 无人机默认参数
    'defaults': {
        'heading': 0,                  # 默认航向角（度）- 室内系统无航向传感器
        'motion': 1,                   # 默认运动状态（0:静止, 1:运动）
    }
}

