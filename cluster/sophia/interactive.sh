#!/usr/bin/env bash
# 1-hour interactive GPU session for debugging (then: source cluster/sophia/env.sh). Type 'exit' to end it.
qsub -I -q by-gpu -A datascience_collab -l select=${1:-1} -l walltime=${2:-01:00:00} -l filesystems=home:eagle
