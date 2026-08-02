import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SENDER = ROOT / "build" / "sender"
PYTHONPATH = str(ROOT / "src" / "python")


def sender(*arguments: str) -> dict:
    result = subprocess.run(
        [SENDER, "encode", *arguments, "--machine"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def receiver(frame: dict) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONPATH": PYTHONPATH}
    return subprocess.run(
        [sys.executable, "-m", "error_control.receiver", "verify", "--machine"],
        input=json.dumps(frame) + "\n",
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


@pytest.mark.parametrize("message", ["A", "Laboratorio", "Redes confiables sobre canal ruidoso ✓"])
@pytest.mark.parametrize("algorithm", ["hamming", "crc32"])
def test_cpp_to_python_three_lengths(message: str, algorithm: str):
    result = receiver(sender("--algorithm", algorithm, "--text", message))
    assert result.returncode == 0
    assert json.loads(result.stdout)["message"] == message


@pytest.mark.parametrize("algorithm", ["hamming", "crc32"])
def test_one_and_multiple_errors(algorithm: str):
    one = receiver(
        sender(
            "--algorithm",
            algorithm,
            "--text",
            "integración",
            "--noise",
            "positions",
            "--positions",
            "0",
        )
    )
    assert json.loads(one.stdout)["detected_error"]
    assert one.returncode == (0 if algorithm == "hamming" else 3)
    multiple = receiver(
        sender(
            "--algorithm",
            algorithm,
            "--text",
            "integración",
            "--noise",
            "positions",
            "--positions",
            "0,1",
        )
    )
    assert multiple.returncode == 3


def test_binary_input_and_bad_sender_input():
    result = receiver(sender("--algorithm", "hamming", "--bits", "101101"))
    assert json.loads(result.stdout)["recovered_bits"] == "101101"
    bad = subprocess.run(
        [SENDER, "encode", "--bits", "102"], capture_output=True, text=True, check=False
    )
    assert bad.returncode == 2 and "solo acepta" in bad.stderr


def test_tcp_end_to_end():
    try:
        probe_socket = socket.socket()
    except PermissionError:
        pytest.skip("el sandbox no permite sockets locales")
    with probe_socket as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = {**os.environ, "PYTHONPATH": PYTHONPATH}
    listener = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "error_control.receiver",
            "listen",
            "--port",
            str(port),
            "--machine",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    time.sleep(0.15)
    sent = subprocess.run(
        [SENDER, "encode", "--algorithm", "hamming", "--text", "TCP ✓", "--port", str(port)],
        capture_output=True,
        text=True,
        check=False,
    )
    output, errors = listener.communicate(timeout=5)
    assert sent.returncode == 0, sent.stderr
    assert listener.returncode == 0, errors
    assert json.loads(output)["message"] == "TCP ✓"
