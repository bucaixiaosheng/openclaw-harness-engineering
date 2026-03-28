#!/usr/bin/env python3
"""Feature Progress Checker for Harness Engineering.

Usage:
    python3 check_feature_progress.py [options]

Examples:
    python3 check_feature_progress.py                    # Show progress
    python3 check_feature_progress.py --phase 2          # Filter by phase
    python3 check_feature_progress.py --status pending   # Filter by status
    python3 check_feature_progress.py --json             # JSON output
    python3 check_feature_progress.py --watch            # Auto-refresh every 30s
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime


def load_feature_list(path="feature_list.json"):
    """Load feature_list.json from given path."""
    if not os.path.exists(path):
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_features(features, phase=None, status=None):
    """Filter features by phase and/or status."""
    result = features
    if phase is not None:
        result = [f for f in result if f.get("phase") == phase]
    if status is not None:
        result = [f for f in result if f.get("status") == status]
    return result


def progress_bar(ratio, width=25):
    """Generate an ASCII progress bar."""
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


def compute_stats(features):
    """Compute statistics from feature list."""
    total = len(features)
    counts = {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0}
    for f in features:
        s = f.get("status", "pending")
        if s in counts:
            counts[s] += 1
    pct = (counts["done"] / total * 100) if total > 0 else 0.0
    return total, counts, pct


def compute_priority_stats(features):
    """Compute per-priority statistics."""
    prios = {}
    for f in features:
        p = f.get("priority", "P?")
        if p not in prios:
            prios[p] = {"total": 0, "done": 0}
        prios[p]["total"] += 1
        if f.get("status") == "done":
            prios[p]["done"] += 1
    return prios


def format_text(features, all_features, phase=None, status=None):
    """Format progress as ASCII text."""
    total, counts, pct = compute_stats(features)
    lines = []
    lines.append("=== Feature Progress ===")
    lines.append(
        f"Total: {total} | Done: {counts['done']} ({pct:.1f}%) "
        f"| In Progress: {counts['in_progress']} "
        f"| Pending: {counts['pending']} | Blocked: {counts['blocked']}"
    )
    lines.append("")

    # Priority breakdown (based on all features for context, filtered for display)
    prios = compute_priority_stats(all_features)
    lines.append("By Priority:")
    for p in sorted(prios.keys()):
        d, t = prios[p]["done"], prios[p]["total"]
        ratio = d / t if t > 0 else 0
        pct_p = ratio * 100
        bar = progress_bar(ratio)
        lines.append(f"  {p}: {d}/{t} done ({pct_p:.1f}%)  {bar}")
    lines.append("")

    # Show non-done features
    non_done = [f for f in features if f.get("status") != "done"]
    if non_done:
        by_status = {}
        for f in non_done:
            s = f.get("status", "pending")
            by_status.setdefault(s, []).append(f)
        for s in ["in_progress", "pending", "blocked"]:
            items = by_status.get(s, [])
            if items:
                label = s.replace("_", " ").title()
                lines.append(f"{label} Features:")
                for f in items:
                    fid = f.get("feature_id", "?")
                    name = f.get("name", "?")
                    pri = f.get("priority", "?")
                    ph = f.get("phase", "?")
                    lines.append(f"  [{fid}] {name} ({pri}, Phase {ph})")
        lines.append("")

    return "\n".join(lines)


def format_json(features, all_features, phase=None, status=None):
    """Format progress as JSON."""
    total, counts, pct = compute_stats(features)
    prios = compute_priority_stats(all_features)
    return json.dumps(
        {
            "total": total,
            "counts": counts,
            "completion_pct": round(pct, 1),
            "by_priority": {
                p: {"done": v["done"], "total": v["total"], "pct": round(v["done"] / v["total"] * 100, 1) if v["total"] else 0}
                for p, v in prios.items()
            },
            "features": [
                {
                    "id": f.get("feature_id"),
                    "name": f.get("name"),
                    "status": f.get("status"),
                    "priority": f.get("priority"),
                    "phase": f.get("phase"),
                    "score": f.get("evaluator_score"),
                }
                for f in features
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Check feature progress for Harness Engineering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                      Show overall progress
  %(prog)s --phase 2            Show only Phase 2 features
  %(prog)s --status pending     Show only pending features
  %(prog)s --json               Output as JSON
  %(prog)s --watch              Auto-refresh every 30 seconds
""",
    )
    parser.add_argument("--file", default="feature_list.json", help="Path to feature_list.json (default: feature_list.json)")
    parser.add_argument("--phase", type=int, default=None, help="Filter by phase number")
    parser.add_argument("--status", default=None, choices=["pending", "in_progress", "done", "blocked"], help="Filter by status")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--watch", action="store_true", help="Auto-refresh every 30 seconds")
    args = parser.parse_args()

    def run_once():
        data = load_feature_list(args.file)
        all_features = data.get("features", [])
        filtered = filter_features(all_features, args.phase, args.status)
        if args.json_output:
            print(format_json(filtered, all_features, args.phase, args.status))
        else:
            print(format_text(filtered, all_features, args.phase, args.status))

    args.json_output = args.json

    if args.watch:
        while True:
            os.system("clear" if os.name == "posix" else "cls")
            print(f"--- Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            run_once()
            print("\nRefreshing in 30s... (Ctrl+C to stop)")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                print("\nStopped.")
                break
    else:
        run_once()


if __name__ == "__main__":
    main()
