#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src/python UV_CACHE_DIR=.cache/uv UV_PROJECT_ENVIRONMENT=.venv MPLCONFIGDIR=.cache/matplotlib
mkdir -p report/data report/figures report/evidence .cache/matplotlib
uv run python scripts/generate_experiments.py
