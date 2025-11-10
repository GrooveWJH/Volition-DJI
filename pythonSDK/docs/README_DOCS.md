# 📚 文档目录说明

本文档说明 `docs/` 目录中各文档的用途、状态和推荐阅读顺序。

**最后更新**: 2025-01-10

---

## 📊 文档概览

| 文档名称 | 状态 | 用途 | 推荐度 |
|---------|------|------|--------|
| [IVAS 系统架构](../ivas/ARCHITECTURE.md) | ✅ 最新 | IVAS 完整架构说明（含 PlantUML） | ⭐⭐⭐⭐⭐ |
| [TRAJECTORY_GUIDE.md](#trajectory_guidemd) | ✅ 有效 | 轨迹飞行指南 | ⭐⭐⭐⭐⭐ |
| [QUICK_REFERENCE.md](#quick_referencemd) | ✅ 有效 | 快速参考手册 | ⭐⭐⭐⭐ |
| [PYTHON_IMPORT_GUIDE.md](#python_import_guidemd) | ✅ 有效 | Python 导入系统详解 | ⭐⭐⭐⭐ |
| [PID_TUNING_GUIDE.md](#pid_tuning_guidemd) | ⚠️ 参考 | PID 调参指南（control 模块） | ⭐⭐⭐ |
| [CONTROL_MODULE_GUIDE.md](#control_module_guidemd) | ⚠️ 参考 | 控制模块指南 | ⭐⭐⭐ |
| [JOYSTICK_UI_DESIGN.md](#joystick_ui_designmd) | ⚠️ 参考 | 虚拟摇杆 UI 设计 | ⭐⭐ |
| [MQTT_CLIENT_ID_FIX.md](#mqtt_client_id_fixmd) | ⚠️ 历史 | MQTT 客户端ID修复记录 | ⭐ |
| [DATA_LOGGING_README.md](#data_logging_readmemd) | ⚠️ 历史 | 数据日志记录说明（control 模块） | ⭐ |
| [MOCK_SIMULATOR_GUIDE.md](#mock_simulator_guidemd) | ❌ 过时 | 模拟器指南（已废弃） | ❌ |
| [live_tool_guide.md](#live_tool_guidemd) | ❌ 过时 | 直播工具指南（已废弃） | ❌ |
| [TRAJECTORY_REFACTOR.md](#trajectory_refactormd) | ❌ 过时 | 轨迹重构记录（已完成） | ❌ |

---

## 📖 详细说明

### ✅ 推荐阅读

#### IVAS 系统架构 (`../ivas/ARCHITECTURE.md`)
**状态**: ✅ 最新（2025-01-10）
**内容**:
- 完整的 IVAS 系统架构（含 PlantUML 图）
- Dashboard、IVAS Client、Mock Server 关系说明
- 开发测试环境 vs 生产环境对比
- 任务执行流程时序图
- 配置说明和最佳实践

**适用人群**: 所有开发者，必读文档
**相关文档**: [IVAS任务执行流程说明](../ivas/IVAS任务执行流程说明.md), [接口文档v4](../ivas/接口文档v4.md)

---

#### TRAJECTORY_GUIDE.md
**状态**: ✅ 有效
**内容**:
- 轨迹飞行任务系统说明
- 航点文件格式（JSON）
- fly_trajectory_sequence 使用方法
- 多无人机并行航点飞行

**适用人群**: 需要编写航点任务的开发者
**相关代码**: `djisdk/tasks/trajectory.py`

---

#### QUICK_REFERENCE.md
**状态**: ✅ 有效
**内容**:
- djisdk 快速参考手册
- 常用命令和API速查
- 代码示例

**适用人群**: djisdk 用户
**相关代码**: `djisdk/`

---

#### PYTHON_IMPORT_GUIDE.md
**状态**: ✅ 有效
**内容**:
- Python 导入系统完全指南
- 绝对导入 vs 相对导入
- sys.path 详解
- 常见导入问题解决方案

**适用人群**: Python 开发者（通用知识）
**推荐场景**: 遇到导入错误时查阅

---

### ⚠️ 参考文档（部分内容可能过时）

#### PID_TUNING_GUIDE.md
**状态**: ⚠️ 参考
**内容**:
- PID 控制器调参指南
- 针对 `control/` 模块

**注意**:
- 主要针对旧的 control 模块
- 当前项目重点是 IVAS 任务系统
- 如需 PID 控制，参考 `control/` 和 `control_mpc/` 目录下的 README

---

#### CONTROL_MODULE_GUIDE.md
**状态**: ⚠️ 参考
**内容**:
- 控制模块使用指南
- PID 位置控制和偏航控制

**注意**:
- 针对 `control/` 模块
- 当前主要使用场景是轨迹飞行（通过 IVAS）
- 如需深入控制算法，查阅此文档

---

#### JOYSTICK_UI_DESIGN.md
**状态**: ⚠️ 参考
**内容**:
- 虚拟摇杆 UI 设计说明
- Rich TUI 渲染技术

**注意**:
- 针对 `utils/keyboard.py` 工具
- 非核心功能，仅用于手动测试
- 如需修改摇杆UI，查阅此文档

---

#### MQTT_CLIENT_ID_FIX.md
**状态**: ⚠️ 历史记录
**内容**:
- MQTT 客户端 ID 冲突问题修复记录
- 已修复，保留作为历史参考

**注意**:
- 问题已解决
- 保留用于了解历史问题和解决思路
- 新开发者可跳过

---

#### DATA_LOGGING_README.md
**状态**: ⚠️ 历史记录
**内容**:
- control 模块的数据日志记录说明
- CSV 格式和可视化工具

**注意**:
- 针对 `control/` 模块
- 当前 IVAS 系统不使用此日志系统
- 如需研究控制算法，可参考

---

### ❌ 过时文档（建议删除）

#### MOCK_SIMULATOR_GUIDE.md
**状态**: ❌ 过时
**原因**:
- 内容已被 [IVAS 系统架构](../ivas/ARCHITECTURE.md) 取代
- Mock Server 相关内容已重新整理

**操作**: 建议删除

---

#### live_tool_guide.md
**状态**: ❌ 过时
**原因**:
- 针对旧的直播工具
- 当前系统不使用此功能
- 相关代码可能已移除

**操作**: 建议删除

---

#### TRAJECTORY_REFACTOR.md
**状态**: ❌ 过时
**原因**:
- 轨迹模块重构已完成
- 仅为历史记录
- 最新内容在 TRAJECTORY_GUIDE.md

**操作**: 建议删除

---

## 🗂️ 推荐阅读顺序

### 新用户入门
1. [IVAS 系统架构](../ivas/ARCHITECTURE.md) - 了解整体架构
2. [QUICK_REFERENCE.md](#quick_referencemd) - 快速上手
3. [TRAJECTORY_GUIDE.md](#trajectory_guidemd) - 轨迹飞行

### 问题排查
1. [PYTHON_IMPORT_GUIDE.md](#python_import_guidemd) - 导入错误
2. [IVAS 系统架构](../ivas/ARCHITECTURE.md) - 任务执行问题

### 深入开发
1. [CONTROL_MODULE_GUIDE.md](#control_module_guidemd) - 控制算法
2. [PID_TUNING_GUIDE.md](#pid_tuning_guidemd) - PID 调参

---

## 🧹 文档清理建议

### 立即删除
```bash
rm docs/MOCK_SIMULATOR_GUIDE.md
rm docs/live_tool_guide.md
rm docs/TRAJECTORY_REFACTOR.md
```

### 可选归档（移到 `docs/archive/`）
```bash
mkdir -p docs/archive
mv docs/MQTT_CLIENT_ID_FIX.md docs/archive/
mv docs/DATA_LOGGING_README.md docs/archive/
```

---

## 📝 文档维护规范

### 文档头部格式
每个文档应包含：
```markdown
# 文档标题

**状态**: ✅ 有效 / ⚠️ 参考 / ❌ 过时
**最后更新**: YYYY-MM-DD
**维护者**: 团队/个人名称

## 概述
文档简介...
```

### 更新频率
- **核心文档** (IVAS架构, QUICK_REFERENCE): 每次重大更新后立即更新
- **参考文档** (PID_TUNING, CONTROL_MODULE): 相关代码变更时更新
- **历史文档** (MQTT_CLIENT_ID_FIX): 无需更新

### 文档分类标签
- `✅ 有效`: 内容准确，经常使用
- `⚠️ 参考`: 部分内容可能过时，谨慎参考
- `❌ 过时`: 内容已失效，建议删除或归档

---

## 🔗 相关资源

- [djisdk README](../djisdk/README.md) - SDK 主文档
- [IVAS README](../ivas/README.md) - IVAS Client 文档
- [control_mpc README](../control_mpc/README.md) - MPC 控制器文档
- [项目根目录 README](../README.md) - 项目总览

---

**维护者**: System Architecture Team
**创建日期**: 2025-01-10
