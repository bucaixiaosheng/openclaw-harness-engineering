# OpenClaw Harness Engineering

> 基于 Claude Harness Engineering 方法论，适配 OpenClaw 多 Agent 协作框架的实战工程系统

## 项目概述

本项目将 Harness Engineering 方法论落地到 OpenClaw 平台，通过 **Planner → Generator → Evaluator** 三角色协作，以 **Sprint Cycle** 驱动的方式高质量交付软件功能。

核心思想：
- **Contract-Driven**：每个 Feature 通过 Sprint Contract 明确预期产出和验收标准
- **Iterative Refinement**：生成 → 评估 → 反馈 → 迭代，最多 3 轮
- **Quality Gate**：评分低于 60 分直接失败，80 分以上通过

## 架构图

```
┌──────────────────────────────────────────────────────────┐
│                        用 户 (User)                       │
│                   提出需求 / 查看进度                      │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                   main (Orchestrator)                     │
│              任务分发、进度跟踪、结果汇报                    │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│              control (Planner)                            │
│     需求分析 → Feature 拆分 → Sprint Contract 发起        │
│     Contract 协商 → 任务分配 → 迭代决策                    │
└──────┬───────────────────────────────────┬───────────────┘
       │                                   │
       ▼                                   ▼
┌──────────────────┐            ┌──────────────────────────┐
│  coding          │            │  evaluator               │
│  (Generator)     │            │  (Evaluator)             │
│                  │            │                          │
│ 按 Contract      │──────────▶│ 独立评估产出物            │
│ 实现 Feature     │  产出物    │ 评分 + 改进建议           │
│ 提交代码+文档    │            │ 维度：功能/质量/文档/     │
│                  │            │       测试/架构           │
└──────────────────┘            └──────────────────────────┘
       ▲                                   │
       │          评估报告 + 反馈           │
       └───────────────────────────────────┘
                    迭代循环 (max 3轮)
```

## 安装说明

### 前置要求

- **Python 3.8+**（系统自带，无需额外安装）
- **OpenClaw** 平台已部署并运行
- **Git**（用于版本控制和产出物管理）

### 无额外依赖

本项目为纯 Python 实现，不依赖任何第三方库。所有配置使用 JSON 格式，所有脚本兼容 Python 3.8+。

## 快速开始

### 第 1 步：准备项目目录

```bash
cd /path/to/openclaw/shared-projects/
git clone <repo-url> openclaw-harness-engineering
cd openclaw-harness-engineering
```

### 第 2 步：编辑 Feature List

```bash
cp feature_list_template.json feature_list.json
# 编辑 feature_list.json，填入你的 Feature 定义
```

### 第 3 步：启动 Sprint

通过 OpenClaw 向 control agent 发送指令：

```
请开始 Sprint Cycle，使用 feature_list.json 中的第一个 P0 Feature
```

control 将自动发起 Sprint Contract，分配给 coding agent 实现，由 evaluator 评估。

## 文件结构树

```
openclaw-harness-engineering/
├── README.md                          # 项目说明文档（本文件）
├── HARNESS_CONFIG.json                # 核心配置：角色定义、Sprint参数、路径配置
├── phase-plan.json                    # Phase 执行计划
├── feature_list_template.json         # Feature List 模板（含示例数据）
├── feature_list.json                  # 实际 Feature List（从模板复制后编辑）
├── sprint_contract_template.json      # Sprint Contract 模板
├── evaluator_rubric.json              # 评估评分标准
├── sprint_contracts/                  # Sprint Contract 存放目录
│   ├── SC-001-xxx.json
│   ├── SC-002-xxx.json
│   └── ...
├── evaluation_reports/                # 评估报告存放目录
│   ├── ER-001-xxx.json
│   ├── ER-002-xxx.json
│   └── ...
└── src/                               # 源代码（按需创建）
    ├── __init__.py
    ├── harness_runner.py              # Harness 主流程运行器
    ├── contract_manager.py            # Contract 管理器
    └── evaluation_engine.py           # 评估引擎
```

## Sprint Cycle 流程

```
1. Contract 协商
   control (Planner) 发起 Sprint Contract → coding (Generator) 确认/协商
   最多 negotiation_rounds (3) 轮协商达成一致
   状态: draft → agreed

2. 实现
   coding (Generator) 按 Contract 实现 Feature
   产出: 代码文件 + 文档 + 测试
   状态: agreed → implementing

3. 评估
   evaluator (Evaluator) 独立评估产出物
   按5个维度打分，生成评估报告
   状态: implementing → evaluating

4. 迭代决策
   - 总分 ≥ 80: ✅ 通过 → completed
   - 总分 60~79: 🔄 迭代 → 回到步骤2（带改进建议）
   - 总分 < 60: ❌ 失败 → failed
   - 迭代次数 ≥ max_iterations(3): ⚠️ 强制结束

           ┌──────────┐
           │  发 起    │
           │ Contract │
           └────┬─────┘
                │
                ▼
           ┌──────────┐     协商失败
           │  协 商    │──────────────▶ 重新发起或放弃
           └────┬─────┘
                │ 达成一致
                ▼
           ┌──────────┐
           │  实 现    │◀─────────────┐
           └────┬─────┘              │
                │                     │
                ▼                     │
           ┌──────────┐              │
           │  评 估    │              │
           └────┬─────┘              │
                │                     │
          ┌─────┴──────┐             │
          │            │              │
      score ≥ 80   60 ≤ score < 80  │
          │            │              │
          ▼            ▼              │
       ✅ 通过    🔄 迭代 ────────────┘
                      (带改进建议)
```

## 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| **功能完整性** | 30% | 是否实现了 Contract 中定义的所有功能点 |
| **代码质量** | 25% | 代码风格、可读性、错误处理、最佳实践 |
| **文档完整性** | 20% | API文档、使用说明、代码注释 |
| **测试覆盖** | 15% | 单元测试、边界测试、集成测试的覆盖度 |
| **架构合规** | 10% | 是否符合项目架构规范和设计模式 |

### 评分等级

- **80~100 分**：✅ 通过 (Pass) — 产出物质量达标
- **60~79 分**：🔄 迭代 (Iterate) — 需要改进后重新评估
- **0~59 分**：❌ 失败 (Fail) — 产出物质量不达标

## 配置说明

主要配置文件为 `HARNESS_CONFIG.json`，包含：

- **agent_roles**: 三角色定义（planner, generator, evaluator）
- **sprint_defaults**: Sprint 默认参数（迭代次数、通过/失败阈值、协商轮数）
- **file_paths**: 各类文件路径配置
- **spawn_config**: Agent 子进程启动参数

详细配置说明请参考 `HARNESS_CONFIG.json` 文件内注释。

## 贡献指南

1. 通过 OpenClaw 向 control agent 提交 Feature Request
2. control 将分析需求并创建 Feature 条目
3. 按 Sprint Cycle 流程执行开发
4. 所有产出物经过 Evaluator 评估达标后方可合并

## License

MIT
