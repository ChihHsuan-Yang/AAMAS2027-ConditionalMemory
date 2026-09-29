#!/bin/bash
# Testable body of the P1 cell runner. Runs identically on a laptop and on an
# Aurora compute node; the .pbs wrapper only supplies scheduler directives.
#
# Run locally:  REPO_ROOT=$PWD bash jobs/p1_cells_aurora.sh --dry-run
set -uo pipefail

: "${REPO_ROOT:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${P1_CACHE:=$REPO_ROOT/results/cache/reader_metis.jsonl}"
: "${P1_LEDGER:=$REPO_ROOT/results/ledgers/cells_metis.jsonl}"
: "${P1_WORKERS:=16}"
: "${P1_CELLS:=}"
: "${PY:=python3}"

# Aurora compute nodes cannot reach the inference gateway without the proxy,
# and a preset no_proxy will route around it. Only set these off-login.
if [[ -n "${PBS_JOBID:-}" ]]; then
  export HTTP_PROXY="http://proxy.alcf.anl.gov:3128"
  export HTTPS_PROXY="http://proxy.alcf.anl.gov:3128"
  export http_proxy="$HTTP_PROXY"
  export https_proxy="$HTTPS_PROXY"
  unset no_proxy NO_PROXY
fi

echo "[p1] host=$(hostname) jobid=${PBS_JOBID:-none} workers=$P1_WORKERS"
echo "[p1] cache=$P1_CACHE"
echo "[p1] ledger=$P1_LEDGER"
mkdir -p "$(dirname "$P1_CACHE")" "$(dirname "$P1_LEDGER")"

if [[ -z "$P1_CELLS" ]]; then
  echo "[p1] ERROR: P1_CELLS (path to a cells JSONL) is required" >&2
  exit 2
fi

cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT/src" "$PY" scripts/run_cells.py \
  --cells "$P1_CELLS" \
  --cache "$P1_CACHE" \
  --ledger "$P1_LEDGER" \
  --workers "$P1_WORKERS" \
  "$@"
rc=${PIPESTATUS[0]}

# A PBS exit status of 0 is NOT success. Verify the artifact exists and has
# grown, and surface the real return code.
echo "[p1] runner rc=$rc"
# A dry run legitimately produces no ledger; skip the artifact check for it.
for a in "$@"; do [[ "$a" == "--dry-run" ]] && { echo "[p1] dry run, skipping artifact check"; exit "$rc"; }; done
if [[ ! -s "$P1_LEDGER" ]]; then
  echo "[p1] FAIL: ledger $P1_LEDGER is missing or empty" >&2
  exit 3
fi
echo "[p1] ledger rows: $(wc -l < "$P1_LEDGER")"
exit "$rc"
