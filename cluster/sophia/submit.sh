#!/usr/bin/env bash
# Submit every job group as a chain of 2 x 06:00:00 jobs (afterany: each resumes the previous one).
#   bash cluster/sophia/submit.sh          # all groups
#   bash cluster/sophia/submit.sh 3        # chains of 3 jobs instead of 2
CHAIN=${1:-2}
cd /lus/eagle/projects/datascience_collab/uhanjir/p1mem/code
Q=qsub; command -v qsub-safe >/dev/null && Q=qsub-safe      # use qsub-safe where ALCF provides it
# Priority order. X1 and X2 both call the Metis reader, whose gateway returns HTTP 429
# above ~24 concurrent requests, and each runner uses 16; so X2 starts only after X1's
# chain ends. X3 calls only the Sophia embedding endpoint and runs in parallel.
submit_chain () {   # submit_chain NAME RUNS [AFTER_JOB_ID] -> prints last job id
  local NAME=$1 RUNS=$2 prev=${3:-}
  for k in $(seq 1 $CHAIN); do
    if [ -z "$prev" ]; then jid=$($Q -N "$NAME" -v RUNS="$RUNS" cluster/sophia/job.pbs)
    else jid=$($Q -N "$NAME" -W depend=afterany:$prev -v RUNS="$RUNS" cluster/sophia/job.pbs); fi
    prev=$jid
  done
  echo "$prev"
}
X1=$(submit_chain "x1_position" "x1_position:main");               echo "X1 (priority 1) chain, last job $X1"
X2=$(submit_chain "x2_fixedctx" "x2_fixedctx:main" "$X1");         echo "X2 (priority 2) starts after $X1, last job $X2"
X3=$(submit_chain "x3_retrieval" "x3_retrieval:main");             echo "X3 (priority 3, parallel) chain, last job $X3"
echo "status: bash cluster/sophia/status.sh"
