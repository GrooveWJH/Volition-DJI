# IVAS SDK 安装指南

本文档说明如何安装和部署 IVAS Python SDK。

## 系统要求

- Python >= 3.7
- pip (Python 包管理器)

## 安装方法

### 方法 1: 直接使用（推荐，无需安装）

将整个 `ivas` 目录复制到你的项目中，然后直接导入：

```python
from ivas import IVASClient
```

**适用场景**:
- 快速集成
- 不想污染系统 Python 环境
- 需要在多个项目间共享代码

### 方法 2: 通过 pip 安装

#### 2.1 从本地目录安装

```bash
# 进入 ivas 目录
cd /path/to/ivas

# 安装依赖
pip install -r requirements.txt

# 安装包（生产环境）
pip install .

# 或者安装为可编辑模式（开发环境，推荐）
pip install -e .
```

#### 2.2 在虚拟环境中安装（推荐）

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 进入 ivas 目录
cd /path/to/ivas

# 安装
pip install -e .

# 使用完毕后退出虚拟环境
deactivate
```

### 方法 3: 添加到 Python 路径

在你的代码开头添加：

```python
import sys
import os

# 添加 ivas 所在目录到 Python 路径
sys.path.insert(0, '/path/to/ivas/parent_directory')

from ivas import IVASClient
```

## 验证安装

### 测试导入

```bash
python3 -c "from ivas import IVASClient; print('✓ IVAS SDK 安装成功')"
```

### 运行示例程序

```bash
cd /path/to/ivas
python3 example.py
```

## 依赖项

IVAS SDK 只依赖一个外部库：

- `requests >= 2.25.0`: HTTP 客户端库

手动安装依赖：

```bash
pip install requests
```

或使用 requirements.txt：

```bash
pip install -r requirements.txt
```

## 目录结构

安装后的目录结构：

```
ivas/
├── __init__.py          # 包初始化
├── client.py            # 核心客户端实现
├── example.py           # 使用示例
├── setup.py             # 安装配置
├── requirements.txt     # 依赖列表
├── README.md            # 使用文档
├── API_GUIDE.md         # 接口详细说明
└── INSTALL.md           # 本文件
```

## 部署场景

### 场景 1: 开发环境

使用可编辑模式安装，方便修改代码：

```bash
cd /path/to/ivas
pip install -e .
```

### 场景 2: 生产环境

使用正式安装模式：

```bash
cd /path/to/ivas
pip install .
```

### 场景 3: 嵌入式设备/受限环境

直接复制 `ivas` 目录到设备，无需安装：

```bash
# 复制目录
scp -r ivas/ user@device:/opt/

# 在设备上使用
python3 << EOF
import sys
sys.path.insert(0, '/opt')
from ivas import IVASClient
# ... 使用 SDK
EOF
```

### 场景 4: Docker 容器

在 Dockerfile 中：

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 复制 ivas 目录
COPY ivas/ /app/ivas/

# 安装依赖
RUN pip install -r ivas/requirements.txt

# 或者安装包
# RUN pip install /app/ivas/

# 运行应用
CMD ["python3", "ivas/example.py"]
```

## 卸载

### 如果通过 pip 安装

```bash
pip uninstall ivas
```

### 如果直接使用

删除 `ivas` 目录即可。

## 更新

### 更新通过 pip 安装的版本

```bash
cd /path/to/ivas
pip install --upgrade .
```

### 更新可编辑模式安装

可编辑模式下，直接修改源码即可，无需重新安装。

## 故障排除

### 问题 1: 导入错误

```
ImportError: No module named 'ivas'
```

**解决方法**:
1. 检查是否正确安装
2. 检查 Python 路径设置
3. 尝试使用绝对路径导入

### 问题 2: 依赖错误

```
ImportError: No module named 'requests'
```

**解决方法**:
```bash
pip install requests
```

### 问题 3: 权限错误

```
PermissionError: [Errno 13] Permission denied
```

**解决方法**:
- 使用虚拟环境
- 或者使用 `--user` 参数: `pip install --user .`

### 问题 4: Python 版本不兼容

确保使用 Python 3.7 或更高版本：

```bash
python3 --version
```

## 技术支持

如有安装问题，请：

1. 查看 README.md 获取更多信息
2. 检查 Python 版本和依赖
3. 联系 IVAS 开发团队

## 相关文档

- [README.md](../README.md) - 使用文档
- [API_GUIDE.md](API_GUIDE.md) - 接口详细说明
- [example.py](../examples/example.py) - 使用示例

---

**文档版本**: 1.0.0
**最后更新**: 2025-11-06
