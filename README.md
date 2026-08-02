# Laboratorio 2 — detección y corrección de errores

Implementación interoperable de Hamming SECDED y CRC-32/ISO-HDLC para CC3067
Redes. El emisor usa C++23 y el receptor Python 3.13; ambos se comunican mediante
tramas JSON Lines, manualmente o por TCP.

## Inicio rápido

```bash
just bootstrap
just build
build/sender encode --algorithm hamming --text "Hola redes" --output /tmp/trama.jsonl
PYTHONPATH=src/python uv run python -m error_control.receiver verify --input /tmp/trama.jsonl
```

CRC y ruido reproducible:

```bash
build/sender encode --algorithm crc32 --bits 101101 --noise bernoulli --ber 0.01 --seed 19644
```

Para TCP, inicie el receptor y luego el emisor:

```bash
PYTHONPATH=src/python uv run python -m error_control.receiver listen --host 127.0.0.1 --port 9000
build/sender encode --algorithm hamming --text "TCP" --host 127.0.0.1 --port 9000
```

## Automatización

- `just test`: pruebas C++ y Python, incluidas integraciones.
- `just required-cases`: evidencia de tres mensajes y tres escenarios.
- `just experiments`: CSV, análisis de limitaciones y cinco gráficas.
- `just report`: reporte HTML y PDF.
- `just verify`: validación integral del entregable.

La especificación del protocolo y las responsabilidades por capa están en
[docs/architecture.md](docs/architecture.md). El proyecto se distribuye bajo MIT.
