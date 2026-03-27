#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python src/extract_map.py "${@:-input/}"
