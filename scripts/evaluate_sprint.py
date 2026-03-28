#!/usr/bin/env python3
"""
evaluate_sprint.py - Sprint评估脚本

评估Sprint产出物质量，按5个维度评分并生成评估报告。

用法:
    python3 scripts/evaluate_sprint.py evaluate <feature_id> [options]
    python3 scripts/evaluate_sprint.py show <feature_id>
    python3 scripts/evaluate_sprint.py history <feature_id>

子命令:
    evaluate   执行评估
    show       展示评估结果
    history    查看历史评估

选项:
    --rubric PATH        评分标准文件 (默认: evaluator_rubric.json)
    --verbose            输出详细评分过程
    --auto-score         对无法自动验证的维度使用默认分3
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# 项目根目录（脚本在 scripts/ 下）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CST = timezone(timedelta(hours=8))


def load_json(path):
    """加载JSON文件，失败则退出。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析失败: {path} - {e}", file=sys.stderr)
        sys.exit(1)


def save_json(path, data):
    """保存JSON文件。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def iso_now():
    """返回当前CST时间的ISO格式字符串。"""
    return datetime.now(CST).isoformat()


# ── 自动评分逻辑 ──────────────────────────────────────────────

def score_functionality(contract, verbose):
    """功能完整性：检查output_files存在 + acceptance_criteria可验证项。"""
    reasons = []
    output_files = contract.get("generator_commitment", {}).get("output_files", [])
    criteria = contract.get("generator_commitment", {}).get("verification_criteria", [])

    # 检查output_files
    missing_files = []
    found_files = []
    for fp in output_files:
        full = os.path.join(PROJECT_ROOT, fp)
        if os.path.exists(full):
            found_files.append(fp)
        else:
            missing_files.append(fp)

    if missing_files:
        reasons.append(f"缺失文件: {', '.join(missing_files)}")
    else:
        reasons.append(f"所有输出文件存在 ({len(found_files)}个)")

    # 基于文件存在率评分
    if not output_files:
        file_score = 3
    else:
        ratio = len(found_files) / len(output_files)
        if ratio >= 1.0:
            file_score = 4
        elif ratio >= 0.8:
            file_score = 3
        elif ratio >= 0.5:
            file_score = 2
        else:
            file_score = 1

    if verbose:
        print(f"  [功能完整性] 文件检查: {len(found_files)}/{len(output_files)} 存在")

    return file_score, "; ".join(reasons)


def score_code_quality(contract, verbose):
    """代码质量：检查输出文件是否为有效Python/JSON。"""
    output_files = contract.get("generator_commitment", {}).get("output_files", [])
    reasons = []
    valid = 0
    total = 0

    for fp in output_files:
        full = os.path.join(PROJECT_ROOT, fp)
        if not os.path.exists(full):
            continue
        total += 1
        try:
            if fp.endswith(".json"):
                with open(full, "r", encoding="utf-8") as f:
                    json.load(f)
                valid += 1
            elif fp.endswith(".py"):
                with open(full, "r", encoding="utf-8") as f:
                    compile(f.read(), fp, "exec")
                valid += 1
            else:
                valid += 1  # 非代码文件默认有效
        except Exception as e:
            reasons.append(f"{fp}: {e}")

    if not total:
        score = 3
        reasons.append("无可检查的代码文件")
    else:
        ratio = valid / total
        if ratio >= 1.0:
            score = 4
        elif ratio >= 0.7:
            score = 3
        else:
            score = 2
        reasons.append(f"{valid}/{total} 文件语法有效")

    if verbose:
        print(f"  [代码质量] 有效文件: {valid}/{total}")

    return score, "; ".join(reasons)


def score_documentation(contract, verbose):
    """文档完整性：检查README等文档文件。"""
    output_files = contract.get("generator_commitment", {}).get("output_files", [])
    reasons = []

    doc_files = [f for f in output_files if any(f.endswith(ext) for ext in (".md", ".rst", ".txt"))]
    readme_exists = os.path.exists(os.path.join(PROJECT_ROOT, "README.md"))

    if doc_files and readme_exists:
        score = 4
        reasons.append(f"文档文件存在: {', '.join(doc_files)}; README.md存在")
    elif readme_exists:
        score = 3
        reasons.append("README.md存在，但Contract中未列出文档文件")
    else:
        score = 2
        reasons.append("缺少README.md等文档")

    if verbose:
        print(f"  [文档完整性] 文档文件: {doc_files}, README: {readme_exists}")

    return score, "; ".join(reasons)


def score_test_coverage(contract, verbose):
    """测试覆盖：检查test文件是否存在且可解析。"""
    output_files = contract.get("generator_commitment", {}).get("output_files", [])
    reasons = []

    test_files = [f for f in output_files if "test" in f.lower()]
    if not test_files:
        score = 2
        reasons.append("未发现测试文件")
    else:
        existing = [f for f in test_files if os.path.exists(os.path.join(PROJECT_ROOT, f))]
        if len(existing) == len(test_files):
            score = 4
            reasons.append(f"测试文件完整 ({len(existing)}个)")
        else:
            score = 3
            reasons.append(f"部分测试文件存在 ({len(existing)}/{len(test_files)})")

    if verbose:
        print(f"  [测试覆盖] 测试文件: {test_files}")

    return score, "; ".join(reasons)


def score_architecture_compliance(contract, verbose):
    """架构合规：检查Sprint Contract结构是否符合规范。"""
    reasons = []
    score = 3  # 默认

    # 检查必要字段
    required_fields = ["contract_id", "feature_id", "status", "generator_commitment", "evaluator_criteria"]
    present = [f for f in required_fields if f in contract]
    missing = [f for f in required_fields if f not in contract]

    if not missing:
        score = 4
        reasons.append("Sprint Contract结构完整")
    else:
        score = 2
        reasons.append(f"缺失字段: {', '.join(missing)}")

    # 检查generator_commitment子字段
    gc = contract.get("generator_commitment", {})
    if all(k in gc for k in ("planned_build", "verification_criteria", "output_files")):
        reasons.append("generator_commitment结构规范")
    else:
        score = min(score, 3)

    if verbose:
        print(f"  [架构合规] 必要字段: {len(present)}/{len(required_fields)}, 缺失: {missing}")

    return score, "; ".join(reasons)


SCORERS = {
    "functionality": score_functionality,
    "code_quality": score_code_quality,
    "documentation": score_documentation,
    "test_coverage": score_test_coverage,
    "architecture_compliance": score_architecture_compliance,
}


def compute_verdict(total_score, scores, thresholds):
    """根据总分和各维度分数判定结果。"""
    auto_fail = thresholds.get("auto_fail_if_any_dimension_is", 1)
    if any(s <= auto_fail for s in scores.values()):
        return "FAIL"
    if total_score >= thresholds["pass"]:
        return "PASS"
    if total_score >= thresholds.get("conditional_pass", thresholds["fail"]):
        return "CONDITIONAL_PASS"
    return "FAIL"


def generate_suggestions(scores):
    """根据低分维度生成改进建议。"""
    suggestions = []
    guides = {
        "functionality": "确保所有output_files都已生成，验收标准全部通过",
        "code_quality": "改善代码结构，增加注释，确保语法正确",
        "documentation": "补充README和使用文档",
        "test_coverage": "增加单元测试和集成测试",
        "architecture_compliance": "确保Sprint Contract结构符合规范",
    }
    for dim_id, score in scores.items():
        if score <= 3:
            suggestions.append(guides.get(dim_id, f"改进 {dim_id}"))
    return suggestions


# ── 子命令 ────────────────────────────────────────────────────

def cmd_evaluate(args):
    """执行评估。"""
    feature_id = args.feature_id
    rubric_path = os.path.join(PROJECT_ROOT, args.rubric)

    rubric = load_json(rubric_path)

    # 加载Sprint Contract
    contract_paths = [
        os.path.join(PROJECT_ROOT, "sprint_contracts", f"{feature_id}_contract.json"),
        os.path.join(PROJECT_ROOT, "sprint_contracts", f"{feature_id.lower()}_contract.json"),
    ]
    contract = None
    contract_path = None
    for cp in contract_paths:
        if os.path.exists(cp):
            contract = load_json(cp)
            contract_path = cp
            break

    if contract is None:
        print(f"[ERROR] 找不到Sprint Contract: {feature_id}", file=sys.stderr)
        print(f"  尝试路径: {contract_paths}", file=sys.stderr)
        sys.exit(1)

    verbose = args.verbose
    auto_score = args.auto_score

    if verbose:
        print(f"评估 Feature: {feature_id}")
        print(f"Contract: {contract_path}")
        print(f"Rubric: {rubric_path}")
        print()

    # 评分
    scores = {}
    thresholds = rubric.get("thresholds", {"pass": 80, "conditional_pass": 60, "fail": 60})

    for dim in rubric["dimensions"]:
        dim_id = dim["id"]
        weight = dim["weight"]

        if dim_id in SCORERS:
            raw_score, reason = SCORERS[dim_id](contract, verbose)
        elif auto_score:
            raw_score = 3
            reason = "自动评分（默认3分）"
        else:
            raw_score = 3
            reason = "无法自动验证，使用默认分3"

        scores[dim_id] = {
            "score": raw_score,
            "weight": weight,
            "reason": reason,
        }

    # 计算加权总分（百分制）
    total_score = sum(s["score"] * s["weight"] * 20 for s in scores.values())
    total_score = round(total_score, 1)

    # 判定
    raw_scores = {k: v["score"] for k, v in scores.items()}
    verdict = compute_verdict(total_score, raw_scores, thresholds)

    # 改进建议
    suggestions = generate_suggestions(raw_scores)

    # 构建评估报告
    report = {
        "contract_id": contract.get("contract_id", "UNKNOWN"),
        "feature_id": feature_id,
        "evaluated_at": iso_now(),
        "scores": scores,
        "total_score": total_score,
        "verdict": verdict,
        "improvement_suggestions": suggestions,
    }

    # 输出报告
    report_dir = os.path.join(PROJECT_ROOT, "evaluation_reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{feature_id}_evaluation.json")
    save_json(report_path, report)

    if verbose:
        print()
        print("=" * 50)
        for dim_id, info in scores.items():
            print(f"  {dim_id}: {info['score']}/5 (权重 {info['weight']:.0%}) - {info['reason']}")
        print(f"  总分: {total_score}/100")
        print(f"  判定: {verdict}")
        if suggestions:
            print(f"  改进建议:")
            for s in suggestions:
                print(f"    - {s}")
        print("=" * 50)

    print(f"[OK] 评估完成: {feature_id} → {verdict} ({total_score}/100)")
    print(f"  报告: {report_path}")

    # 更新Sprint Contract的evaluation_result
    contract.setdefault("evaluation_result", {})
    contract["evaluation_result"]["scores"] = raw_scores
    contract["evaluation_result"]["weighted_total"] = total_score
    contract["evaluation_result"]["verdict"] = verdict
    contract["evaluation_result"]["improvement_suggestions"] = suggestions
    contract["evaluation_result"]["evaluated_at"] = report["evaluated_at"]
    contract["updated_at"] = iso_now()
    save_json(contract_path, contract)

    # 更新feature_list
    fl_path = os.path.join(PROJECT_ROOT, "feature_list.json")
    if os.path.exists(fl_path):
        fl = load_json(fl_path)
        for feat in fl.get("features", []):
            if feat.get("feature_id") == feature_id:
                feat["evaluator_score"] = total_score
                break
        save_json(fl_path, fl)
        if verbose:
            print(f"  已更新 feature_list.json")


def cmd_show(args):
    """展示评估结果。"""
    report_path = os.path.join(PROJECT_ROOT, "evaluation_reports", f"{args.feature_id}_evaluation.json")
    if not os.path.exists(report_path):
        print(f"[ERROR] 评估报告不存在: {report_path}", file=sys.stderr)
        sys.exit(1)

    report = load_json(report_path)
    print(f"Feature: {report['feature_id']}")
    print(f"Contract: {report['contract_id']}")
    print(f"评估时间: {report['evaluated_at']}")
    print(f"总分: {report['total_score']}/100")
    print(f"判定: {report['verdict']}")
    print()
    for dim_id, info in report["scores"].items():
        print(f"  {dim_id}: {info['score']}/5 (权重 {info['weight']:.0%}) - {info['reason']}")
    if report.get("improvement_suggestions"):
        print(f"\n改进建议:")
        for s in report["improvement_suggestions"]:
            print(f"  - {s}")


def cmd_history(args):
    """查看历史评估（读取所有评估报告）。"""
    report_dir = os.path.join(PROJECT_ROOT, "evaluation_reports")
    if not os.path.isdir(report_dir):
        print("[INFO] 暂无评估报告")
        return

    reports = sorted(
        [f for f in os.listdir(report_dir) if f.endswith("_evaluation.json")],
        reverse=True,
    )

    if args.feature_id:
        reports = [f for f in reports if f.startswith(args.feature_id)]

    if not reports:
        print("[INFO] 暂无匹配的评估报告")
        return

    for fname in reports:
        report = load_json(os.path.join(report_dir, fname))
        print(f"{report['feature_id']:12s} | {report['verdict']:16s} | {report['total_score']:5}/100 | {report['evaluated_at']}")


def main():
    parser = argparse.ArgumentParser(
        description="Sprint评估脚本 - 评估Sprint产出物质量",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # evaluate
    p_eval = sub.add_parser("evaluate", help="执行评估")
    p_eval.add_argument("feature_id", help="Feature ID (如 F-001)")
    p_eval.add_argument("--rubric", default="evaluator_rubric.json", help="评分标准文件路径")
    p_eval.add_argument("--verbose", "-v", action="store_true", help="输出详细评分过程")
    p_eval.add_argument("--auto-score", action="store_true", help="对无法自动验证的维度使用默认分3")

    # show
    p_show = sub.add_parser("show", help="展示评估结果")
    p_show.add_argument("feature_id", help="Feature ID")

    # history
    p_hist = sub.add_parser("history", help="查看历史评估")
    p_hist.add_argument("feature_id", nargs="?", default=None, help="可选: 过滤指定Feature")

    args = parser.parse_args()

    if args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "history":
        cmd_history(args)


if __name__ == "__main__":
    main()
