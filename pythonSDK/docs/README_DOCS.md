# 📚 文档目录说明

本文档说明 `docs/` 目录中各文档的用途、状态和推荐阅读顺序。

**最后更新**: 2024-11-19 (文档结构重组)

## 📁 目录结构

```
docs/
├── README_DOCS.md              # 本文档 - 总览和索引
├── architecture/               # 系统架构文档
│   ├── Arch.md                # 系统架构总览
│   ├── 接口设计.md            # 接口设计说明
│   ├── 通讯链路.md            # 通讯链路文档
│   ├── 视频推流方案.md        # 视频推流技术方案
│   └── 无人机后端服务器.md    # 后端服务器架构
├── control/                    # 控制系统相关文档
│   ├── CONTROL_MODULE_GUIDE.md # 控制模块指南
│   ├── PID_TUNING_GUIDE.md    # PID调参指南
│   └── TRAJECTORY_GUIDE.md     # 轨迹飞行指南
├── guides/                     # 使用指南和参考
│   ├── PYTHON_IMPORT_GUIDE.md # Python导入系统详解
│   ├── JOYSTICK_UI_DESIGN.md  # 虚拟摇杆UI设计
│   └── QUICK_REFERENCE.md      # 快速参考手册
├── diagrams/                   # 架构图表和流程图
│   ├── IVAS多无人机通信架构.svg
│   ├── IVAS接口组件关系概览.svg
│   ├── 地面站与IVAS典型调用时序.svg
│   ├── 无人机后端服务器核心模块关系.svg
│   └── 无人机与地面站通讯链路拓扑.svg
├── troubleshooting/            # 问题排查和调试
│   ├── waypoint_fast_arrival_bug.md  # 航点快速到达问题
│   ├── pure_fake_target_logic.md     # 纯虚假目标逻辑
│   └── GPS_PRECISION_AUDIT.md        # GPS精度审计
├── api/                        # API文档 (预留)
└── archive/                    # 历史文档归档
    ├── DATA_LOGGING_README.md
    ├── live_tool_guide.md
    ├── MOCK_SIMULATOR_GUIDE.md
    ├── MQTT_CLIENT_ID_FIX.md
    └── TRAJECTORY_REFACTOR.md
```

---

## 📊 文档概览

### 🏗️ 架构文档 (`architecture/`)
| 文档名称 | 状态 | 用途 | 推荐度 |
|---------|------|------|--------|
| [Arch.md](architecture/Arch.md) | ✅ 最新 | 系统架构总览 | ⭐⭐⭐⭐⭐ |
| [接口设计.md](architecture/接口设计.md) | ✅ 有效 | 接口设计说明 | ⭐⭐⭐⭐ |
| [通讯链路.md](architecture/通讯链路.md) | ✅ 有效 | 通讯链路文档 | ⭐⭐⭐⭐ |
| [视频推流方案.md](architecture/视频推流方案.md) | ✅ 有效 | 视频推流技术方案 | ⭐⭐⭐ |
| [无人机后端服务器.md](architecture/无人机后端服务器.md) | ✅ 有效 | 后端服务器架构 | ⭐⭐⭐⭐ |

### 🎮 控制系统文档 (`control/`)
| 文档名称 | 状态 | 用途 | 推荐度 |
|---------|------|------|--------|
| [TRAJECTORY_GUIDE.md](control/TRAJECTORY_GUIDE.md) | ✅ 有效 | 轨迹飞行指南 | ⭐⭐⭐⭐⭐ |
| [CONTROL_MODULE_GUIDE.md](control/CONTROL_MODULE_GUIDE.md) | ⚠️ 参考 | 控制模块指南 | ⭐⭐⭐ |
| [PID_TUNING_GUIDE.md](control/PID_TUNING_GUIDE.md) | ⚠️ 参考 | PID 调参指南 | ⭐⭐⭐ |

