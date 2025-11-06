# IVAS Python SDK

IVAS 无人机客户端 SDK，提供与 IVAS 服务器交互的完整接口。

## 功能特性

- **位置数据上报**: 自动生成并上报无人机位置数据
- **目标检测上报**: 上报目标检测数据（人、车、飞机等）
- **任务轮询**: 定期从服务器获取任务指令
- **Token 管理**: 自动处理登录和 token 过期重新登录
- **可配置频率**: 灵活配置上报频率和轮询频率
- **多设备支持**: 可同时运行多个客户端实例

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

或者手动安装：

```bash
pip install requests
```

### 基本使用

```python
from ivas import IVASClient
import threading

# 创建客户端实例
client = IVASClient(
    device_code=1,              # 设备编号
    account='ZSDX001',          # 登录账号
    password='your_password',   # 登录密码
    base_lat=23.0,              # 基准纬度
    base_lon=113.0,             # 基准经度
    base_alt=100.0,             # 基准海拔
    coord_range={               # 坐标随机范围
        'lat_offset': 0.001,
        'lon_offset': 0.001,
        'alt_offset': 10.0
    },
    base_url='http://localhost:5001',  # IVAS 服务器地址
    report_hz=1.0,              # 位置上报频率 (Hz)
    task_hz=0.2                 # 任务轮询频率 (Hz)
)

# 在线程中运行客户端
thread = threading.Thread(target=client.run, daemon=True)
thread.start()

# 或者直接运行（阻塞）
# client.run()
```

### 运行示例

```bash
# 单设备示例
python3 examples/example.py

# 多设备示例
python3 examples/example.py --multi
```

## 安装方式

### 方式 1: 直接使用（无需安装）

将 `ivas` 目录复制到你的项目中，直接导入使用：

```python
from ivas import IVASClient
```

### 方式 2: 通过 pip 安装

在 `ivas` 目录下执行：

```bash
# 安装到 Python 环境
pip install .

# 或者以可编辑模式安装（开发模式）
pip install -e .
```

### 方式 3: 添加到 Python 路径

在你的代码中添加：

```python
import sys
import os
sys.path.insert(0, '/path/to/ivas')

from ivas import IVASClient
```

## API 文档

### IVASClient 类

#### 初始化参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `device_code` | int | 是 | - | 设备编号 (例如: 1, 2, 3) |
| `account` | str | 是 | - | 登录账号 (例如: ZSDX001) |
| `password` | str | 是 | - | 登录密码 |
| `base_lat` | float | 是 | - | 基准纬度 |
| `base_lon` | float | 是 | - | 基准经度 |
| `base_alt` | float | 是 | - | 基准海拔高度 |
| `coord_range` | dict | 是 | - | 坐标随机范围，包含 `lat_offset`, `lon_offset`, `alt_offset` |
| `base_url` | str | 是 | - | IVAS 服务器地址 |
| `display_queue` | Queue | 否 | None | 可视化队列（可选） |
| `report_hz` | float | 否 | 1.0 | 位置和目标上报频率，单位 Hz |
| `task_hz` | float | 否 | 0.2 | 任务轮询频率，单位 Hz |

#### 主要方法

- `run()`: 启动客户端主循环（阻塞，持续运行直到调用 stop()）
- `stop()`: 停止客户端运行
- `login() -> bool`: 手动执行登录，返回登录是否成功

## 使用示例

### 单设备示例

```python
from ivas import IVASClient
import threading
import time

# 配置
client = IVASClient(
    device_code=1,
    account='ZSDX001',
    password='your_password',
    base_lat=23.0,
    base_lon=113.0,
    base_alt=100.0,
    coord_range={'lat_offset': 0.001, 'lon_offset': 0.001, 'alt_offset': 10.0},
    base_url='http://localhost:5001',
    report_hz=1.0,
    task_hz=0.2
)

# 启动客户端
thread = threading.Thread(target=client.run, daemon=True)
thread.start()

# 运行一段时间后停止
try:
    time.sleep(60)  # 运行 60 秒
except KeyboardInterrupt:
    pass

client.stop()
thread.join(timeout=2)
```

