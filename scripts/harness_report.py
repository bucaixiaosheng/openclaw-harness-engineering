#!/usr/bin/env python3
"""Harness Engineering Report Generator.

Usage:
    python3 harness_report.py [options]

Examples:
    python3 harness_report.py                       # Generate markdown report
    python3 harness_report.py --output report.md    # Specify output file
    python3 harness_report.py --html                # Generate HTML report
"""

import argparse
import json
import os
import sys
from datetime import datetime


def load_json(path):
    """Load JSON file, return None if not found."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def scan_directory(base_dir, subdir, pattern="*.json"):
    """Scan a directory for JSON files."""
    d = os.path.join(base_dir, subdir)
    if not os.path.isdir(d):
        return []
    import glob
    return sorted(glob.glob(os.path.join(d, pattern)))


def generate_markdown(feature_list, contracts, eval_reports, project_name):
    """Generate Markdown report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S CST")
    features = feature_list.get("features", []) if feature_list else []
    total = len(features)
    counts = {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0}
    for f in features:
        s = f.get("status", "pending")
        if s in counts:
            counts[s] += 1
    done_pct = (counts["done"] / total * 100) if total > 0 else 0.0

    # Scores
    scores = []
    iterations = []
    for f in features:
        sc = f.get("evaluator_score")
        if sc is not None:
            scores.append(sc)
        it = f.get("iteration_count", 0)
        if it:
            iterations.append(it)
    avg_score = sum(scores) / len(scores) if scores else 0
    avg_iter = sum(iterations) / len(iterations) if iterations else 0

    lines = []
    lines.append("# Harness Engineering Report")
    lines.append(f"> Generated: {now}")
    lines.append(f"> Project: {project_name}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Features | {total} |")
    lines.append(f"| Completed | {counts['done']} ({done_pct:.0f}%) |")
    lines.append(f"| In Progress | {counts['in_progress']} |")
    lines.append(f"| Pending | {counts['pending']} |")
    lines.append(f"| Blocked | {counts['blocked']} |")
    lines.append(f"| Avg Score | {avg_score:.1f}/100 |")
    lines.append(f"| Max Score | {max(scores):.0f}/100 |" if scores else "| Max Score | N/A |")
    lines.append(f"| Min Score | {min(scores):.0f}/100 |" if scores else "| Min Score | N/A |")
    lines.append(f"| Iterations | {avg_iter:.1f} avg |")
    lines.append("")

    # By Phase
    phases = {}
    for f in features:
        ph = f.get("phase", 0)
        phases.setdefault(ph, []).append(f)

    lines.append("## Features by Phase")
    for ph in sorted(phases.keys()):
        flist = phases[ph]
        d = sum(1 for f in flist if f.get("status") == "done")
        lines.append(f"### Phase {ph} ({d}/{len(flist)} done)")
        lines.append("| ID | Name | Priority | Status | Score | Iterations |")
        lines.append("|----|------|----------|--------|-------|------------|")
        for f in flist:
            fid = f.get("feature_id", "?")
            name = f.get("name", "?")
            pri = f.get("priority", "?")
            status = f.get("status", "?")
            sc = f.get("evaluator_score")
            sc_str = f"{sc:.0f}" if sc is not None else "-"
            it = f.get("iteration_count", 0)
            lines.append(f"| {fid} | {name} | {pri} | {status} | {sc_str} | {it} |")
        lines.append("")

    # Iteration history
    multi_iter = [f for f in features if f.get("iteration_count", 0) > 1]
    if multi_iter:
        lines.append("## Features Requiring Multiple Iterations")
        lines.append("| ID | Name | Iterations |")
        lines.append("|----|-------|------------|")
        for f in sorted(multi_iter, key=lambda x: x.get("iteration_count", 0), reverse=True):
            lines.append(f"| {f.get('feature_id')} | {f.get('name')} | {f.get('iteration_count')} |")
        lines.append("")

    # Needs review
    needs_review = [f for f in features if f.get("status") == "blocked" or (f.get("evaluator_score") is not None and f.get("evaluator_score") < 80)]
    if needs_review:
        lines.append("## Features Needing Manual Review")
        for f in needs_review:
            fid = f.get("feature_id", "?")
            name = f.get("name", "?")
            reason = "Blocked" if f.get("status") == "blocked" else f"Low score ({f.get('evaluator_score'):.0f})"
            lines.append(f"- **{fid}** {name} — {reason}")
        lines.append("")

    # Contracts scanned
    if contracts:
        lines.append(f"## Sprint Contracts ({len(contracts)} found)")
        lines.append("")
        for c in contracts:
            data = load_json(c)
            if data:
                cid = data.get("contract_id", os.path.basename(c))
                fid = data.get("feature_id", "?")
                status = data.get("status", "?")
                it = data.get("iteration", 0)
                lines.append(f"- `{cid}` → {fid} (status: {status}, iteration: {it})")
        lines.append("")

    # Evaluation reports scanned
    if eval_reports:
        lines.append(f"## Evaluation Reports ({len(eval_reports)} found)")
        lines.append("")
        for r in eval_reports:
            data = load_json(r)
            if data:
                verdict = data.get("evaluation_result", {}).get("verdict", "?")
                total_score = data.get("evaluation_result", {}).get("weighted_total", "?")
                lines.append(f"- `{os.path.basename(r)}` — verdict: {verdict}, score: {total_score}")
        lines.append("")

    return "\n".join(lines)


