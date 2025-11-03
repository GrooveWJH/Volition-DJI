# 相机变焦控制功能使用指南

## 功能概述

DJI 无人机 Python SDK 现已支持相机变焦控制功能。您可以在直播过程中使用键盘方向键实时调整相机变焦倍数。

## 新增功能

### 1. djisdk 库新增 `set_camera_zoom()` 函数

**函数签名：**
```python
set_camera_zoom(
    mqtt_client: MQTTClient,
    payload_index: str,
    zoom_factor: float,
    camera_type: str = "zoom",
    seq: int | None = None
) -> None
```

**参数说明：**
- `mqtt_client`: MQTT 客户端实例
- `payload_index`: 相机枚举值（格式: `{type-subtype-gimbalindex}`，例如 `"88-0-0"`）
- `zoom_factor`: 变焦倍数
  - 可见光相机（zoom/wide）: 2-200
  - 红外相机（ir）: 2-20
- `camera_type`: 相机类型（`"zoom"` | `"wide"` | `"ir"`，默认 `"zoom"`）
- `seq`: 序列号（可选，默认自动生成时间戳）

**使用示例：**
```python
from djisdk import MQTTClient, set_camera_zoom

# 初始化 MQTT 客户端
mqtt = MQTTClient("GATEWAY_SN", mqtt_config)
mqtt.connect()

# 设置变焦倍数为 10x
set_camera_zoom(mqtt, payload_index="88-0-0", zoom_factor=10.0)

# 设置红外相机变焦
set_camera_zoom(mqtt, payload_index="88-0-0", zoom_factor=5.0, camera_type="ir")
```

### 2. live.py 增强：键盘控制变焦

**运行直播工具：**
```bash
python3 live.py
```

**操作方式：**
1. 按照提示选择无人机并建立连接
2. 等待无人机进入 DRC 模式并开始直播
3. 直播开始后，进入键盘控制模式：

   **控制按键：**
   - `↑` (上箭头) - 放大（zoom in），每次增加 0.5x
   - `↓` (下箭头) - 缩小（zoom out），每次减少 0.5x
   - `q` 或 `ESC` - 退出并停止直播

**屏幕输出示例：**
```
========== 变焦控制模式 ==========
使用方向键控制变焦：
  ↑ - 放大 (zoom in)
  ↓ - 缩小 (zoom out)
  q 或 ESC - 退出并停止直播

当前变焦: 2.0x (范围: 2.0-200.0x)

↑ 放大至 2.5x
→ 变焦指令已发送: zoom zoom=2.5x (payload: 88-0-0)

↑ 放大至 3.0x
→ 变焦指令已发送: zoom zoom=3.0x (payload: 88-0-0)
```

## 技术实现细节

### DRC 下行指令格式

变焦控制使用 DJI Cloud API 的 DRC 下行指令：

**Topic:** `thing/product/{gateway_sn}/drc/down`

**Method:** `drc_camera_focal_length_set`

**Payload 示例：**
```json
{
    "seq": 1234567890,
    "method": "drc_camera_focal_length_set",
    "data": {
        "payload_index": "88-0-0",
        "camera_type": "zoom",
        "zoom_factor": 10.0
    }
}
```

### 特性说明

1. **Fire-and-forget 模式**：变焦指令使用 QoS 0 发送，无响应回包
2. **参数校验**：自动检查变焦倍数是否在有效范围内
3. **实时控制**：键盘输入立即生效，无需等待
4. **边界保护**：到达最大/最小变焦时会提示，不会发送无效指令

## 配置说明

### live.py 配置项

在 `live.py` 文件中可以修改以下配置：

```python
# 变焦控制参数（在 zoom_control_loop 函数中）
zoom_factor = 2.0       # 初始变焦倍数
zoom_step = 0.5         # 每次调整步长
min_zoom = 2.0          # 最小变焦
max_zoom = 200.0        # 最大变焦（可见光）
```

### 相机类型适配

如果需要控制不同类型的相机，修改 `main()` 函数中的调用：

```python
# 可见光相机（默认）
zoom_control_loop(mqtt, payload_index, camera_type="zoom")

# 红外相机
zoom_control_loop(mqtt, payload_index, camera_type="ir")

# 广角相机
zoom_control_loop(mqtt, payload_index, camera_type="wide")
```

## 测试验证

所有功能已通过以下测试：
- ✅ 基本变焦功能测试
- ✅ 参数验证测试（无效相机类型、超出范围的变焦倍数）
- ✅ 边界情况测试（最小/最大变焦）
- ✅ MQTT 消息格式验证

## 文件变更清单

1. **djisdk/services/drc_commands.py** - 新增 `set_camera_zoom()` 函数
2. **djisdk/services/__init__.py** - 导出 `set_camera_zoom`
3. **djisdk/__init__.py** - 顶层导出 `set_camera_zoom`
4. **live.py** - 新增键盘控制功能
   - 新增 `get_key()` - 读取键盘输入
   - 新增 `zoom_control_loop()` - 变焦控制循环
   - 修改 `main()` - 集成键盘控制

## 注意事项

1. **键盘控制仅在 Unix/Linux/macOS 系统上可用**（使用 `termios` 模块）
2. **需要在终端中运行**，不支持某些 IDE 的集成终端
3. **确保无人机已进入 DRC 模式**，否则变焦指令无法生效
4. **变焦范围因相机型号而异**，请根据实际相机调整参数

## 故障排查

### 问题：按键无响应

**解决方法：**
- 检查终端是否支持原始模式输入
- 尝试在标准终端（Terminal.app / iTerm2 / gnome-terminal）中运行
- 确认程序已进入变焦控制模式

### 问题：变焦指令发送失败

**解决方法：**
- 检查 MQTT 连接状态
- 确认无人机已进入 DRC 模式
- 验证 payload_index 是否正确（可通过 `mqtt.get_payload_index()` 获取）

### 问题：变焦无效果

**解决方法：**
- 检查相机类型是否匹配（可见光/红外）
- 确认变焦倍数在有效范围内
- 查看无人机端是否接收到指令

## 扩展开发

如需添加其他相机控制功能，可参考 `set_camera_zoom()` 的实现模式：

1. 在 `djisdk/services/drc_commands.py` 中添加新函数
2. 使用 DRC 下行 topic: `thing/product/{gateway_sn}/drc/down`
3. 设置正确的 method 和 data
4. QoS 0，Fire-and-forget 模式
5. 导出到 `services/__init__.py` 和 `djisdk/__init__.py`

---

**版本信息：**
- djisdk: 1.0.0
- Python: 3.8+
- 依赖: paho-mqtt, rich

**更新日期：** 2025-11-03
