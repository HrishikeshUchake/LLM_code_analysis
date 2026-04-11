#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CODE_DIR="$REPO_ROOT/codes/code_0F"
cd "$REPO_ROOT"

MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-Coder-32B-Instruct}"

HF_HOME="${HF_HOME:-/lustre/hdd/LAS/jannesar-lab/hrishi21/hf_cache}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
HF_DATASETS_CACHE="${HF_DATASETS_CACHE:-$HF_HOME/datasets}"
HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

export HF_HOME TRANSFORMERS_CACHE HF_DATASETS_CACHE HUGGINGFACE_HUB_CACHE TOKENIZERS_PARALLELISM
mkdir -p "$HF_HOME" "$TRANSFORMERS_CACHE" "$HF_DATASETS_CACHE" "$HUGGINGFACE_HUB_CACHE"

export HF_HUB_DISABLE_XET=1
export HF_HUB_ENABLE_HF_TRANSFER=0
python3 llm/prompt_experiment.py --provider local_transformers --model "$MODEL_ID" --input_code "$CODE_DIR"/data_analysis/output_3_segments.json --input_dictionary "$CODE_DIR"/data_analysis/output_3_dictionary.json --output "$CODE_DIR"/data_analysis
