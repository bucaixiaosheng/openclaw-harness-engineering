#!/usr/bin/env python3
"""negotiate_sprint_contract.py - Sprint Contract管理工具

子命令: create, update, show, agree, complete, fail
无第三方依赖，纯标准库。
"""

import argparse
import json
import sys
import os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
VALID_STATUSES = {"draft", "agreed", "implementing", "evaluating", "completed", "failed"}
CONTRACT_TEMPLATE = {
    "contract_id": "",
    "feature_id": "",
    "status": "draft",
    "created_at": "",
    "updated_at": "",
    "generator_commitment": {
        "planned_build": "",
        "verification_criteria": [],
        "output_files": []
    },
    "evaluator_criteria": {
        "dimensions": {
            "functional_completeness": {"weight": 0.30, "description": "功能完整性"},
            "code_quality": {"weight": 0.25, "description": "代码质量"},
            "documentation_completeness": {"weight": 0.20, "description": "文档完整性"},
            "test_coverage": {"weight": 0.15, "description": "测试覆盖"},
            "architecture_compliance": {"weight": 0.10, "description": "架构合规"}
        },
        "score_thresholds": {"pass": 80, "fail": 60}
    },
    "negotiation_history": [],
    "evaluation_result": {
        "scores": {k: None for k in ["functional_completeness", "code_quality",
                                      "documentation_completeness", "test_coverage",
                                      "architecture_compliance"]},
        "weighted_total": None,
        "verdict": "pending",
        "improvement_suggestions": []
    },
    "iteration": 0,
    "max_iterations": 3
}

def now_iso():
    return datetime.now(TZ).isoformat()

def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"错误: 读取 {path} 失败: {e}", file=sys.stderr)
        sys.exit(1)

def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def find_feature(feature_list_path, feature_id):
    data = load_json(feature_list_path)
    if data is None:
        print(f"错误: Feature List不存在: {feature_list_path}", file=sys.stderr)
        sys.exit(1)
    for f in data.get("features", []):
        if f["feature_id"] == feature_id:
            return f, data
    print(f"错误: 未找到Feature: {feature_id}", file=sys.stderr)
    sys.exit(1)

def contract_path(contracts_dir, feature_id):
    return os.path.join(contracts_dir, f"{feature_id}_contract.json")

def load_config(config_path):
    return load_json(config_path) or {}

def cmd_create(args):
    """创建Sprint Contract"""
    config = load_config(args.config)
    contracts_dir = config.get("file_paths", {}).get("sprint_contracts_dir", "sprint_contracts/")
    feature_list_path = config.get("file_paths", {}).get("feature_list", "feature_list.json")
    max_iter = config.get("sprint_defaults", {}).get("max_iterations", 3)

    feature, fl_data = find_feature(feature_list_path, args.feature_id)
    cpath = contract_path(contracts_dir, args.feature_id)

    if os.path.exists(cpath):
        print(f"Contract已存在: {cpath}")
        return

    import copy
    contract = copy.deepcopy(CONTRACT_TEMPLATE)
    # Auto-increment contract_id
    existing = [f for f in os.listdir(contracts_dir) if f.endswith("_contract.json")] if os.path.isdir(contracts_dir) else []
    cnum = len(existing) + 1
    contract["contract_id"] = f"SC-{cnum:03d}"
    contract["feature_id"] = args.feature_id
    contract["created_at"] = now_iso()
    contract["updated_at"] = now_iso()
    contract["max_iterations"] = max_iter
    contract["generator_commitment"]["planned_build"] = feature.get("description", "")
    contract["generator_commitment"]["verification_criteria"] = feature.get("acceptance_criteria", [])
    contract["generator_commitment"]["output_files"] = feature.get("output_files", [])
    contract["negotiation_history"].append({
        "round": 1,
        "role": "planner",
        "message": f"为 {args.feature_id} 创建Sprint Contract",
        "timestamp": now_iso()
    })

    if args.auto_agree:
        contract["status"] = "agreed"
        contract["negotiation_history"].append({
            "round": 1,
            "role": "generator",
            "message": "自动确认Contract (auto-agree模式)",
            "timestamp": now_iso()
        })

    save_json(cpath, contract)
    print(f"已创建Contract: {cpath} (status: {contract['status']})")

def cmd_update(args):
    """更新Contract状态"""
    config = load_config(args.config)
    contracts_dir = config.get("file_paths", {}).get("sprint_contracts_dir", "sprint_contracts/")
    cpath = contract_path(contracts_dir, args.feature_id)

    if not os.path.exists(cpath):
        print(f"错误: Contract不存在: {cpath}", file=sys.stderr)
        sys.exit(1)

    if args.status not in VALID_STATUSES:
        print(f"错误: 无效状态 '{args.status}' (应为: {', '.join(sorted(VALID_STATUSES))})", file=sys.stderr)
        sys.exit(1)

    contract = load_json(cpath)
    old_status = contract["status"]
    contract["status"] = args.status
    contract["updated_at"] = now_iso()

    if args.message:
        contract["negotiation_history"].append({
            "round": len(contract["negotiation_history"]) + 1,
            "role": "system",
            "message": args.message,
            "timestamp": now_iso()
        })

    save_json(cpath, contract)
    print(f"Contract {args.feature_id}: {old_status} → {args.status}")

