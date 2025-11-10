# 归档文档说明

本目录包含已过时或历史参考的文档，保留用于追溯历史问题和解决思路。

**归档日期**: 2025-01-10

---

## 📦 归档文件列表

### ❌ 完全过时（内容已被新文档取代）

| 文档 | 原因 | 替代文档 |
|------|------|---------|
| `MOCK_SIMULATOR_GUIDE.md` | 内容已被 IVAS 架构文档取代 | [IVAS 系统架构](../../ivas/ARCHITECTURE.md) |
| `live_tool_guide.md` | 功能已废弃，相关代码已移除 | - |
| `TRAJECTORY_REFACTOR.md` | 重构已完成，仅为历史记录 | [TRAJECTORY_GUIDE.md](../TRAJECTORY_GUIDE.md) |

### ⚠️ 历史参考（问题已解决，保留作为参考）

| 文档 | 原因 | 状态 |
|------|------|------|
| `MQTT_CLIENT_ID_FIX.md` | MQTT 客户端 ID 冲突问题修复记录 | 已修复 |
| `DATA_LOGGING_README.md` | control 模块数据日志记录说明 | 功能稳定，IVAS 系统不使用 |

---

## 🔍 查阅建议

### 如果您遇到类似问题
1. **MQTT 连接冲突**: 查阅 `MQTT_CLIENT_ID_FIX.md` 了解解决思路
2. **轨迹系统设计**: 查阅 `TRAJECTORY_REFACTOR.md` 了解重构历史
3. **数据日志系统**: 查阅 `DATA_LOGGING_README.md` 了解 control 模块日志格式

### 如果您需要删除历史文档
```bash
# 删除所有归档文档（谨慎操作）
rm -rf docs/archive/
```

---

## 📚 活跃文档

查看当前有效的文档列表：[README_DOCS.md](../README_DOCS.md)

---

**维护者**: System Architecture Team
