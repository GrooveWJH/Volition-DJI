# IVAS Mock/Production 模式使用指南

本指南介绍如何在 Mock 模式（本地测试）和 Production 模式（真实部署）之间切换 IVAS 服务器。

---

## 🎯 概述

IVAS 系统现在支持两种运行模式：

| 模式 | 服务器地址 | 用途 | 环境变量 |
|------|-----------|------|---------|
| **Mock 模式** | `http://localhost:5001` | 本地测试、开发、演示 | `IVAS_BASE_URL=http://localhost:5001` |
| **Production 模式** | `http://192.168.31.38:8888` | 真实部署、生产环境 | (默认，无需设置) |

---

## 🚀 快速开始

### 1️⃣ Mock 模式测试流程

**步骤 1: 启动 Mock IVAS 服务器**

```bash
cd /home/groove/work/Volition-DJI/pythonSDK
python ivas/task_mock_server.py
```

**终端输出：**
```
======================================
  IVAS Mock 测试服务器
======================================
  地址: http://localhost:5001
  队列: 设备 1, 2, 3
======================================

 * Serving Flask app 'task_mock_server'
 * Running on http://0.0.0.0:5001
```

---

**步骤 2: 启动键盘控制器（Mock 模式）**

在**新终端**中运行：

```bash
cd /home/groove/work/Volition-DJI/pythonSDK
IVAS_BASE_URL=http://localhost:5001 python ivas/keyboard_commander.py
```

**终端输出：**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃           IVAS 键盘控制器                                ┃
┃           服务器: http://localhost:5001                  ┃
┃           模式: Mock 模式                                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ 按键 ┃     任务名称     ┃      任务类型      ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│  1   │ 起飞到预设高度   │ mission=1          │
│  2   │ 降落             │ mission=2          │
│  3   │ 返航             │ mission=3          │
│  4   │ 飞向指定点       │ mission=4 (需坐标) │
│  k   │ 切换设备         │ 当前: 设备 1       │
│  s   │ 查看统计         │ Mock Server 状态   │
│  c   │ 清空队列         │ 清空所有任务       │
│  q   │ 退出             │ 关闭程序           │
└──────┴──────────────────┴────────────────────┘

当前控制设备: 1

选择任务 (输入按键):
```

---

**步骤 3: 运行客户端程序（Mock 模式）**

在**第三个终端**中运行：

```bash
cd /home/groove/work/Volition-DJI/pythonSDK
IVAS_BASE_URL=http://localhost:5001 python pure.py
```

或者使用快速启动脚本：

```bash
./start_mock_system.sh
# 然后选择: IVAS_BASE_URL=http://localhost:5001 python pure.py
```

---

### 2️⃣ Production 模式部署流程

**启动真实 IVAS 客户端（Production 模式）**

```bash
cd /home/groove/work/Volition-DJI/pythonSDK
python pure.py  # 默认即为 Production 模式
```

**终端输出：**
```
[IVAS] 服务器: http://192.168.31.38:8888
[IVAS] 设备: ZSDX001 (device_code=1)
```

---

## 📋 核心组件说明

### 1. Mock IVAS 服务器 (`ivas/task_mock_server.py`)

**功能：**
- 模拟真实 IVAS 服务器的任务队列管理
- 提供 REST API 接口（登录、任务下发、任务拉取）
- 支持多设备任务队列（设备 1, 2, 3）
- 支持广播模式（device_id=99 → 所有设备）

**API 端点：**
```
POST /jk-ivas/third/login              # 模拟登录
POST /jk-ivas/third/controller/outdoorTask  # 任务拉取
POST /mock/push_task                   # 推送任务到队列
GET  /mock/stats                       # 查看统计信息
POST /mock/clear                       # 清空所有队列
```

**启动方式：**
```bash
python ivas/task_mock_server.py
```

---

### 2. 键盘控制器 (`ivas/keyboard_commander.py`)

**功能：**
- 通过键盘发送任务指令到 IVAS 服务器
- 支持 Mock/Production 模式切换
- 支持单机/广播模式（设备 1-3 或 99）

**使用示例：**
```bash
# Mock 模式
IVAS_BASE_URL=http://localhost:5001 python ivas/keyboard_commander.py

# Production 模式（默认）
python ivas/keyboard_commander.py
```

**键盘操作：**
- `1-7`: 发送任务 1-7
- `k`: 切换设备（1, 2, 3, 99）
- `s`: 查看 Mock Server 统计（仅 Mock 模式）
- `c`: 清空队列（仅 Mock 模式）
- `q`: 退出

---

### 3. 配置文件 (`config.py`)

**IVAS 模式配置：**
```python
import os

# IVAS 服务器配置
# 支持环境变量切换测试/生产环境
IVAS_SERVER = {
    'base_url': os.getenv('IVAS_BASE_URL', 'http://192.168.31.38:8888'),
    'report_hz': 1.0,
    'task_hz': 2.0,
}
```

**环境变量使用：**
```bash
# Mock 模式：设置 IVAS_BASE_URL 为本地服务器
IVAS_BASE_URL=http://localhost:5001 python pure.py

