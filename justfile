set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

export UV_CACHE_DIR := ".cache/uv"
export UV_PROJECT_ENVIRONMENT := ".venv"
export PYTHONPATH := "src/python"

bootstrap:
    uv sync --python 3.13

build:
    cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
    cmake --build build

test: build
    ctest --test-dir build --output-on-failure
    uv run pytest -q

lint:
    uv run ruff check src/python tests/python scripts/generate_experiments.py
    uv run ruff format --check src/python tests/python scripts/generate_experiments.py
    shellcheck scripts/*.sh

required-cases: build
    scripts/run-required-cases.sh

experiments: build
    scripts/run-experiments.sh

report:
    scripts/render-report.sh

verify:
    scripts/verify-lab.sh
