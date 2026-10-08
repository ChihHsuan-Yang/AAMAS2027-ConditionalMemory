#!/usr/bin/env bash
# Queue state, why jobs wait, and the last lines of every run log.
qstat -u $USER
for j in $(qstat -u $USER 2>/dev/null | awk '$10=="Q"{print $1}'); do
  echo "-- $j"; qstat -f $j | grep -iE "comment|estimated.start"
done
for f in /lus/eagle/projects/datascience_collab/uhanjir/p1mem/logs/*_s*.log; do [ -f "$f" ] && { echo "== $(basename $f)"; tail -2 "$f"; }; done
df -h /lus/eagle/projects/datascience_collab/uhanjir/p1mem | tail -1
