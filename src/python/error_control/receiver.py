"""CLI y transporte del receptor."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from typing import TextIO

from .core import decode_frame


def parse_line(line: str) -> dict:
    if len(line.encode()) > 16 * 1024 * 1024:
        raise ValueError("trama demasiado grande")
    try:
        frame = json.loads(line)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON inválido: {error.msg}") from error
    return decode_frame(frame)


def process(source: TextIO, machine: bool) -> int:
    line = source.readline()
    if not line:
        raise ValueError("entrada vacía o trama truncada")
    result = parse_line(line)
    if machine:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    elif result["accepted"]:
        detail = result.get("message", result["recovered_bits"])
        print(f"{result['status'].upper()}: {detail}")
        if result["corrected_positions"]:
            print("Posiciones corregidas:", result["corrected_positions"])
    else:
        print("RECHAZADA: se detectó un error no corregible", file=sys.stderr)
    return 0 if result["accepted"] else 3


def receive_tcp(host: str, port: int, timeout: float, output: Path | None, machine: bool) -> int:
    with socket.create_server((host, port), reuse_port=False) as server:
        server.settimeout(timeout)
        actual_port = server.getsockname()[1]
        print(f"Escuchando en {host}:{actual_port}", file=sys.stderr, flush=True)
        connection, _ = server.accept()
        with connection:
            connection.settimeout(timeout)
            chunks = bytearray()
            while b"\n" not in chunks:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > 16 * 1024 * 1024:
                    raise ValueError("trama TCP demasiado grande")
        line, separator, remainder = bytes(chunks).partition(b"\n")
        if not separator or remainder:
            raise ValueError("transporte requiere exactamente una trama JSONL delimitada")
        text = line.decode("utf-8")
        if output:
            output.write_text(text + "\n", encoding="utf-8")
        result = parse_line(text)
        print(
            json.dumps(result, ensure_ascii=False)
            if machine
            else result.get("message", result["status"])
        )
        return 0 if result["accepted"] else 3


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Verifica/corrige tramas JSONL Hamming SECDED o CRC-32"
    )
    sub = cli.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify", help="leer una trama desde archivo o stdin")
    verify.add_argument("--input", type=Path, help="archivo JSONL (stdin si se omite)")
    verify.add_argument("--machine", action="store_true", help="respuesta JSON automatizable")
    listen = sub.add_parser("listen", help="recibir una trama por TCP")
    listen.add_argument("--host", default="127.0.0.1")
    listen.add_argument("--port", type=int, default=9000)
    listen.add_argument("--timeout", type=float, default=5.0)
    listen.add_argument("--output", type=Path, help="guardar trama recibida")
    listen.add_argument("--machine", action="store_true")
    return cli


def main() -> int:
    args = parser().parse_args()
    started = time.perf_counter_ns()
    try:
        if args.command == "listen":
            if not 0 <= args.port <= 65535 or args.timeout <= 0:
                raise ValueError("puerto o timeout inválido")
            return receive_tcp(args.host, args.port, args.timeout, args.output, args.machine)
        if args.input:
            with args.input.open(encoding="utf-8") as source:
                code = process(source, args.machine)
        else:
            code = process(sys.stdin, args.machine)
        if not args.machine:
            print(f"Decodificación: {time.perf_counter_ns() - started} ns", file=sys.stderr)
        return code
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
