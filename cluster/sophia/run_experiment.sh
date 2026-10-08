#!/usr/bin/env bash
# Run ONE experiment. Called by job.pbs; also usable by hand from an interactive node.
#   bash cluster/sophia/run_experiment.sh <x1_position|x2_fixedctx|x3_retrieval> <out_dir>
# DRY_RUN=1 builds every request and checks counts without any endpoint call.
set -uo pipefail
EXP=$1 OUT=$2
[ -n "${ROOT:-}" ] || source "$(dirname "$0")/env.sh"
mkdir -p "$OUT"
EXTRA=(); [ "${DRY_RUN:-0}" = 1 ] && EXTRA=(--dry-run)
case "$EXP" in
  x1_position)  SCRIPT=scripts/x1_position_session.py ;;   # PRIORITY 1: second session, randomized position
  x2_fixedctx)  SCRIPT=scripts/x2_fixed_context.py ;;      # PRIORITY 2: fixed-total-context representations
  x3_retrieval) SCRIPT=scripts/x3_retrieval_baseline.py ;; # PRIORITY 3: retrieval baselines (embeddings only)
  *) echo "unknown experiment $EXP"; exit 2 ;;
esac
echo "[$(date +%F' '%T)] $EXP -> $OUT ${EXTRA[*]:-}"
python -u "$SCRIPT" --root "$LMEV2_ROOT" --out "$OUT" "${EXTRA[@]}"