### 多设备示例

```python
from ivas import IVASClient
import threading

# 配置多个设备
devices = [
    {'device_code': 1, 'account': 'ZSDX001', 'password': 'pwd1', 'base_lat': 23.0, 'base_lon': 113.0},
    {'device_code': 2, 'account': 'ZSDX002', 'password': 'pwd2', 'base_lat': 23.001, 'base_lon': 113.001},
    {'device_code': 3, 'account': 'ZSDX003', 'password': 'pwd3', 'base_lat': 23.002, 'base_lon': 113.002}
]

clients = []
threads = []

for device in devices:
    # 补充通用配置
    device.update({
        'base_alt': 100.0,
        'coord_range': {'lat_offset': 0.001, 'lon_offset': 0.001, 'alt_offset': 10.0},
        'base_url': 'http://localhost:5001',
        'report_hz': 1.0,
        'task_hz': 0.2
    })

    client = IVASClient(**device)
    clients.append(client)

    thread = threading.Thread(target=client.run, daemon=True)
    thread.start()
    threads.append(thread)

# 等待运行...
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    for client in clients:
        client.stop()
```

## 项目结构

```
ivas/
├── __init__.py          # 包初始化，导出 IVASClient
├── client.py            # 核心客户端实现
├── setup.py             # pip 安装配置
├── requirements.txt     # 依赖列表
├── README.md            # 本文档
├── docs/                # 📚 文档目录
│   ├── API_GUIDE.md    # 接口详细说明和数据包格式
│   └── INSTALL.md      # 安装部署指南
└── examples/            # 💡 示例代码
    └── example.py      # 单设备/多设备使用示例
```

## 核心功能说明

### 1. 自动登录
客户端启动时会自动调用登录接口获取 token，无需手动处理。

### 2. 位置上报
按配置的 `report_hz` 频率自动生成并上报无人机位置数据：
- 设备编号
- GPS 坐标（纬度、经度、海拔）
- 方位角
- 运动状态等

### 3. 目标检测上报
按配置的 `report_hz` 频率自动生成并上报目标检测数据：
- 检测到的目标数量
- 目标类型（人、车、飞机）
- 目标位置
- 边界框坐标等

### 4. 任务轮询
按配置的 `task_hz` 频率从服务器获取任务指令。

### 5. Token 过期处理
当检测到 401 错误（token 过期）时，自动重新登录获取新 token 并重试请求。

## 依赖项

- Python >= 3.7
- requests >= 2.25.0

## 注意事项

1. **服务器连接**: 确保 IVAS 服务器已启动并可访问
2. **账号密码**: 使用正确的账号和密码
3. **频率设置**: 根据实际需求和服务器性能调整上报频率
4. **多设备**: 运行多个设备时注意服务器负载
5. **线程安全**: 建议在独立线程中运行客户端

## 故障排除

### 导入错误
```python
# 如果出现导入错误，检查路径设置
import sys
sys.path.insert(0, '/path/to/ivas/parent_directory')
from ivas import IVASClient
```

### 连接失败
- 检查服务器地址是否正确
- 确认服务器是否已启动
- 检查网络连接

### 登录失败
- 验证账号密码是否正确
- 检查服务器日志

## 开发模式

如需修改 SDK 代码，建议使用可编辑模式安装：

```bash
pip install -e .
```

这样修改代码后无需重新安装即可生效。

## 版本信息

- **版本**: 1.0.0
- **Python**: >= 3.7
- **许可证**: MIT

## 📖 相关文档

- **[API_GUIDE.md](docs/API_GUIDE.md)** - 接口操作顺序、数据包格式、完整调用示例
- **[INSTALL.md](docs/INSTALL.md)** - 安装部署指南、不同场景的安装方法
- **[example.py](examples/example.py)** - 单设备和多设备使用示例代码

## 技术支持

如有问题或建议，请联系 IVAS 开发团队。