def markdown_to_html(md):
    """Convert markdown to simple HTML with CSS."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        "<title>Harness Engineering Report</title>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #333; }",
        "h1 { border-bottom: 2px solid #4a9eff; padding-bottom: 0.3em; }",
        "h2 { border-bottom: 1px solid #ddd; padding-bottom: 0.2em; margin-top: 2em; }",
        "table { border-collapse: collapse; width: 100%; margin: 1em 0; }",
        "th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }",
        "th { background: #f5f5f5; font-weight: 600; }",
        "tr:nth-child(even) { background: #fafafa; }",
        "blockquote { border-left: 3px solid #4a9eff; padding-left: 1em; color: #666; margin: 0.5em 0; }",
        "code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }",
        "strong { color: #d63384; }",
        "</style>",
        "</head><body>",
    ]
    for line in md.split("\n"):
        if line.startswith("# "):
            html_parts.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_parts.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("> "):
            html_parts.append(f"<blockquote>{line[2:]}</blockquote>")
        elif line.startswith("| ") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            row = "".join(f"<td>{c}</td>" for c in cells)
            html_parts.append(f"<tr>{row}</tr>")
        elif line.startswith("|---"):
            continue
        elif line.startswith("- "):
            html_parts.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_parts.append("")
        else:
            # Bold
            import re
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
            html_parts.append(f"<p>{line}</p>")
    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Harness Engineering report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                       Generate report to harness_report.md
  %(prog)s --output report.md    Specify output file
  %(prog)s --html                Generate HTML report
""",
    )
    parser.add_argument("--output", default="harness_report.md", help="Output file path (default: harness_report.md)")
    parser.add_argument("--html", action="store_true", help="Output as HTML")
    parser.add_argument("--dir", default=".", help="Project root directory (default: current)")
    args = parser.parse_args()

    base = os.path.abspath(args.dir)
    feature_list = load_json(os.path.join(base, "feature_list.json"))
    if feature_list is None:
        # Try template
        feature_list = load_json(os.path.join(base, "feature_list_template.json"))

    contracts = scan_directory(base, "sprint_contracts")
    eval_reports = scan_directory(base, "evaluation_reports")

    project_name = os.path.basename(base)
    md = generate_markdown(feature_list, contracts, eval_reports, project_name)

    if args.html:
        output = markdown_to_html(md)
        out_file = args.output if args.output.endswith(".html") else args.output.rsplit(".", 1)[0] + ".html"
    else:
        output = md
        out_file = args.output

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Report written to: {out_file}")


if __name__ == "__main__":
    main()
