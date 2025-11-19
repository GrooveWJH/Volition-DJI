# Python 导入系统完全指南

## 目录
1. [导入基础](#1-导入基础)
2. [绝对导入 vs 相对导入](#2-绝对导入-vs-相对导入)
3. [sys.path 和模块搜索路径](#3-syspath-和模块搜索路径)
4. [__name__, __package__, __file__ 详解](#4-__name__-__package__-__file__-详解)
5. [运行方式的区别](#5-运行方式的区别)
6. [常见问题和解决方案](#6-常见问题和解决方案)
7. [最佳实践](#7-最佳实践)

---

## 1. 导入基础

### 1.1 导入语法

```python
# 导入整个模块
import math
import os

# 导入并重命名
import numpy as np

# 从模块导入特定对象
from math import sqrt, pi
from os import path

# 导入模块中的所有公开对象（不推荐）
from math import *

# 从包导入子模块
from collections import defaultdict
from os.path import join, exists
```

### 1.2 包（Package）vs 模块（Module）

```
项目结构示例：
myproject/
├── __init__.py          # 使 myproject 成为包
├── module1.py           # 模块
├── module2.py           # 模块
└── subpackage/
    ├── __init__.py      # 使 subpackage 成为包
    ├── module3.py       # 子模块
    └── module4.py       # 子模块
```

- **模块（Module）**: 单个 `.py` 文件
- **包（Package）**: 包含 `__init__.py` 的目录（Python 3.3+ 可以没有 `__init__.py`，称为命名空间包）

---

## 2. 绝对导入 vs 相对导入

### 2.1 绝对导入（Absolute Import）

从项目根目录或 `sys.path` 中的路径开始导入。

```python
# 假设目录结构：
# pythonSDK/
# ├── djisdk/
# │   ├── __init__.py
# │   └── core/
# │       └── mqtt_client.py
# └── utils/
#     └── keyboardControl.py

# 在 utils/keyboardControl.py 中使用绝对导入
from djisdk import MQTTClient
from djisdk.core.mqtt_client import MQTTClient
```

**特点：**
- ✅ 清晰明确，路径从根开始
- ✅ 适合任何运行方式（直接运行、模块运行）
- ✅ 易于理解和维护
- ❌ 如果包名改变，需要修改所有导入语句

### 2.2 相对导入（Relative Import）

使用 `.` 和 `..` 表示当前包和父包。

```python
# 假设目录结构：
# myproject/
# ├── __init__.py
# ├── module1.py
# └── subpackage/
#     ├── __init__.py
#     ├── module2.py
#     └── module3.py

# 在 subpackage/module2.py 中：
from . import module3           # 导入同级模块
from .module3 import SomeClass  # 从同级模块导入
from .. import module1          # 导入父包中的模块
from ..module1 import func      # 从父包模块导入
```

**相对导入规则：**
- `.` = 当前包
- `..` = 父包
- `...` = 父包的父包（依此类推）

**特点：**
- ✅ 包重命名时不需要修改导入
- ✅ 明确表示包内部关系
- ❌ **只能在包内使用，不能在直接运行的脚本中使用**
- ❌ 可读性较差（多个 `..` 时）

### 2.3 相对导入的限制

**核心问题：相对导入需要 `__package__` 属性，直接运行的脚本没有这个属性。**

```python
# utils/keyboardControl.py
from ..djisdk import MQTTClient  # ❌ 直接运行会报错

# 运行：
# python utils/keyboardControl.py
# ImportError: attempted relative import with no known parent package
```

**为什么？**
- 直接运行时，`__name__` = `'__main__'`，`__package__` = `None`
- Python 不知道"父包"是谁

---

## 3. sys.path 和模块搜索路径

### 3.1 sys.path 是什么

`sys.path` 是一个列表，包含 Python 搜索模块的所有目录。

```python
import sys
print(sys.path)
# 输出示例：
# [
#     '/Users/user/project',           # 当前工作目录
#     '/usr/lib/python3.13',           # 标准库
#     '/usr/lib/python3.13/site-packages',  # 第三方库
#     ...
# ]
```

### 3.2 sys.path 的初始化

Python 启动时，`sys.path` 包含：

1. **当前脚本所在目录**（直接运行）或**当前工作目录**（模块运行）
2. `PYTHONPATH` 环境变量中的目录
3. 标准库目录
4. site-packages 目录（第三方库）

### 3.3 动态修改 sys.path

```python
import sys
import os

# 方法 1: 添加到开头（优先搜索）
sys.path.insert(0, '/path/to/directory')

# 方法 2: 添加到末尾
sys.path.append('/path/to/directory')

# 方法 3: 添加相对路径（常用于脚本）
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.insert(0, parent_dir)
```

**示例：解决相对导入问题**

```python
# utils/keyboardControl.py
import sys
import os

# 直接运行时，添加父目录到 sys.path
if __name__ == '__main__' and __package__ is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 现在可以使用绝对导入
from djisdk import MQTTClient
from utils.keyboard import generate_layout
```

### 3.4 PYTHONPATH 环境变量

```bash
# 设置 PYTHONPATH（临时）
export PYTHONPATH=/path/to/myproject:$PYTHONPATH

# 运行脚本
python utils/keyboardControl.py

# 或者一次性设置
PYTHONPATH=/path/to/myproject python utils/keyboardControl.py
```

---

## 4. __name__, __package__, __file__ 详解

### 4.1 `__name__`

- **直接运行**：`__name__` = `'__main__'`
- **被导入**：`__name__` = 模块的完整路径

```python
# module.py
print(f"__name__ = {__name__}")

if __name__ == '__main__':
    print("直接运行")
else:
    print("被导入")

# 运行：
# python module.py  →  __name__ = '__main__'，输出 "直接运行"
# import module     →  __name__ = 'module'，输出 "被导入"
```

### 4.2 `__package__`

- **直接运行**：`__package__` = `None`
- **作为模块运行**：`__package__` = 包名

```python
# utils/keyboardControl.py
print(f"__package__ = {__package__}")

# 运行方式 1: 直接运行
# python utils/keyboardControl.py
# __package__ = None

# 运行方式 2: 作为模块运行
# python -m utils.keyboardControl
# __package__ = 'utils'
```

**判断运行方式：**

```python
if __name__ == '__main__' and __package__ is None:
    print("直接运行脚本")
elif __name__ == '__main__':
    print("python -m 模块运行")
else:
    print("被导入")
```

### 4.3 `__file__`

当前文件的路径（可能是相对路径或绝对路径）。

```python
import os

print(__file__)
# 输出：utils/keyboardControl.py（相对路径）

# 获取绝对路径
abs_path = os.path.abspath(__file__)
print(abs_path)
# 输出：/Users/user/pythonSDK/utils/keyboardControl.py

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
print(script_dir)
# 输出：/Users/user/pythonSDK/utils

# 获取父目录
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
print(parent_dir)
# 输出：/Users/user/pythonSDK
```

---

## 5. 运行方式的区别

### 5.1 直接运行（Script Mode）

```bash
python utils/keyboardControl.py
```

**特点：**
- `__name__` = `'__main__'`
- `__package__` = `None`
- `sys.path[0]` = `'utils'`（脚本所在目录）
- **不能使用相对导入**

### 5.2 模块运行（Module Mode）

```bash
python -m utils.keyboardControl
```

**特点：**
- `__name__` = `'__main__'`
- `__package__` = `'utils'`
- `sys.path[0]` = 当前工作目录（通常是项目根目录）
- **可以使用相对导入**

### 5.3 被导入

```python
import utils.keyboardControl
# 或
from utils.keyboardControl import main
```

**特点：**
- `__name__` = `'utils.keyboardControl'`
- `__package__` = `'utils'`
- `if __name__ == '__main__'` 块不会执行

### 5.4 对比表

| 运行方式                        | `__name__`              | `__package__` | `sys.path[0]`        | 相对导入 |
|---------------------------------|-------------------------|---------------|----------------------|----------|
| `python script.py`              | `'__main__'`            | `None`        | 脚本所在目录         | ❌       |
| `python -m package.module`      | `'__main__'`            | `'package'`   | 当前工作目录         | ✅       |
| `import package.module`         | `'package.module'`      | `'package'`   | -                    | ✅       |

---

## 6. 常见问题和解决方案

### 6.1 问题：ImportError: attempted relative import with no known parent package

**原因：**
直接运行脚本时使用了相对导入。

**错误示例：**
```python
# utils/keyboardControl.py
from ..djisdk import MQTTClient  # ❌

# 运行：
# python utils/keyboardControl.py
# ImportError: attempted relative import with no known parent package
```

**解决方案 1：使用 python -m**

```bash
# 在项目根目录运行
python -m utils.keyboardControl  # ✅
```

**解决方案 2：动态路径 + 绝对导入（推荐，灵活性最高）**

```python
# utils/keyboardControl.py
import sys
import os

# 直接运行时，添加父目录到 sys.path
if __name__ == '__main__' and __package__ is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 尝试相对导入，失败则使用绝对导入
try:
    from ..djisdk import MQTTClient  # 模块运行时
except ImportError:
    from djisdk import MQTTClient    # 直接运行时
```

**解决方案 3：仅使用绝对导入**

```python
# utils/keyboardControl.py
import sys
import os

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 使用绝对导入
from djisdk import MQTTClient  # ✅
from utils.keyboard import generate_layout  # ✅
```

### 6.2 问题：ModuleNotFoundError: No module named 'xxx'

**原因：**
模块不在 `sys.path` 中。

**解决方案：**

```python
import sys
import os

# 方法 1: 添加到 sys.path
sys.path.insert(0, '/path/to/module/parent')

# 方法 2: 使用相对路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# 方法 3: 设置 PYTHONPATH
# export PYTHONPATH=/path/to/project:$PYTHONPATH
```

### 6.3 问题：循环导入（Circular Import）

**错误示例：**
```python
# module_a.py
from module_b import func_b

def func_a():
    return func_b()

# module_b.py
from module_a import func_a  # ❌ 循环导入

def func_b():
    return func_a()

# ImportError: cannot import name 'func_b' from partially initialized module 'module_b'
```

**解决方案 1：延迟导入**

```python
# module_a.py
def func_a():
    from module_b import func_b  # 在函数内导入
    return func_b()

# module_b.py
def func_b():
    from module_a import func_a
    return func_a()
```

**解决方案 2：重构代码**

将共享代码提取到第三个模块。

```python
# common.py
def shared_func():
    pass

# module_a.py
from common import shared_func

def func_a():
    return shared_func()

# module_b.py
from common import shared_func

def func_b():
    return shared_func()
```

### 6.4 问题：ImportError: cannot import name 'xxx' from 'yyy'

**原因：**
- 导入的对象不存在
- 模块初始化时出错
- 循环导入

**调试方法：**

```python
# 1. 检查模块是否能正常导入
import yyy
print(dir(yyy))  # 查看模块包含的所有对象

# 2. 检查对象是否存在
print(hasattr(yyy, 'xxx'))

# 3. 查看导入错误的详细信息
import traceback
try:
    from yyy import xxx
except ImportError as e:
    traceback.print_exc()
```

---

## 7. 最佳实践

### 7.1 包结构设计

```
myproject/
├── myproject/           # 主包（与项目同名）
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── module1.py
│   └── utils/
│       ├── __init__.py
│       └── module2.py
├── tests/               # 测试目录
│   ├── __init__.py
│   └── test_module1.py
├── scripts/             # 脚本目录
│   └── run.py
├── setup.py             # 安装配置
├── requirements.txt     # 依赖列表
└── README.md
```

### 7.2 导入规范

**推荐顺序（PEP 8）：**

```python
# 1. 标准库
import os
import sys
from pathlib import Path

# 2. 第三方库
import numpy as np
import requests
from rich.console import Console

# 3. 本地模块
from myproject.core import module1
from myproject.utils import module2
```

**导入风格：**

```python
# ✅ 推荐：明确导入
from math import sqrt, pi, sin

# ❌ 不推荐：导入所有（污染命名空间）
from math import *

# ✅ 推荐：导入模块，使用时带前缀
import numpy as np
result = np.array([1, 2, 3])

# ❌ 不推荐：直接导入函数（不清楚来源）
from numpy import array
result = array([1, 2, 3])  # array 来自哪里？
```

### 7.3 编写可直接运行 + 可导入的脚本

```python
#!/usr/bin/env python3
"""
模块文档字符串
"""
import sys
import os

# 动态路径处理（支持直接运行）
if __name__ == '__main__' and __package__ is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入（兼容两种运行方式）
try:
    from .module import func  # 相对导入（模块运行）
except ImportError:
    from package.module import func  # 绝对导入（直接运行）


def main():
    """主函数"""
    print("执行主逻辑")


if __name__ == '__main__':
    # 直接运行时执行
    main()
```

### 7.4 使用 __init__.py 管理导出

```python
# myproject/core/__init__.py

# 方法 1: 显式导入（推荐）
from .module1 import ClassA, func1
from .module2 import ClassB, func2

__all__ = ['ClassA', 'func1', 'ClassB', 'func2']

# 方法 2: 自动导入所有公开对象
from .module1 import *
from .module2 import *

# 使用时：
# from myproject.core import ClassA, func1
```

### 7.5 避免隐式相对导入（Python 2 遗留问题）

```python
# ❌ Python 2 风格（隐式相对导入）
import module  # 同级目录的 module.py

# ✅ Python 3 风格（显式相对导入）
from . import module

# ✅ 或使用绝对导入
from myproject.core import module
```

### 7.6 使用 __all__ 控制 import *

```python
# module.py
__all__ = ['public_func', 'PublicClass']

def public_func():
    pass

def _private_func():  # 下划线开头表示私有
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass

# 使用：
# from module import *
# 只导入 __all__ 中的对象：public_func, PublicClass
```

---

## 8. 实战案例：本项目的导入策略

### 8.1 项目结构

```
pythonSDK/
├── djisdk/              # DJI SDK 包
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── mqtt_client.py
│   │   └── service_caller.py
│   └── services/
│       ├── __init__.py
│       └── commands.py
└── utils/               # 工具包
    ├── __init__.py
    ├── keyboard.py
    └── keyboardControl.py
```

### 8.2 utils/keyboardControl.py 的导入策略

```python
#!/usr/bin/env python3
import sys
import os

# 1. 动态路径处理：支持直接运行
if __name__ == '__main__' and __package__ is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. 兼容两种运行方式
try:
    # 模块运行时（python -m utils.keyboardControl）
    from ..djisdk import MQTTClient, ServiceCaller
    from .keyboard import generate_layout, pressed_keys
except ImportError:
    # 直接运行时（python utils/keyboardControl.py）
    from djisdk import MQTTClient, ServiceCaller
    from utils.keyboard import generate_layout, pressed_keys


def main():
    # 主逻辑
    pass


if __name__ == '__main__':
    main()
```

### 8.3 运行方式

```bash
# 方式 1: 直接运行（推荐，简单直观）
python utils/keyboardControl.py

# 方式 2: 模块运行（适合包内调用）
python -m utils.keyboardControl

# 方式 3: 作为库导入
python -c "from utils.keyboardControl import main; main()"
```

---

## 9. 总结

### 关键要点

1. **绝对导入 vs 相对导入**
   - 绝对导入：从 `sys.path` 根开始，适合任何场景
   - 相对导入：只能在包内使用，不能直接运行

2. **sys.path**
   - Python 模块搜索路径列表
   - 可通过 `sys.path.insert()` 动态修改
   - 可通过 `PYTHONPATH` 环境变量设置

3. **运行方式**
   - `python script.py`：直接运行，`__package__` = `None`，不能用相对导入
   - `python -m module`：模块运行，`__package__` = 包名，可以用相对导入

4. **最佳实践**
   - 使用 `if __name__ == '__main__' and __package__ is None` 判断直接运行
   - 使用 `try/except ImportError` 兼容两种导入方式
   - 优先使用绝对导入（清晰明确）
   - 包内部使用相对导入（解耦）

### 调试技巧

```python
# 打印调试信息
print(f"__name__: {__name__}")
print(f"__package__: {__package__}")
print(f"__file__: {__file__}")
print(f"sys.path: {sys.path}")

# 检查模块内容
import module
print(dir(module))

# 查看导入路径
import module
print(module.__file__)
```

### 参考资料

- [PEP 328 - Imports: Multi-Line and Absolute/Relative](https://www.python.org/dev/peps/pep-0328/)
- [PEP 366 - Main module explicit relative imports](https://www.python.org/dev/peps/pep-0366/)
- [Python 官方文档 - 模块](https://docs.python.org/3/tutorial/modules.html)
- [Real Python - Absolute vs Relative Imports](https://realpython.com/absolute-vs-relative-python-imports/)
