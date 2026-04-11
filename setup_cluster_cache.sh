#!/usr/bin/env bash
set -euo pipefail

TARGET_BASE="/home/hrishi21"
TARGET_HF_CACHE="$TARGET_BASE/hf_cache_dir/huggingface"
HF_SOURCE="$HOME/.cache/huggingface"

echo "Setting up HuggingFace cache storage redirection to: $TARGET_HF_CACHE"

# 1. Create the new parent directories
mkdir -p "$TARGET_BASE/hf_cache_dir"

# 2. Check and migrate existing HuggingFace cache
if [ -d "$HF_SOURCE" ] && [ ! -L "$HF_SOURCE" ]; then
    echo "Moving existing HuggingFace cache from $HF_SOURCE to $TARGET_HF_CACHE"
    mv "$HF_SOURCE" "$TARGET_HF_CACHE"
else
    # Automatically create the target if source didn't exist
    mkdir -p "$TARGET_HF_CACHE"
fi

# 3. Create the symbolic link
if [ ! -L "$HF_SOURCE" ]; then
    echo "Creating symbolic link from $HF_SOURCE to $TARGET_HF_CACHE"
    # Ensure parent (.cache) exists
    mkdir -p "$(dirname "$HF_SOURCE")"
    ln -s "$TARGET_HF_CACHE" "$HF_SOURCE"
    echo "Symlink created successfully."
else
    echo "Symlink $HF_SOURCE already exists."
fi

echo "Done."
