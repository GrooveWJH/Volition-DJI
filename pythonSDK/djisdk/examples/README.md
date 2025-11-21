# DJI SDK 示例代码

本目录包含 djisdk 的常见使用示例。

## 📁 示例列表

### 基础操作
- `basic_connection.py` - 建立基础DRC连接
- `flight_control.py` - 基础飞行控制
- `data_monitoring.py` - 数据监控和状态检查

### 高级功能
- `multi_drone.py` - 多机并行控制
- `trajectory_flight.py` - CSV轨迹飞行
- `live_streaming.py` - 视频直播控制

### 完整应用
- `inspection_mission.py` - 自动巡检任务
- `formation_flight.py` - 编队飞行
- `emergency_landing.py` - 紧急情况处理

## 🚀 快速开始

```bash
# 运行基础连接示例
python examples/basic_connection.py

# 运行多机控制示例
python examples/multi_drone.py
```

## 📝 使用说明

1. 修改示例中的配置参数（SN、MQTT配置等）
2. 确保无人机已连接并处于可控状态
3. 在安全环境下运行测试代码

## ⚠️ 安全注意

- 所有示例仅供学习和测试使用
- 实际飞行前请确保环境安全
- 建议先在模拟器或室内进行测试