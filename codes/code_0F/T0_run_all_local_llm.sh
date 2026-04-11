#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$SCRIPT_DIR/T6_execute_segmentation.sh"
bash "$SCRIPT_DIR/T7_execute_segmentation.sh"
bash "$SCRIPT_DIR/T8_execute_llm_p1.sh"
