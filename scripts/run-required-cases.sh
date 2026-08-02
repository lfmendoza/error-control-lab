#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src/python UV_CACHE_DIR=.cache/uv UV_PROJECT_ENVIRONMENT=.venv
mkdir -p report/evidence
: > report/evidence/required-cases.log
messages=("A" "Laboratorio" "Comunicación confiable entre lenguajes ✓")
for algorithm in hamming crc32; do
  for index in "${!messages[@]}"; do
    for scenario in none one multiple; do
      frame="/tmp/ecl-${algorithm}-${index}-${scenario}.jsonl"
      build/sender encode --algorithm "$algorithm" --text "${messages[$index]}" \
        --noise "$scenario" --seed "$((19644 + index))" --output "$frame" 2>&1 | \
        sed "s|$frame|<trama-temporal>|g" >> report/evidence/required-cases.log
      printf 'algoritmo=%s mensaje=%s escenario=%s\n' "$algorithm" "$((index + 1))" "$scenario" >> report/evidence/required-cases.log
      set +e
      uv run python -m error_control.receiver verify --input "$frame" --machine >> report/evidence/required-cases.log 2>&1
      status=$?
      set -e
      if [[ "$scenario" == none && "$status" -ne 0 ]]; then exit 1; fi
      if [[ "$algorithm" == crc32 && "$scenario" != none && "$status" -ne 3 ]]; then exit 1; fi
      if [[ "$algorithm" == hamming && "$scenario" == one && "$status" -ne 0 ]]; then exit 1; fi
    done
  done
done
printf 'Casos obligatorios completados de forma reproducible.\n' >> report/evidence/required-cases.log
