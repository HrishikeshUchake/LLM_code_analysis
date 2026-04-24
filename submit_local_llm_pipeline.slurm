#!/bin/bash
#SBATCH --job-name=projectv2_local_llm
#SBATCH --account=jannesar-lab
#SBATCH --partition=nova
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:4
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --chdir=/lustre/hdd/LAS/jannesar-lab/hrishi21/project_v2
#SBATCH --output=projectv2_local_llm_%j.out
#SBATCH --error=projectv2_local_llm_%j.err

set -euo pipefail

REPO_ROOT="/lustre/hdd/LAS/jannesar-lab/hrishi21/project_v2"
cd "$REPO_ROOT"

# Optional module loads if your cluster requires them.
# module load python/3.10
module load cuda/12.8.1-hm53cro

# Optional: activate a project virtualenv if you use one.
source /lustre/hdd/LAS/jannesar-lab/hrishi21/project_v2/.venv/bin/activate

export HF_HOME="/lustre/hdd/LAS/jannesar-lab/hrishi21/hf_cache_dir"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export HF_DATASETS_CACHE="$HF_HOME/datasets"
export HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export TOKENIZERS_PARALLELISM=false
export HF_HUB_DISABLE_XET=1
export HF_HUB_ENABLE_HF_TRANSFER=0

export MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-Coder-32B-Instruct}"

echo "========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Model: $MODEL_ID"
echo "Start time: $(date)"
echo "========================================="

nvidia-smi || true

bash "$REPO_ROOT/run_local_llm_pipeline.sh"

echo "========================================="
echo "End time: $(date)"
echo "========================================="