def cmd_show(args):
    """展示Contract详情"""
    config = load_config(args.config)
    contracts_dir = config.get("file_paths", {}).get("sprint_contracts_dir", "sprint_contracts/")
    cpath = contract_path(contracts_dir, args.feature_id)

    if not os.path.exists(cpath):
        print(f"错误: Contract不存在: {cpath}", file=sys.stderr)
        sys.exit(1)

    contract = load_json(cpath)
    print(f"Contract ID: {contract.get('contract_id')}")
    print(f"Feature ID:  {contract.get('feature_id')}")
    print(f"Status:      {contract.get('status')}")
    print(f"Iteration:   {contract.get('iteration', 0)}/{contract.get('max_iterations', 3)}")
    print(f"Created:     {contract.get('created_at')}")
    print(f"Updated:     {contract.get('updated_at')}")
    print(f"\nGenerator Commitment:")
    gc = contract.get("generator_commitment", {})
    print(f"  计划构建: {gc.get('planned_build', '')}")
    print(f"  验证标准:")
    for vc in gc.get("verification_criteria", []):
        print(f"    - {vc}")
    print(f"  输出文件:")
    for of in gc.get("output_files", []):
        print(f"    - {of}")

    er = contract.get("evaluation_result", {})
    wt = er.get("weighted_total")
    print(f"\n评估结果: {er.get('verdict', 'pending')} (score: {wt if wt is not None else 'N/A'})")

    nh = contract.get("negotiation_history", [])
    if nh:
        print(f"\nNegotiation History ({len(nh)} 条):")
        for entry in nh:
            print(f"  [R{entry.get('round','?')}] {entry.get('role','?')}: {entry.get('message','')}")

def cmd_agree(args):
    """标记Contract为agreed"""
    args.status = "agreed"
    args.message = args.message or "Generator确认Contract，同意开始实现"
    cmd_update(args)

def cmd_complete(args):
    """标记Contract为completed"""
    args.status = "completed"
    args.message = args.message or "Sprint已完成"
    cmd_update(args)

def cmd_fail(args):
    """标记Contract为failed"""
    args.status = "failed"
    args.message = args.message or "Sprint失败"
    cmd_update(args)

def main():
    parser = argparse.ArgumentParser(
        description="Sprint Contract管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s create --feature-id F-001 --auto-agree
  %(prog)s update --feature-id F-001 --status implementing --message "开始实现"
  %(prog)s show --feature-id F-001
  %(prog)s agree --feature-id F-001
  %(prog)s complete --feature-id F-001
  %(prog)s fail --feature-id F-001 --message "超出最大迭代次数"
        """
    )
    parser.add_argument("--config", default="HARNESS_CONFIG.json", help="配置文件路径")
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="创建Sprint Contract")
    p_create.add_argument("--feature-id", required=True, help="Feature ID (如 F-001)")
    p_create.add_argument("--auto-agree", action="store_true", help="自动标记为agreed")

    # update
    p_update = sub.add_parser("update", help="更新Contract状态")
    p_update.add_argument("--feature-id", required=True, help="Feature ID")
    p_update.add_argument("--status", required=True, help=f"新状态 ({', '.join(sorted(VALID_STATUSES))})")
    p_update.add_argument("--message", help="添加negotiation记录")

    # show
    p_show = sub.add_parser("show", help="展示Contract详情")
    p_show.add_argument("--feature-id", required=True, help="Feature ID")

    # agree
    p_agree = sub.add_parser("agree", help="标记为agreed")
    p_agree.add_argument("--feature-id", required=True, help="Feature ID")
    p_agree.add_argument("--message", help="确认消息")

    # complete
    p_complete = sub.add_parser("complete", help="标记为completed")
    p_complete.add_argument("--feature-id", required=True, help="Feature ID")
    p_complete.add_argument("--message", help="完成消息")

    # fail
    p_fail = sub.add_parser("fail", help="标记为failed")
    p_fail.add_argument("--feature-id", required=True, help="Feature ID")
    p_fail.add_argument("--message", help="失败原因")

    args = parser.parse_args()
    {"create": cmd_create, "update": cmd_update, "show": cmd_show,
     "agree": cmd_agree, "complete": cmd_complete, "fail": cmd_fail}[args.command](args)

if __name__ == "__main__":
    main()
