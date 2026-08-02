#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR=.cache/uv UV_PROJECT_ENVIRONMENT=.venv PYTHONPATH=src/python

required=(cmake ninja g++ uv quarto shellcheck pdftotext pdftoppm rg git)
for tool in "${required[@]}"; do command -v "$tool" >/dev/null || { echo "Falta dependencia: $tool" >&2; exit 1; }; done
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

scripts/run-required-cases.sh
scripts/run-experiments.sh
scripts/render-report.sh

pdf=deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.pdf
html=deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.html
test -s "$pdf" && test -s "$html"
mkdir -p report/pdf-pages
pdftotext "$pdf" /tmp/error-control-lab-report.txt
for expected in \
  "Luis Fernando Mendoza Alvarez" "19644" "github.com/lfmendoza/error-control-lab" \
  "Descripción de la práctica" "Objetivos" "Arquitectura por capas" \
  "Diseño del formato de trama" "Fundamento de Hamming SECDED" \
  "Fundamento de CRC-32" "Metodología experimental" "Escenarios de prueba" \
  "Resultados" "Discusión" "Limitaciones" "Conclusiones" "Referencias"; do
  rg -Fq "$expected" /tmp/error-control-lab-report.txt || { echo "Texto ausente del PDF: $expected" >&2; exit 1; }
done
pdftoppm -png -r 110 "$pdf" report/pdf-pages/page >/dev/null 2>&1
page_count=$(find report/pdf-pages -maxdepth 1 -name 'page-*.png' | wc -l)
((page_count > 0))

mapfile -t scan_files < <(rg --files -g '!uv.lock' -g '!scripts/verify-lab.sh' -g '!report/evidence/**' -g '!report/data/**' -g '!deliverables/**' -g '!report/pdf-pages/**')
if rg -n '\b(TODO|FIXME|TBD)\b' "${scan_files[@]}"; then
  echo "Se encontraron placeholders" >&2
  exit 1
fi
if rg -n -i '/home/|\.local/|ChatGPT|OpenAI|Codex|prompt|agente generativo' "${scan_files[@]}"; then
  echo "Se encontraron placeholders, rutas locales o referencias prohibidas" >&2
  exit 1
fi
if rg -n -i '(api[_-]?key|secret|token|password)[[:space:]]*[:=][[:space:]]*.{8,}' "${scan_files[@]}"; then
  echo "Posible secreto detectado" >&2
  exit 1
fi
git diff --check
test -z "$(git diff --cached --name-only)"
for artifact in .venv build build-sanitize .cache .pytest_cache .ruff_cache report/pdf-pages; do
  git check-ignore -q "$artifact" || { echo "Artefacto no ignorado: $artifact" >&2; exit 1; }
done
printf 'Verificación completa: %s páginas PDF.\n' "$page_count"
