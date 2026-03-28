#!/usr/bin/env python3
"""create_feature_list.py - Feature List管理工具

子命令: create, add, validate, show
无第三方依赖，纯标准库。
"""

import argparse
import json
import sys
import os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))

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

def next_feature_id(features):
    nums = []
    for f in features:
        fid = f.get("feature_id", "")
        if fid.startswith("F-"):
            try: nums.append(int(fid[2:]))
            except ValueError: pass
    return f"F-{max(nums, default=0) + 1:03d}"

def cmd_create(args):
    """创建新的Feature List"""
    features = []
    if args.from_markdown:
        # 简单从Markdown提取：每个##或###标题作为一个Feature候选
        if not os.path.exists(args.from_markdown):
            print(f"错误: 文件不存在: {args.from_markdown}", file=sys.stderr)
            sys.exit(1)
        with open(args.from_markdown, "r", encoding="utf-8") as f:
            lines = f.readlines()
        idx = 0
        for line in lines:
            line = line.strip()
            if line.startswith("##") and not line.startswith("###"):
                name = line.lstrip("#").strip()
                idx += 1
                features.append({
                    "feature_id": f"F-{idx:03d}",
                    "name": name,
                    "description": "",
                    "priority": "P1",
                    "phase": 1,
                    "status": "pending",
                    "sprint_contract_id": None,
                    "evaluator_score": None,
                    "iteration_count": 0,
                    "max_iterations": 3,
                    "acceptance_criteria": [],
                    "output_files": [],
                    "created_at": datetime.now(TZ).isoformat()
                })
        if not features:
            print("警告: 未从Markdown中提取到Feature (需要##标题)", file=sys.stderr)
    else:
        # 交互式输入
        print("交互式创建Feature (空行结束)")
        idx = 0
        while True:
            name = input(f"Feature #{idx+1} 名称 (留空结束): ").strip()
            if not name:
                break
            desc = input("  描述: ").strip()
            priority = input("  优先级 (P0/P1/P2) [P1]: ").strip() or "P1"
            phase = int(input("  Phase [1]: ").strip() or "1")
            idx += 1
            features.append({
                "feature_id": f"F-{idx:03d}",
                "name": name,
                "description": desc,
                "priority": priority,
                "phase": phase,
                "status": "pending",
                "sprint_contract_id": None,
                "evaluator_score": None,
                "iteration_count": 0,
                "max_iterations": 3,
                "acceptance_criteria": [],
                "output_files": [],
                "created_at": datetime.now(TZ).isoformat()
            })

    data = {"features": features}
    save_json(args.output, data)
    print(f"已创建Feature List: {args.output} ({len(features)} 个Feature)")

def cmd_add(args):
    """添加单个Feature"""
    data = load_json(args.output)
    if data is None:
        data = {"features": []}
    features = data.get("features", [])
    fid = next_feature_id(features)
    feature = {
        "feature_id": fid,
        "name": args.name,
        "description": args.description or "",
        "priority": args.priority or "P1",
        "phase": args.phase or 1,
        "status": "pending",
        "sprint_contract_id": None,
        "evaluator_score": None,
        "iteration_count": 0,
        "max_iterations": 3,
        "acceptance_criteria": [],
        "output_files": [],
        "created_at": datetime.now(TZ).isoformat()
    }
    features.append(feature)
    data["features"] = features
    save_json(args.output, data)
    print(f"已添加Feature: {fid} - {feature['name']}")

def cmd_validate(args):
    """验证Feature List"""
    data = load_json(args.output)
    if data is None:
        print(f"错误: 文件不存在: {args.output}", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []
    required_fields = ["feature_id", "name", "description", "priority", "phase", "status"]
    valid_priorities = {"P0", "P1", "P2"}
    valid_statuses = {"pending", "in_progress", "done", "blocked"}

    features = data.get("features", [])
    if not features:
        warnings.append("Feature List为空")

    for i, f in enumerate(features):
        prefix = f"Feature #{i+1}"
        for field in required_fields:
            if field not in f or not f[field]:
                errors.append(f"{prefix} ({f.get('feature_id','?')}): 缺少必填字段 '{field}'")
        if f.get("priority") not in valid_priorities:
            errors.append(f"{prefix}: 无效priority '{f.get('priority')}' (应为P0/P1/P2)")
        if f.get("status") not in valid_statuses:
            errors.append(f"{prefix}: 无效status '{f.get('status')}' (应为pending/in_progress/done/blocked)")
        if not f.get("acceptance_criteria"):
            warnings.append(f"{prefix} ({f.get('feature_id','?')}): 无acceptance_criteria")

    print(f"验证 {args.output}: {len(features)} 个Feature")
    if errors:
        print(f"\n❌ 错误 ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    if warnings:
        print(f"\n⚠️  警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    if not errors and not warnings:
        print("✅ 验证通过")
    sys.exit(1 if errors else 0)

def cmd_show(args):
    """展示Feature列表"""
    data = load_json(args.output)
    if data is None:
        print(f"错误: 文件不存在: {args.output}", file=sys.stderr)
        sys.exit(1)
    features = data.get("features", [])
    if not features:
        print("Feature List为空")
        return

    # 表头
    hdr = f"{'ID':<8} {'Name':<30} {'Pri':<4} {'Phase':<5} {'Status':<12} {'Score':<6}"
    print(hdr)
    print("-" * len(hdr))
    for f in features:
        score = f.get("evaluator_score")
        score_str = str(score) if score is not None else "-"
        name = f.get("name", "")[:28]
        print(f"{f.get('feature_id',''):<8} {name:<30} {f.get('priority',''):<4} {f.get('phase',''):<5} {f.get('status',''):<12} {score_str:<6}")
    print(f"\n共 {len(features)} 个Feature")

def main():
    parser = argparse.ArgumentParser(
        description="Feature List管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s create --from-markdown requirements.md
  %(prog)s add --name "用户登录" --description "实现OAuth登录" --priority P0 --phase 1
  %(prog)s validate
  %(prog)s show
        """
    )
    parser.add_argument("--output", default="feature_list.json", help="Feature List文件路径 (默认: feature_list.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="创建新Feature List")
    p_create.add_argument("--from-markdown", help="从Markdown文件导入Feature")

    # add
    p_add = sub.add_parser("add", help="添加单个Feature")
    p_add.add_argument("--name", required=True, help="Feature名称")
    p_add.add_argument("--description", default="", help="Feature描述")
    p_add.add_argument("--priority", default="P1", choices=["P0", "P1", "P2"], help="优先级")
    p_add.add_argument("--phase", type=int, default=1, help="Phase编号")

    # validate
    sub.add_parser("validate", help="验证Feature List格式")

    # show
    sub.add_parser("show", help="展示Feature列表")

    args = parser.parse_args()
    {"create": cmd_create, "add": cmd_add, "validate": cmd_validate, "show": cmd_show}[args.command](args)

if __name__ == "__main__":
    main()