# Production 模式：不设置环境变量，使用默认值
python pure.py
```

---

## 🔧 常见使用场景

### 场景 1: 本地开发测试

```bash
# 终端 1: 启动 Mock Server
python ivas/task_mock_server.py

# 终端 2: 启动键盘控制器（Mock 模式）
IVAS_BASE_URL=http://localhost:5001 python ivas/keyboard_commander.py

# 终端 3: 运行客户端（Mock 模式）
IVAS_BASE_URL=http://localhost:5001 python pure.py

# 在键盘控制器中按 '1' 发送起飞任务
# 客户端会立即收到任务并执行
```

---

### 场景 2: 室内系统测试

```bash
# 终端 1: 启动 Mock Server
python ivas/task_mock_server.py

# 终端 2: 运行室内指挥端（Mock 模式）
IVAS_MODE=mock python indoor_commander.py

# 终端 3: 启动键盘控制器
IVAS_MODE=mock python ivas/keyboard_commander.py

# 室内指挥端会轮询任务并转发到 MQTT
```

---

### 场景 3: 生产部署

```bash
# 直接运行（默认 Production 模式）
python pure.py

# 或显式指定
IVAS_MODE=production python pure.py
```

---

## 📊 Mock Server 功能演示

### 查看队列统计

在键盘控制器中按 `s` 键：

```
Mock Server 统计
  任务推送总数: 12
  任务拉取总数: 8
  当前队列状态:
    设备 1: 3 个任务
    设备 2: 1 个任务
    设备 3: 0 个任务
```

### 清空所有队列

在键盘控制器中按 `c` 键：

```
✓ 已清空所有队列，共清除 4 个任务
```

### 广播模式

在键盘控制器中：
1. 按 `k` → 输入 `99` → 切换到广播模式
2. 按 `1` → 发送起飞任务到所有设备

```
✓ 服务器已广播到设备: [1, 2, 3]
```

---

## 🛠️ 故障排查

### 问题 1: Mock Server 启动失败

**错误：**
```
Address already in use
```

**解决方案：**
```bash
# 检查端口占用
lsof -ti:5001

# 杀掉占用进程
lsof -ti:5001 | xargs kill
```

---

### 问题 2: 客户端连接失败

**错误：**
```
[red]✗ 任务发送失败[/red]
```

**检查清单：**
1. ✅ Mock Server 是否启动？(`python ivas/task_mock_server.py`)
2. ✅ 环境变量是否设置？(`IVAS_MODE=mock`)
3. ✅ 网络连接是否正常？(`curl http://localhost:5001`)

---

### 问题 3: 模式混淆

**症状：** 客户端使用 Mock 模式，但连接到 Production 服务器

**解决方案：**
```bash
# 检查当前配置
python -c "from config import IVAS_MODE, IVAS_SERVER; print(f'模式: {IVAS_MODE}, 服务器: {IVAS_SERVER[\"base_url\"]}')"

# 输出应为：
# 模式: mock, 服务器: http://localhost:5001
```

---

## 📝 开发建议

### ✅ 推荐做法

1. **本地开发时使用 Mock 模式**
   ```bash
   IVAS_MODE=mock python pure.py
   ```

2. **生产部署前测试 Production 模式**
   ```bash
   IVAS_MODE=production python pure.py
   ```

3. **使用 `.env` 文件管理环境变量**（可选）
   ```bash
   # .env
   IVAS_MODE=mock
   ```

---

### ❌ 避免做法

1. ❌ 修改 `config.py` 中的硬编码值来切换模式
2. ❌ 在生产环境中运行 Mock Server
3. ❌ 混用 Mock/Production 配置（确保所有组件使用相同模式）

---

## 🔗 相关文件

| 文件 | 功能 | 位置 |
|------|------|------|
| `config.py` | 统一配置管理 | `/home/groove/work/Volition-DJI/pythonSDK/config.py` |
| `task_mock_server.py` | Mock IVAS 服务器 | `/home/groove/work/Volition-DJI/pythonSDK/ivas/task_mock_server.py` |
| `keyboard_commander.py` | 键盘任务控制器 | `/home/groove/work/Volition-DJI/pythonSDK/ivas/keyboard_commander.py` |
| `start_mock_system.sh` | 快速启动脚本 | `/home/groove/work/Volition-DJI/pythonSDK/start_mock_system.sh` |
| `pure.py` | 主客户端程序 | `/home/groove/work/Volition-DJI/pythonSDK/pure.py` |
| `indoor_commander.py` | 室内指挥端 | `/home/groove/work/Volition-DJI/pythonSDK/indoor_commander.py` |

---

## 📚 总结

- **Mock 模式**: `IVAS_MODE=mock` → 本地测试，无需真实服务器
- **Production 模式**: `IVAS_MODE=production` → 真实部署，连接生产服务器
- **快速切换**: 仅需修改环境变量，无需改代码
- **统一配置**: 所有程序从 `config.py` 读取配置，保证一致性

---

**🎉 现在你可以在 Mock 和 Production 模式之间无缝切换了！**
