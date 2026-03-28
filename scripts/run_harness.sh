#!/usr/bin/env bash
# run_harness.sh - OpenClaw Harness Engineering 主控脚本
# 用法: ./run_harness.sh [--config FILE] [--feature-id ID] [--phase NUM] [--dry-run] [--help]

set -euo pipefail

CONFIG_FILE="HARNESS_CONFIG.json"
FEATURE_ID=""
PHASE=""
DRY_RUN=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

usage() {
    cat <<EOF
OpenClaw Harness Engineering - 主控脚本

用法: $0 [选项]

选项:
  --config FILE       配置文件路径 (默认: HARNESS_CONFIG.json)
  --feature-id ID     只处理指定的Feature (如: F-001)
  --phase NUM         只处理指定Phase的Features (如: 1, 2)
  --dry-run           只打印将要执行的操作，不实际执行
  --help              显示此帮助信息

示例:
  $0                              # 处理所有待处理Feature
  $0 --dry-run                    # 预览将要执行的操作
  $0 --feature-id F-002           # 只处理F-002
  $0 --phase 2                    # 只处理Phase 2的Feature
  $0 --config my_config.json      # 使用自定义配置

Sprint Cycle流程:
  [1/4] 创建Sprint Contract  → negotiate_sprint_contract.py create
  [2/4] Generator实现         → spawn coding agent
  [3/4] Evaluator评估         → evaluate_sprint.py
  [4/4] 检查结果              → 决定通过或迭代
EOF
    exit 0
}

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $*" >&2; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; exit 1; }

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG_FILE="$2"; shift 2 ;;
        --feature-id) FEATURE_ID="$2"; shift 2 ;;
        --phase) PHASE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) usage ;;
        *) error "未知参数: $1 (使用 --help 查看帮助)" ;;
    esac
done

cd "$PROJECT_DIR"

# 读取配置
[[ ! -f "$CONFIG_FILE" ]] && error "配置文件不存在: $CONFIG_FILE"
CONFIG=$(cat "$CONFIG_FILE")
log "已加载配置: $CONFIG_FILE"

# 提取配置值
CONTRACTS_DIR=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['file_paths']['sprint_contracts_dir'])" 2>/dev/null || echo "sprint_contracts/")
REPORTS_DIR=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['file_paths']['evaluation_reports_dir'])" 2>/dev/null || echo "evaluation_reports/")
MAX_ITER=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['sprint_defaults']['max_iterations'])" 2>/dev/null || echo "3")
PASS_THRESHOLD=$(echo "$CONFIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['sprint_defaults']['score_threshold_pass'])" 2>/dev/null || echo "80")

mkdir -p "$CONTRACTS_DIR" "$REPORTS_DIR"

# 读取Feature List
FEATURE_LIST="feature_list.json"
[[ ! -f "$FEATURE_LIST" ]] && error "Feature List不存在: $FEATURE_LIST"

# 筛选待处理的Features
FILTER_CMD="import sys,json
data=json.load(sys.stdin)
features=[f for f in data['features']]
"
[[ -n "$FEATURE_ID" ]] && FILTER_CMD+="features=[f for f in features if f['feature_id']=='$FEATURE_ID']
"
[[ -n "$PHASE" ]] && FILTER_CMD+="features=[f for f in features if f.get('phase')==$PHASE]
"
FILTER_CMD+="features=[f for f in features if f.get('status') not in ('done','blocked')]
"
FILTER_CMD+="for f in features: print(f['feature_id'])
"

FEATURES=$(echo "$FILTER_CMD" | python3 -c "$(cat)" < "$FEATURE_LIST" 2>/dev/null)

if [[ -z "$FEATURES" ]]; then
    log "没有待处理的Feature"
    exit 0
fi

TOTAL=$(echo "$FEATURES" | wc -l)
CURRENT=0
PASSED=0
FAILED=0

log "找到 $TOTAL 个待处理Feature(s)"
echo "========================================"

for FID in $FEATURES; do
    CURRENT=$((CURRENT + 1))
    echo ""
    log "[$CURRENT/$TOTAL] 处理 Feature: $FID"
    echo "----------------------------------------"

    # [1/4] 创建Sprint Contract
    log "[1/4] 创建Sprint Contract"
    CONTRACT_FILE="${CONTRACTS_DIR}${FID}_contract.json"
    if $DRY_RUN; then
        log "  [DRY-RUN] 将执行: python3 scripts/negotiate_sprint_contract.py create --feature-id $FID --auto-agree"
    else
        if [[ -f "$CONTRACT_FILE" ]]; then
            log "  Contract已存在: $CONTRACT_FILE, 跳过创建"
        else
            python3 scripts/negotiate_sprint_contract.py create --feature-id "$FID" --auto-agree || {
                error "[1/4] 创建Sprint Contract失败: $FID"
            }
            log "  Contract已创建: $CONTRACT_FILE"
        fi
    fi

    # [2/4] Generator实现
    log "[2/4] Generator实现"
    if $DRY_RUN; then
        log "  [DRY-RUN] 将spawn coding agent实现Feature: $FID"
    else
        log "  ⚠️  需要spawn coding agent来实现此Feature"
        log "  提示: 使用 sessions_spawn runtime=subagent 来启动Generator Agent"
        log "  Contract文件: $CONTRACT_FILE"
    fi

    # [3/4] Evaluator评估
    log "[3/4] Evaluator评估"
    if $DRY_RUN; then
        log "  [DRY-RUN] 将执行: python3 scripts/evaluate_sprint.py --feature-id $FID"
    else
        if [[ -f "scripts/evaluate_sprint.py" ]]; then
            python3 scripts/evaluate_sprint.py --feature-id "$FID" || {
                warn "  Evaluator评估失败或脚本不存在"
            }
        else
            log "  ⚠️  evaluate_sprint.py 尚未创建，跳过评估"
        fi
    fi

    # [4/4] 检查结果
    log "[4/4] 检查结果"
    if $DRY_RUN; then
        log "  [DRY-RUN] 将检查评估结果，决定通过或迭代"
    else
        if [[ -f "$CONTRACT_FILE" ]]; then
            VERDICT=$(python3 -c "import json; d=json.load(open('$CONTRACT_FILE')); print(d.get('evaluation_result',{}).get('verdict','pending'))" 2>/dev/null || echo "pending")
            SCORE=$(python3 -c "import json; d=json.load(open('$CONTRACT_FILE')); print(d.get('evaluation_result',{}).get('weighted_total','N/A'))" 2>/dev/null || echo "N/A")
            ITER=$(python3 -c "import json; d=json.load(open('$CONTRACT_FILE')); print(d.get('iteration',0))" 2>/dev/null || echo "0")
            log "  状态: verdict=$VERDICT, score=$SCORE, iteration=$ITER/$MAX_ITER"
            if [[ "$VERDICT" == "pass" ]]; then
                log "  ✅ 通过"
                PASSED=$((PASSED + 1))
            else
                log "  ⏳ 待评估或需迭代"
            fi
        else
            log "  Contract不存在，跳过结果检查"
        fi
    fi

    echo "----------------------------------------"
done

echo ""
echo "========================================"
log "进度汇总:"
log "  总计: $TOTAL"
log "  通过: $PASSED"
log "  待处理: $((TOTAL - PASSED - FAILED))"
log "  失败: $FAILED"
echo "========================================"
