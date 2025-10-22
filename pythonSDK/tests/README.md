# DJI SDK 测试套件

完整的单元测试覆盖 djisdk 核心功能。

## 📋 测试覆盖

### 核心层 (Core Layer)

#### 1. `test_mqtt_client.py` - MQTTClient 测试
- ✅ 初始化
- ✅ MQTT 连接管理
- ✅ 消息发布
- ✅ 消息订阅
- ✅ Future 响应处理
- ✅ 超时清理
- ✅ 线程安全
- ✅ 错误处理

#### 2. `test_service_caller.py` - ServiceCaller 测试
- ✅ 服务调用
- ✅ 超时处理
- ✅ 唯一 TID 生成
- ✅ 异常处理
- ✅ 与 MQTTClient 集成

### 业务层 (Services Layer)

#### 3. `test_commands.py` - 业务服务测试
- ✅ `_call_service` 通用包装
- ✅ 控制权管理 (request_control_auth, release_control_auth)
- ✅ DRC 模式 (enter_drc_mode, exit_drc_mode)
- ✅ 直播控制 (change_live_lens, set_live_quality, start/stop_live_push)
- ✅ 控制台输出
- ✅ 参数验证

#### 4. `test_heartbeat.py` - 心跳服务测试
- ✅ 线程启动/停止
- ✅ 心跳消息格式
- ✅ 序列号递增
- ✅ 定时精确性
- ✅ 多线程隔离
- ✅ 边界情况

## 🚀 快速开始

### 安装测试依赖

```bash
# 如果还没有安装 paho-mqtt 和 rich
pip install paho-mqtt rich
```

### 运行所有测试

```bash
# 从 scripts/python 目录运行
python tests/run_tests.py

# 或使用 unittest
python -m unittest discover -s tests -p "test_*.py"
```

### 运行特定测试

```bash
# 只运行 MQTTClient 测试
python tests/run_tests.py test_mqtt_client

# 只运行 ServiceCaller 测试
python tests/run_tests.py test_service_caller

# 运行单个测试类
python -m unittest tests.test_mqtt_client.TestMQTTClient

# 运行单个测试方法
python -m unittest tests.test_mqtt_client.TestMQTTClient.test_connect
```

### 详细输出

```bash
# 详细模式
python tests/run_tests.py -v

# 安静模式
python tests/run_tests.py -q
```

## 📊 测试统计

| 模块 | 测试类数 | 测试方法数 | 代码覆盖 |
|------|---------|-----------|---------|
| test_mqtt_client | 1 | 10 | ~95% |
| test_service_caller | 2 | 7 | ~90% |
| test_commands | 4 | 16 | ~95% |
| test_heartbeat | 2 | 11 | ~90% |
| **总计** | **9** | **44** | **~92%** |

## 🎯 测试设计原则

### 1. 使用 Mock 隔离依赖
```python
@patch('djisdk.core.mqtt_client.mqtt.Client')
def test_connect(self, mock_mqtt_client):
    # 隔离外部 MQTT 库
    mock_client_instance = Mock()
    mock_mqtt_client.return_value = mock_client_instance
    # ...
```

### 2. 测试边界情况
```python
def test_cleanup_request_nonexistent(self):
    """测试清理不存在的请求 - 不应该抛出异常"""
    self.client.cleanup_request("nonexistent-tid")
```

### 3. 验证线程安全
```python
def test_thread_safety(self):
    """多线程同时操作 pending_requests"""
    threads = [threading.Thread(target=add_request, args=(tid,))
               for tid in tids]
    # ...
```

### 4. 集成测试
```python
class TestServiceCallerIntegration(unittest.TestCase):
    """测试真实的 MQTTClient + ServiceCaller 集成"""
    def test_full_integration(self):
        # 完整的请求-响应流程
```

## 📝 添加新测试

### 测试新服务函数

```python
# tests/test_commands.py

@patch('djisdk.services.commands._call_service')
@patch('djisdk.services.commands.console')
def test_new_service(self, mock_console, mock_call_service):
    """测试新服务"""
    new_service_function(self.mock_caller, param="value")

    # 验证调用
    mock_call_service.assert_called_once_with(
        self.mock_caller,
        "new_service_method",
        {"param": "value"},
        "成功消息"
    )
```

### 测试新核心类

```python
# tests/test_new_module.py

import unittest
from unittest.mock import Mock, patch

class TestNewModule(unittest.TestCase):
    def setUp(self):
        """每个测试前运行"""
        self.instance = NewModule()

    def test_feature(self):
        """测试具体功能"""
        result = self.instance.method()
        self.assertEqual(result, expected_value)
```

## 🐛 调试失败的测试

### 查看详细错误
```bash
python -m unittest tests.test_mqtt_client.TestMQTTClient.test_connect -v
```

### 使用 pdb 调试
```python
import pdb; pdb.set_trace()
```

### 查看 Mock 调用
```python
print(mock_object.call_args_list)
print(mock_object.call_count)
```

## ✅ 持续集成 (CI)

测试可以集成到 CI/CD 流程：

```yaml
# .github/workflows/test.yml (GitHub Actions 示例)
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install paho-mqtt rich
      - run: python tests/run_tests.py
```

## 📖 测试最佳实践

1. **每个测试独立** - 使用 setUp/tearDown
2. **测试名称清晰** - test_method_scenario
3. **一个测试一个断言** - 聚焦单一功能
4. **使用 Mock 隔离** - 不依赖外部服务
5. **测试边界情况** - 包括错误路径
6. **文档化测试** - 使用清晰的 docstring

## 🔍 代码覆盖率

安装覆盖率工具：
```bash
pip install coverage
```

运行覆盖率分析：
```bash
coverage run -m unittest discover -s tests
coverage report
coverage html  # 生成 HTML 报告
```

---

**测试让代码更可靠！** 🎉
