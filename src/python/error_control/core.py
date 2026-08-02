"""Servicios puros de presentación y enlace; no dependen de CLI ni sockets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def bytes_to_bits(data: bytes) -> list[int]:
    return [(byte >> shift) & 1 for byte in data for shift in range(7, -1, -1)]


def bits_to_bytes(bits: list[int], original_bits: int) -> bytes:
    if original_bits < 0 or original_bits > len(bits) or original_bits % 8:
        raise ValueError("longitud original inválida para convertir a bytes")
    if any(bit not in (0, 1) for bit in bits):
        raise ValueError("la secuencia contiene bits inválidos")
    output = bytearray(original_bits // 8)
    for index, bit in enumerate(bits[:original_bits]):
        output[index // 8] |= bit << (7 - index % 8)
    return bytes(output)


def crc32(data: bytes) -> int:
    """CRC-32/ISO-HDLC reflejado, sin delegar el cálculo a una biblioteca."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xEDB88320 if crc & 1 else crc >> 1
    return crc ^ 0xFFFFFFFF


def required_parity_bits(data_bits: int) -> int:
    if data_bits <= 0:
        raise ValueError("el bloque debe contener al menos un bit de datos")
    parity = 0
    while 2**parity < data_bits + parity + 1:
        parity += 1
    return parity


def hamming_encode_block(data: list[int]) -> list[int]:
    parity_count = required_parity_bits(len(data))
    length = len(data) + parity_count
    code = [0] * (length + 1)
    source = iter(data)
    for position in range(1, length + 1):
        if position & (position - 1):
            code[position] = next(source)
    for parity in (1 << exponent for exponent in range(parity_count)):
        code[parity] = sum(code[pos] for pos in range(1, length + 1) if pos & parity) % 2
    body = code[1:]
    return body + [sum(body) % 2]


@dataclass
class BlockResult:
    data: list[int]
    status: str
    corrected_position: int | None
    syndrome: int


def hamming_decode_block(received: list[int], data_bits: int) -> BlockResult:
    parity_count = required_parity_bits(data_bits)
    body_length = data_bits + parity_count
    if len(received) != body_length + 1 or any(bit not in (0, 1) for bit in received):
        raise ValueError("bloque SECDED inválido")
    body = [0, *received[:body_length]]
    syndrome = 0
    for exponent in range(parity_count):
        parity = 1 << exponent
        if sum(body[pos] for pos in range(1, body_length + 1) if pos & parity) % 2:
            syndrome |= parity
    global_mismatch = sum(received) % 2 == 1
    corrected_position: int | None = None
    if syndrome == 0 and not global_mismatch:
        status = "ok"
    elif syndrome != 0 and global_mismatch:
        if syndrome > body_length:
            status = "detected_uncorrectable_syndrome"
        else:
            body[syndrome] ^= 1
            corrected_position = syndrome - 1  # índice cero dentro del cuerpo transmitido
            status = "corrected_single"
    elif syndrome == 0 and global_mismatch:
        corrected_position = body_length
        status = "corrected_global_parity"
    else:
        status = "detected_double"
    data = [body[pos] for pos in range(1, body_length + 1) if pos & (pos - 1)]
    return BlockResult(data, status, corrected_position, syndrome)


def validate_frame(frame: Any) -> dict[str, Any]:
    if not isinstance(frame, dict):
        raise ValueError("la trama JSON debe ser un objeto")
    required = {"version", "algorithm", "encoding", "original_bits", "encoded_bits"}
    missing = sorted(required - frame.keys())
    if missing:
        raise ValueError(f"faltan campos requeridos: {', '.join(missing)}")
    if frame["version"] != 1:
        raise ValueError("versión de trama no soportada")
    if frame["algorithm"] not in {"hamming", "crc32"}:
        raise ValueError("algoritmo no soportado")
    if frame["encoding"] not in {"text", "bits"}:
        raise ValueError("codificación no soportada")
    if not isinstance(frame["original_bits"], int) or frame["original_bits"] <= 0:
        raise ValueError("original_bits debe ser un entero positivo")
    if not isinstance(frame["encoded_bits"], str) or not frame["encoded_bits"]:
        raise ValueError("encoded_bits debe ser una cadena binaria no vacía")
    if set(frame["encoded_bits"]) - {"0", "1"}:
        raise ValueError("encoded_bits contiene caracteres no binarios")
    if frame["encoding"] == "text" and frame["original_bits"] % 8:
        raise ValueError("el texto debe tener longitud múltiplo de ocho bits")
    return frame


def decode_frame(frame: dict[str, Any]) -> dict[str, Any]:
    frame = validate_frame(frame)
    encoded = [int(bit) for bit in frame["encoded_bits"]]
    original_bits = frame["original_bits"]
    statuses: list[str] = []
    corrected: list[int] = []
    syndromes: list[int] = []
    if frame["algorithm"] == "hamming":
        block_data_bits = frame.get("block_data_bits")
        if not isinstance(block_data_bits, int) or block_data_bits <= 0 or block_data_bits > 4096:
            raise ValueError("block_data_bits inválido")
        block_size = block_data_bits + required_parity_bits(block_data_bits) + 1
        expected_blocks = (original_bits + block_data_bits - 1) // block_data_bits
        if len(encoded) != expected_blocks * block_size:
            raise ValueError("longitud SECDED inconsistente con los metadatos")
        data: list[int] = []
        for block_index in range(expected_blocks):
            start = block_index * block_size
            result = hamming_decode_block(encoded[start : start + block_size], block_data_bits)
            data.extend(result.data)
            statuses.append(result.status)
            syndromes.append(result.syndrome)
            if result.corrected_position is not None:
                corrected.append(start + result.corrected_position)
        detected = any(status != "ok" for status in statuses)
        uncorrectable = any(status.startswith("detected_") for status in statuses)
        accepted = not uncorrectable
        payload = data[:original_bits] if accepted else []
    else:
        if len(encoded) != original_bits + 32:
            raise ValueError("longitud CRC inconsistente con los metadatos")
        payload = encoded[:original_bits]
        padded = [*payload]
        padded.extend([0] * (-len(padded) % 8))
        supplied = int("".join(map(str, encoded[original_bits:])), 2)
        calculated = crc32(bits_to_bytes(padded, len(padded)))
        detected = supplied != calculated
        uncorrectable = detected
        accepted = not detected
        statuses = ["ok" if accepted else "detected_crc"]
    response: dict[str, Any] = {
        "accepted": accepted,
        "algorithm": frame["algorithm"],
        "status": "accepted"
        if accepted and not detected
        else "corrected"
        if accepted
        else "rejected",
        "detected_error": detected,
        "uncorrectable": uncorrectable,
        "block_statuses": statuses,
        "corrected_positions": corrected,
        "original_bits": original_bits,
    }
    if syndromes:
        response["syndromes"] = syndromes
    if accepted:
        response["recovered_bits"] = "".join(map(str, payload))
        if frame["encoding"] == "text":
            try:
                response["message"] = bits_to_bytes(payload, original_bits).decode("utf-8")
            except UnicodeDecodeError:
                response["accepted"] = False
                response["status"] = "rejected_presentation"
                response["presentation_error"] = "los datos recuperados no forman UTF-8 válido"
    return response
