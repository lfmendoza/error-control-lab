#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR=.cache/uv UV_PROJECT_ENVIRONMENT=.venv
command -v cmake ninja g++ uv just quarto shellcheck pdftotext pdftoppm >/dev/null
uv sync --python 3.13
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build