### 📖 使用指南 (`guides/`)
| 文档名称 | 状态 | 用途 | 推荐度 |
|---------|------|------|--------|
| [QUICK_REFERENCE.md](guides/QUICK_REFERENCE.md) | ✅ 有效 | 快速参考手册 | ⭐⭐⭐⭐ |
| [PYTHON_IMPORT_GUIDE.md](guides/PYTHON_IMPORT_GUIDE.md) | ✅ 有效 | Python 导入系统详解 | ⭐⭐⭐⭐ |
| [JOYSTICK_UI_DESIGN.md](guides/JOYSTICK_UI_DESIGN.md) | ⚠️ 参考 | 虚拟摇杆 UI 设计 | ⭐⭐ |

### 🔧 问题排查 (`troubleshooting/`)
| 文档名称 | 状态 | 用途 | 推荐度 |
|---------|------|------|--------|
| [waypoint_fast_arrival_bug.md](troubleshooting/waypoint_fast_arrival_bug.md) | ✅ 有效 | 航点快速到达问题分析 | ⭐⭐⭐ |
| [pure_fake_target_logic.md](troubleshooting/pure_fake_target_logic.md) | ✅ 有效 | 纯虚假目标逻辑分析 | ⭐⭐⭐ |
| [GPS_PRECISION_AUDIT.md](troubleshooting/GPS_PRECISION_AUDIT.md) | ✅ 有效 | GPS精度审计报告 | ⭐⭐⭐ |

### 📊 架构图表 (`diagrams/`)
| 文件名称 | 用途 |
|---------|------|
| IVAS多无人机通信架构.svg | IVAS多无人机通信完整架构图 |
| IVAS接口组件关系概览.svg | 接口组件关系总览 |
| 地面站与IVAS典型调用时序.svg | 调用时序图 |
| 无人机后端服务器核心模块关系.svg | 后端服务器模块关系 |
| 无人机与地面站通讯链路拓扑.svg | 通讯链路拓扑图 |

### 📁 历史归档 (`archive/`)
| 文档名称 | 状态 | 备注 |
|---------|------|------|
| MQTT_CLIENT_ID_FIX.md | ⚠️ 历史 | MQTT 客户端ID修复记录 |
| DATA_LOGGING_README.md | ⚠️ 历史 | 数据日志记录说明（control 模块） |
| MOCK_SIMULATOR_GUIDE.md | ❌ 过时 | 模拟器指南（已废弃） |
| live_tool_guide.md | ❌ 过时 | 直播工具指南（已废弃） |
| TRAJECTORY_REFACTOR.md | ❌ 过时 | 轨迹重构记录（已完成） |

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
1. [系统架构总览](architecture/Arch.md) - 了解整体架构
2. [快速参考手册](guides/QUICK_REFERENCE.md) - 快速上手
3. [轨迹飞行指南](control/TRAJECTORY_GUIDE.md) - 轨迹飞行

### 架构理解
1. [系统架构总览](architecture/Arch.md) - 系统整体设计
2. [接口设计](architecture/接口设计.md) - 接口规范
3. [通讯链路](architecture/通讯链路.md) - 通信协议
4. [后端服务器](architecture/无人机后端服务器.md) - 服务端架构

### 开发指南
1. [快速参考手册](guides/QUICK_REFERENCE.md) - djisdk API速查
2. [Python导入指南](guides/PYTHON_IMPORT_GUIDE.md) - 导入系统详解
3. [控制模块指南](control/CONTROL_MODULE_GUIDE.md) - 控制系统开发

### 问题排查
1. [Python导入指南](guides/PYTHON_IMPORT_GUIDE.md) - 解决导入错误
2. [航点快速到达问题](troubleshooting/waypoint_fast_arrival_bug.md) - 航点问题排查
3. [GPS精度审计](troubleshooting/GPS_PRECISION_AUDIT.md) - GPS相关问题

### 深入开发
1. [控制模块指南](control/CONTROL_MODULE_GUIDE.md) - 控制算法
2. [PID调参指南](control/PID_TUNING_GUIDE.md) - PID调参
3. [虚拟摇杆UI设计](guides/JOYSTICK_UI_DESIGN.md) - UI开发

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
