#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# USER INPUTS (edit or export before running)
# -----------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

: "${CODE_DIR:=$REPO_ROOT/codes/code_0F}"
: "${MODEL_ID:=Qwen/Qwen2.5-Coder-32B-Instruct}"
: "${VENV_PATH:=}"

# HF cache paths (recommended on clusters)
: "${HF_HOME:=/lustre/hdd/LAS/jannesar-lab/hrishi21/hf_cache_dir}"
: "${TRANSFORMERS_CACHE:=$HF_HOME/transformers}"
: "${HF_DATASETS_CACHE:=$HF_HOME/datasets}"
: "${HUGGINGFACE_HUB_CACHE:=$HF_HOME/hub}"
: "${TOKENIZERS_PARALLELISM:=false}"

export HF_HOME TRANSFORMERS_CACHE HF_DATASETS_CACHE HUGGINGFACE_HUB_CACHE TOKENIZERS_PARALLELISM
export HF_HUB_DISABLE_XET=1
export HF_HUB_ENABLE_HF_TRANSFER=0
mkdir -p "$HF_HOME" "$TRANSFORMERS_CACHE" "$HF_DATASETS_CACHE" "$HUGGINGFACE_HUB_CACHE"

if [[ -n "$VENV_PATH" ]]; then
  # Optional Python environment activation for cluster jobs.
  source "$VENV_PATH/bin/activate"
fi

echo "========================================="
echo "Repo root: $REPO_ROOT"
echo "Model: $MODEL_ID"
echo "Start time: $(date)"
echo "========================================="

# Re-run the LLM stage with requested model id while preserving current pipeline behavior.
bash "$CODE_DIR/T6_execute_segmentation.sh"
bash "$CODE_DIR/T7_execute_segmentation.sh"
python3 llm/prompt_experiment.py \
  --provider local_transformers \
  --model "$MODEL_ID" \
  --input_code "$CODE_DIR/data_analysis/output_3_segments.json" \
  --input_dictionary "$CODE_DIR/data_analysis/output_3_dictionary.json" \
  --output "$CODE_DIR/data_analysis"

echo "========================================="
echo "End time: $(date)"
echo "========================================="
