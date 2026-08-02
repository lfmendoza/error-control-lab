#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR=.cache/uv UV_PROJECT_ENVIRONMENT=.venv PYTHONPATH=src/python

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/error-control-verify.XXXXXX")
cleanup() { rm -rf "$tmp_dir"; }
trap cleanup EXIT

initial_status="$tmp_dir/initial-status"
final_status="$tmp_dir/final-status"
git status --short > "$initial_status"

required=(cmake ninja g++ uv quarto shellcheck pdftotext pdftoppm rg git)
for tool in "${required[@]}"; do
  command -v "$tool" >/dev/null || { echo "Falta dependencia: $tool" >&2; exit 1; }
done
[[ "$(uv run python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == 3.13 ]]
git check-ignore -q .local/context/instrucciones-lab2.txt

cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build
ctest --test-dir build --output-on-failure
uv run ruff check src/python tests/python scripts/generate_experiments.py
uv run ruff format --check src/python tests/python scripts/generate_experiments.py
shellcheck scripts/*.sh
uv run pytest -q

cmake -S . -B build-sanitize -G Ninja -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON
cmake --build build-sanitize
ASAN_OPTIONS=detect_leaks=1 ctest --test-dir build-sanitize --output-on-failure

scripts/run-required-cases.sh "$tmp_dir/evidence"
scripts/run-experiments.sh "$tmp_dir/results"
scripts/render-report.sh "$tmp_dir/deliverables"

uv run python - "$tmp_dir/results" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = list(csv.DictReader((root / "data" / "experiments.csv").open(encoding="utf-8")))
summary = json.loads((root / "data" / "summary.json").read_text(encoding="utf-8"))
assert len(rows) == 480 and summary["total_transmissions"] == 480
assert {row["algorithm"] for row in rows} == {"hamming", "crc32"}
assert all(sum(row["algorithm"] == algorithm for row in rows) == 240 for algorithm in ("hamming", "crc32"))
assert summary["false_negatives"] == 0
for algorithm, metrics in summary["aggregate"].items():
    assert metrics["total_transmissions"] == 240
    assert 0 <= metrics["altered_transmissions"] <= 240
    assert metrics["conditional_detection_rate"] == 1.0
    assert metrics["conditional_false_negative_rate"] == 0.0
    assert metrics["mean_encode_ns"] > 0 and metrics["mean_decode_ns"] > 0
    assert metrics["mean_encode_ns"] < 10**9 and metrics["mean_decode_ns"] < 10**10
assert summary["limitations"]["hamming_three_bit_miscorrection"]["positions"] == [0, 1, 3]
assert summary["limitations"]["hamming_three_bit_miscorrection"]["result"]["message"] == "Q"
assert summary["limitations"]["crc_search"]["undetected"] is None
print("Métricas temporales y deterministas validadas")
PY

for artifact in \
  deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.html \
  deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.pdf \
  report/data/experiments.csv report/data/results.md report/data/summary.json \
  report/figures/processing_time.png; do
  test -s "$artifact" || { echo "Artefacto comprometido ausente/vacío: $artifact" >&2; exit 1; }
done
for expected in "480 transmisiones reales" "| HAMMING | 240 |" "| CRC32 | 240 |"; do
  rg -Fq "$expected" report/data/results.md || { echo "Resultado publicado incompleto: $expected" >&2; exit 1; }
done
pdf_text="$tmp_dir/report.txt"
pdftotext deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.pdf "$pdf_text"
for expected in \
  "Luis Fernando Mendoza Alvarez" "19644" "github.com/lfmendoza/error-control-lab" \
  "Descripción de la práctica" "Objetivos" "Arquitectura por capas" \
  "Diseño del formato de trama" "Fundamento de Hamming SECDED" \
  "Fundamento de CRC-32" "Metodología experimental" "Escenarios de prueba" \
  "Resultados" "Discusión" "Limitaciones" "Conclusiones" "Referencias"; do
  rg -Fq "$expected" "$pdf_text" || { echo "Texto ausente del PDF: $expected" >&2; exit 1; }
done
test -s "$tmp_dir/evidence/required-cases.log"

mapfile -t scan_files < <(rg --files -g '!uv.lock' -g '!scripts/verify-lab.sh' -g '!report/evidence/**' -g '!report/data/**' -g '!deliverables/**' -g '!report/pdf-pages/**')
if rg -n '\b(TODO|FIXME|TBD)\b' "${scan_files[@]}"; then exit 1; fi
if rg -n -i '/home/|\.local/|ChatGPT|OpenAI|Codex|prompt|agente generativo' "${scan_files[@]}"; then exit 1; fi
if rg -n -i '(api[_-]?key|secret|token|password)[[:space:]]*[:=][[:space:]]*.{8,}' "${scan_files[@]}"; then exit 1; fi

git diff --check
test -z "$(git diff --cached --name-only)"
for artifact in .venv build build-sanitize .cache .pytest_cache .ruff_cache report/pdf-pages; do
  git check-ignore -q "$artifact" || { echo "Artefacto no ignorado: $artifact" >&2; exit 1; }
done

git status --short > "$final_status"
diff -u "$initial_status" "$final_status"
printf 'Verificación idempotente completa; no se modificaron archivos versionados.\n'
