#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CODE_DIR="$REPO_ROOT/codes/code_0F"
cd "$REPO_ROOT"
# Output 2
python3 operate_segmentation_data/processing_data.py --script_folder "$CODE_DIR"/ --scan_code "$CODE_DIR"/data_analysis/output_1_code_analysis.json --output "$CODE_DIR"/data_analysis

