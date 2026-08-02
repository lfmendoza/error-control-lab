"""Ejecuta transmisiones reales y deriva CSV, figuras y evidencia."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from error_control.core import decode_frame

ROOT = Path(__file__).parents[1]
SENDER = ROOT / "build" / "sender"
DATA = ROOT / "report" / "data"
FIGURES = ROOT / "report" / "figures"
EVIDENCE = ROOT / "report" / "evidence"
EVIDENCE_FIGURES = FIGURES / "evidence"


def encode(
    algorithm: str,
    message: str,
    noise: str,
    seed: int,
    ber: float = 0,
    positions: list[int] | None = None,
) -> dict:
    command = [
        SENDER,
        "encode",
        "--algorithm",
        algorithm,
        "--text",
        message,
        "--noise",
        noise,
        "--ber",
        str(ber),
        "--seed",
        str(seed),
        "--machine",
    ]
    if positions:
        command[command.index("--machine") : command.index("--machine")] = [
            "--positions",
            ",".join(str(position) for position in positions),
        ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_trials() -> list[dict]:
    rows = []
    for algorithm, length, ber, trial in itertools.product(
        ("hamming", "crc32"), (1, 8, 32, 128, 512), (0, 0.001, 0.01, 0.05), range(12)
    ):
        message = "R" * length
        frame = encode(algorithm, message, "bernoulli", 19644 + trial, ber)
        start = time.perf_counter_ns()
        result = decode_frame(frame)
        decode_ns = time.perf_counter_ns() - start
        flipped = len(frame["noise"]["flipped_positions"])
        correct = result.get("message") == message
        actual_error = flipped > 0
        rows.append(
            {
                "algorithm": algorithm,
                "length_bytes": length,
                "ber": ber,
                "trial": trial,
                "errors": flipped,
                "corrupted": int(actual_error),
                "encoded_bits": len(frame["encoded_bits"]),
                "overhead_pct": (len(frame["encoded_bits"]) - length * 8) / (length * 8) * 100,
                "detected": int(result["detected_error"]),
                "corrected": int(result["status"] == "corrected"),
                "false_negative": int(
                    actual_error and not result["detected_error"] and not correct
                ),
                "recovered_correctly": int(correct),
                "encode_ns": frame["metrics"]["encode_ns"],
                "decode_ns": decode_ns,
            }
        )
    return rows


def write_csv(rows: list[dict]) -> None:
    with (DATA / "experiments.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def line_plot(rows: list[dict], field: str, title: str, ylabel: str, filename: str) -> None:
    plt.figure(figsize=(7.2, 4.3))
    grouped: dict[tuple[str, float], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row["algorithm"], row["ber"])].append(row[field])
    for algorithm in ("hamming", "crc32"):
        x = sorted({key[1] for key in grouped if key[0] == algorithm})
        y = [sum(grouped[(algorithm, point)]) / len(grouped[(algorithm, point)]) for point in x]
        plt.plot(x, y, marker="o", label=algorithm.upper())
    plt.title(title)
    plt.xlabel("BER configurada")
    plt.ylabel(ylabel)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / filename, dpi=180)
    plt.close()


def make_figures(rows: list[dict]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.figure(figsize=(7.2, 4.3))
    for algorithm in ("hamming", "crc32"):
        selected = [
            row
            for row in rows
            if row["algorithm"] == algorithm and row["ber"] == 0 and row["trial"] == 0
        ]
        plt.plot(
            [row["length_bytes"] for row in selected],
            [row["overhead_pct"] for row in selected],
            marker="o",
            label=algorithm.upper(),
        )
    plt.xscale("log", base=2)
    lengths = [1, 8, 32, 128, 512]
    plt.xticks(lengths, [str(length) for length in lengths])
    plt.xlabel("Longitud (bytes)")
    plt.ylabel("Overhead (%)")
    plt.title("Redundancia por longitud (eje X en escala log2)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "overhead.png", dpi=180)
    plt.close()
    line_plot(
        [row for row in rows if row["corrupted"]],
        "detected",
        "Detección condicionada a corrupción",
        "P(detectado | transmisión alterada)",
        "detection_vs_ber.png",
    )
    line_plot(
        rows,
        "recovered_correctly",
        "Recuperación correcta",
        "Proporción recuperada",
        "recovery_vs_ber.png",
    )
    plt.figure(figsize=(7.2, 4.3))
    for algorithm in ("hamming", "crc32"):
        selected = [row for row in rows if row["algorithm"] == algorithm and row["ber"] == 0]
        grouped = defaultdict(list)
        for row in selected:
            grouped[row["length_bytes"]].append(row["encode_ns"] + row["decode_ns"])
        x = sorted(grouped)
        y = [sum(grouped[value]) / len(grouped[value]) / 1000 for value in x]
        plt.plot(x, y, marker="o", label=algorithm.upper())
    plt.xscale("log", base=2)
    plt.yscale("log")
    plt.xlabel("Longitud (bytes)")
    plt.ylabel("Tiempo total (µs)")
    plt.title("Costo de procesamiento")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "processing_time.png", dpi=180)
    plt.close()
    categories = ("cero", "uno", "múltiples")
    values = {algorithm: [] for algorithm in ("hamming", "crc32")}
    for algorithm in values:
        for category in categories:
            candidates = [
                row
                for row in rows
                if row["algorithm"] == algorithm
                and (
                    (category == "cero" and row["errors"] == 0)
                    or (category == "uno" and row["errors"] == 1)
                    or (category == "múltiples" and row["errors"] >= 2)
                )
            ]
            values[algorithm].append(
                sum(row["recovered_correctly"] for row in candidates) / len(candidates)
                if candidates
                else 0
            )
    x = range(3)
    width = 0.36
    plt.figure(figsize=(7.2, 4.3))
    plt.bar([i - width / 2 for i in x], values["hamming"], width, label="HAMMING")
    plt.bar([i + width / 2 for i in x], values["crc32"], width, label="CRC32")
    plt.xticks(list(x), categories)
    plt.ylabel("Proporción recuperada")
    plt.title("Resultado según cantidad de errores")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "error_categories.png", dpi=180)
    plt.close()


def find_limitations() -> dict:
    base_hamming = encode("hamming", "A", "none", 1)
    original_hamming = base_hamming["encoded_bits"]
    hamming_case = None
    for positions in itertools.combinations(range(len(original_hamming)), 3):
        changed = list(original_hamming)
        for position in positions:
            changed[position] = "1" if changed[position] == "0" else "0"
        candidate = {**base_hamming, "encoded_bits": "".join(changed)}
        try:
            result = decode_frame(candidate)
        except ValueError:
            continue
        if result["accepted"] and result.get("message") != "A":
            hamming_case = {"positions": positions, "result": result}
            break
    base_crc = encode("crc32", "A", "none", 1)
    original_crc = base_crc["encoded_bits"]
    crc_case = None
    checked = 0
    for count in (1, 2, 3, 4):
        for positions in itertools.combinations(range(len(original_crc)), count):
            checked += 1
            changed = list(original_crc)
            for position in positions:
                changed[position] = "1" if changed[position] == "0" else "0"
            result = decode_frame({**base_crc, "encoded_bits": "".join(changed)})
            if result["accepted"] and result.get("message") != "A":
                crc_case = {"positions": positions, "result": result}
                break
        if crc_case:
            break
    limitations = {
        "hamming_three_bit_miscorrection": hamming_case,
        "crc_search": {"patterns_checked": checked, "undetected": crc_case},
    }
    (EVIDENCE / "limitations.json").write_text(
        json.dumps(limitations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return limitations


def render_evidence_card(
    filename: str,
    title: str,
    message: str,
    algorithm: str,
    positions: list[int],
    result: dict,
    frame: dict,
) -> None:
    """Genera una tarjeta visual usando exclusivamente una ejecución real."""
    EVIDENCE_FIGURES.mkdir(parents=True, exist_ok=True)
    observed = result.get("message", result.get("status", "rechazada"))
    flips = ", ".join(str(position) for position in positions) if positions else "ninguno"
    lines = [
        title,
        "Evidencia reproducible de ejecución real",
        f"Mensaje utilizado: {message!r}",
        f"Algoritmo: {algorithm.upper()}",
        f"Bits alterados: {flips}",
        f"Resultado observado: {observed!r}",
        f"Estado: {result['status']} | detectado={result['detected_error']}",
        f"Trama: {len(frame['encoded_bits'])} bits | semilla={frame['noise']['seed']}",
    ]
    figure, axis = plt.subplots(figsize=(10, 3.6))
    axis.axis("off")
    axis.text(0.02, 0.88, lines[0], fontsize=17, fontweight="bold", va="top")
    axis.text(
        0.02,
        0.76,
        "\n".join(lines[1:]),
        fontsize=12,
        family="DejaVu Sans Mono",
        va="top",
        linespacing=1.6,
    )
    figure.tight_layout()
    figure.savefig(EVIDENCE_FIGURES / filename, dpi=180, bbox_inches="tight")
    plt.close(figure)


def generate_evidence() -> None:
    cases = [
        ("01_no_errors.png", "Figura E1. Trama sin errores", "A", "hamming", "none", []),
        (
            "02_single_error.png",
            "Figura E2. Corrección de un error",
            "A",
            "hamming",
            "positions",
            [0],
        ),
        (
            "03_multiple_errors.png",
            "Figura E3. Múltiples errores detectados",
            "A",
            "crc32",
            "positions",
            [0, 1],
        ),
        (
            "04_secded_limitation.png",
            "Figura E4. Límite de SECDED",
            "A",
            "hamming",
            "positions",
            [0, 1, 3],
        ),
    ]
    for index, (filename, title, message, algorithm, noise, positions) in enumerate(cases, 1):
        frame = encode(algorithm, message, noise, 19644 + index, positions=positions)
        result = decode_frame(frame)
        render_evidence_card(filename, title, message, algorithm, positions, result, frame)


def main(output_root: Path = ROOT) -> None:
    global DATA, FIGURES, EVIDENCE, EVIDENCE_FIGURES
    DATA = output_root / "data"
    FIGURES = output_root / "figures"
    EVIDENCE = output_root / "evidence"
    EVIDENCE_FIGURES = FIGURES / "evidence"
    DATA.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = run_trials()
    write_csv(rows)
    make_figures(rows)
    generate_evidence()
    limitations = find_limitations()
    aggregate = {}
    for algorithm in ("hamming", "crc32"):
        selected = [row for row in rows if row["algorithm"] == algorithm]
        corrupted = [row for row in selected if row["corrupted"]]
        aggregate[algorithm] = {
            "total_transmissions": len(selected),
            "altered_transmissions": len(corrupted),
            "conditional_detection_rate": sum(row["detected"] for row in corrupted)
            / len(corrupted),
            "recovery_rate": sum(row["recovered_correctly"] for row in selected) / len(selected),
            "conditional_recovery_rate": sum(row["recovered_correctly"] for row in corrupted)
            / len(corrupted),
            "conditional_false_negative_rate": sum(row["false_negative"] for row in corrupted)
            / len(corrupted),
            "mean_encode_ns": sum(row["encode_ns"] for row in selected) / len(selected),
            "mean_decode_ns": sum(row["decode_ns"] for row in selected) / len(selected),
        }
    summary = {
        "trials": len(rows),
        "total_transmissions": len(rows),
        "altered_transmissions": sum(row["corrupted"] for row in rows),
        "false_negatives": sum(row["false_negative"] for row in rows),
        "aggregate": aggregate,
        "limitations": limitations,
    }
    (DATA / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"Se ejecutaron **{len(rows)} transmisiones reales** con semillas deterministas.",
        "",
        "| Algoritmo | Total | Alteradas | Detección | Corr. global | "
        "Corr. alteradas | FN alteradas | Codif. (µs) | Decodif. (µs) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for algorithm in ("hamming", "crc32"):
        item = aggregate[algorithm]
        lines.append(
            f"| {algorithm.upper()} | {item['total_transmissions']} | "
            f"{item['altered_transmissions']} | "
            f"{item['conditional_detection_rate']:.3f} | {item['recovery_rate']:.3f} | "
            f"{item['conditional_recovery_rate']:.3f} | "
            f"{item['conditional_false_negative_rate']:.3f} | "
            f"{item['mean_encode_ns'] / 1000:.2f} | {item['mean_decode_ns'] / 1000:.2f} |"
        )
    lines.extend(
        [
            "",
            "Falsos negativos observados en la matriz Bernoulli: "
            f"**{summary['false_negatives']}**.",
        ]
    )
    (DATA / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Ejecutar y publicar experimentos reproducibles")
    cli.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "report",
        help="directorio que contiene data/, figures/ y evidence/",
    )
    main(cli.parse_args().output_root)
