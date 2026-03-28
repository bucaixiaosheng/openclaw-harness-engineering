# 示例项目：Todo CLI应用

## 概述

本示例展示如何使用Harness Engineering系统开发一个简单的Todo CLI应用。通过一个完整的开发周期，演示从Feature List创建到最终评估的全流程。

## 使用Harness Engineering的完整流程

### Step 1: 创建Feature List

```bash
# 使用create_feature_list.py添加Feature
python3 scripts/create_feature_list.py add \
  --name "Todo数据模型" \
  --description "实现Todo的CRUD数据存储，使用JSON文件持久化" \
  --priority P0 --phase 1

python3 scripts/create_feature_list.py add \
  --name "CLI命令行接口" \
  --description "实现add/list/done/delete四个子命令" \
  --priority P0 --phase 2

python3 scripts/create_feature_list.py add \
  --name "用户帮助信息" \
  --description "实现--help和各子命令的帮助提示" \
  --priority P1 --phase 3
```

### Step 2: 创建Sprint Contract

```bash
# 为FEAT-001创建Sprint Contract（自动同意模式）
python3 scripts/negotiate_sprint_contract.py create FEAT-001 --auto-agree
```

### Step 3: Generator实现

```bash
# 由control agent spawn coding agent，按Sprint Contract实现
# coding agent读取sprint_contracts/FEAT-001_contract.json，实现代码
# 实现Todo数据模型：JSON文件持久化、CRUD操作
```

### Step 4: Evaluator评估

```bash
# 对FEAT-001的产出进行自动评估
python3 scripts/evaluate_sprint.py evaluate FEAT-001 --auto-score
```

### Step 5: 查看结果

```bash
# 查看Feature进度
python3 scripts/check_feature_progress.py

# 生成Harness报告
python3 scripts/harness_report.py
```

### Step 6: 主控脚本一键执行

```bash
# Dry-run模式预览完整流程
./scripts/run_harness.sh --dry-run
```

## 示例文件说明

| 文件 | 说明 |
|------|------|
| `feature_list.json` | Todo应用的3个Feature定义 |
| `sprint_contract.json` | FEAT-001的完整Sprint Contract（含评估结果） |
| `evaluation_report.json` | FEAT-001的评估报告 |

## 关键概念

- **Feature List**: 项目所有功能需求的列表，按优先级和Phase组织
- **Sprint Contract**: Generator与Evaluator之间的"合同"，定义构建内容和验收标准
- **Evaluation Report**: 基于rubric的5维度评估结果（功能、代码、文档、测试、架构）
- **Iteration**: 当评估未通过时，可重新协商Contract并再次实现（最多3次）
