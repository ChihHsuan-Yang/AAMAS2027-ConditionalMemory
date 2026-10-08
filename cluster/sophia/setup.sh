#!/usr/bin/env bash
# ONE-TIME setup on a Sophia LOGIN node. Run from your unzipped code folder (NOT from inside $ROOT/code):
#   bash cluster/sophia/setup.sh
set -e
ROOT=/lus/eagle/projects/datascience_collab/uhanjir/p1mem
SRC=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p $ROOT/{runs,logs,hf_cache,.cache}
case "$ROOT/code/" in "$SRC"/*) echo "run setup.sh from the unzipped folder, not from a parent of $ROOT/code"; exit 1;; esac
if [ "$SRC" != "$ROOT/code" ]; then rm -rf $ROOT/code; mkdir -p $ROOT/code; cp -r "$SRC"/. $ROOT/code/; fi
export http_proxy=http://proxy.alcf.anl.gov:3128 https_proxy=http://proxy.alcf.anl.gov:3128
export HF_HOME=$ROOT/hf_cache
module use /soft/modulefiles 2>/dev/null || true
module load conda
eval "$(conda shell.bash hook)"
[ -d $ROOT/env ] || conda create -y -p $ROOT/env python=3.11
conda activate $ROOT/env
cd $ROOT/code
python -m pip install --upgrade pip
python -m pip install -e . tokenizers huggingface_hub scipy numpy pytest


echo "== LongMemEval-V2 dataset and the benchmark's tokenizer (Hugging Face, through the proxy)"
mkdir -p $ROOT/data/lmev2 $ROOT/auth
ROOT_LMEV2=$ROOT/data/lmev2 python - <<'P'
import os, sys
from pathlib import Path
from huggingface_hub import hf_hub_download, snapshot_download
root = Path(os.environ["ROOT_LMEV2"])
snapshot_download("xiaowu0162/longmemeval-v2", repo_type="dataset", local_dir=str(root))
print("dataset ->", root)
# only tokenizer.json is needed for token counts (not the 9B weights)
print("tokenizer ->", hf_hub_download("Qwen/Qwen3.5-9B", "tokenizer.json"))
sys.path.insert(0, "src")
from p1mem.adapters import lmev2
lmev2.verify_checksums(root)
print("checksums: OK")
P
python -m pytest -q tests/test_memory_tokens.py tests/test_lmev2_scoring.py

echo "== ALCF inference endpoint login (browser link; choose your ALCF identity)"
[ -f $ROOT/auth/inference_auth_token.py ] || curl -sSfL -o $ROOT/auth/inference_auth_token.py \
  https://raw.githubusercontent.com/argonne-lcf/inference-endpoints/refs/heads/main/inference_auth_token.py
python -m pip install globus-sdk
( cd $ROOT/auth && python inference_auth_token.py authenticate )
( cd $ROOT/auth && python inference_auth_token.py get_access_token >/dev/null && echo "endpoint token: OK" )
echo "setup done. Next: bash cluster/sophia/interactive.sh (debug)  or  bash cluster/sophia/submit.sh"
