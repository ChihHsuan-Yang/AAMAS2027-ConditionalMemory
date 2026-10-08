#!/usr/bin/env bash
# Fill in your ALCF allocation (and username) in every cluster/sophia file. Run ONCE,
# from the unzipped code folder, before setup.sh:
#   bash cluster/sophia/configure.sh <allocation> [username]
set -e
ALLOC=${1:?usage: bash cluster/sophia/configure.sh <allocation> [username]}
USERNAME=${2:-$USER}
cd "$(dirname "$0")"
for f in env.sh setup.sh job.pbs submit.sh interactive.sh status.sh run_experiment.sh; do
  sed -i "s/YOUR_ALLOCATION/$ALLOC/g; s/YOUR_USERNAME/$USERNAME/g" "$f"
done
if grep -q "YOUR_ALLOCATION\|YOUR_USERNAME" env.sh setup.sh job.pbs submit.sh; then
  echo "ERROR: placeholders remain"; exit 1; fi
echo "configured: allocation=$ALLOC  root=/lus/eagle/projects/$ALLOC/$USERNAME/p1mem"
