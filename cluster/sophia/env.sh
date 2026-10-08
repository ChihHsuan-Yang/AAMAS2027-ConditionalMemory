# Environment for every job on Sophia (sourced by the job scripts).
export ROOT=/lus/eagle/projects/datascience_collab/uhanjir/p1mem
export HF_HOME=$ROOT/hf_cache                 # models/datasets on eagle, not in home (small quota)
export XDG_CACHE_HOME=$ROOT/.cache
export TRITON_CACHE_DIR=$ROOT/.cache/triton
export VLLM_CACHE_ROOT=$ROOT/.cache/vllm
export TOKENIZERS_PARALLELISM=false
export P1_AUTH_DIR=$ROOT/auth                 # holds ALCF's inference_auth_token.py (setup.sh downloads it)
export LMEV2_ROOT=$ROOT/data/lmev2            # LongMemEval-V2 (setup.sh downloads and verifies it)
# outside access (pip, Hugging Face, ALCF endpoint) through the ALCF proxy; LOCAL servers must bypass it
export http_proxy=http://proxy.alcf.anl.gov:3128 https_proxy=http://proxy.alcf.anl.gov:3128
export HTTP_PROXY=$http_proxy HTTPS_PROXY=$https_proxy
export no_proxy=localhost,127.0.0.1,0.0.0.0 NO_PROXY=localhost,127.0.0.1,0.0.0.0
module use /soft/modulefiles 2>/dev/null || true
module load conda 2>/dev/null || true
eval "$(conda shell.bash hook)"               # without this, 'conda activate' fails in scripts (__conda_exe)
conda activate $ROOT/env
export LD_LIBRARY_PATH=$ROOT/env/lib:${LD_LIBRARY_PATH:-}   # conda's newer libstdc++ before /lib64 (CXXABI errors)
cd $ROOT/code
