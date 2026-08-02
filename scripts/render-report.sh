#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p deliverables
export XDG_CACHE_HOME="$PWD/.cache/quarto" XDG_DATA_HOME="$PWD/.cache/quarto-data"
export TEXMFVAR="$PWD/.cache/texlive/var" TEXMFCONFIG="$PWD/.cache/texlive/config"
mkdir -p "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$TEXMFVAR" "$TEXMFCONFIG"
quarto render report/report.qmd
install -m 0644 report/Laboratorio_2_Redes_Luis_Fernando_Mendoza.html \
  deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.html
install -m 0644 report/Laboratorio_2_Redes_Luis_Fernando_Mendoza.pdf \
  deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.pdf
test -s deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.html
test -s deliverables/Laboratorio_2_Redes_Luis_Fernando_Mendoza.pdf
