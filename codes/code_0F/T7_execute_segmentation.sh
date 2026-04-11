#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CODE_DIR="$REPO_ROOT/codes/code_0F"
cd "$REPO_ROOT"
# Output 3
python3 operate_segmentation_data/processing_segmentation.py --input_json "$CODE_DIR"/data_analysis/output_2_processed_code.json --input_variable "$CODE_DIR"/data_analysis/output_2_variables.txt --output "$CODE_DIR"/data_analysis
