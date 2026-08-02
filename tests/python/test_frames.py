import json

import pytest
from error_control.core import bytes_to_bits, crc32, decode_frame, hamming_encode_block
from error_control.receiver import parse_line


def crc_frame(text: str) -> dict:
    payload = bytes_to_bits(text.encode())
    checksum = crc32(text.encode())
    suffix = f"{checksum:032b}"
    return {
        "version": 1,
        "algorithm": "crc32",
        "encoding": "text",
        "original_bits": len(payload),
        "block_data_bits": 8,
        "encoded_bits": "".join(map(str, payload)) + suffix,
    }


def test_crc_accepts_and_rejects():
    frame = crc_frame("hola")
    assert decode_frame(frame)["message"] == "hola"
    frame["encoded_bits"] = ("1" if frame["encoded_bits"][0] == "0" else "0") + frame[
        "encoded_bits"
    ][1:]
    assert not decode_frame(frame)["accepted"]


def test_hamming_multiblock():
    payload = bytes_to_bits(b"abc")
    encoded = sum((hamming_encode_block(payload[i : i + 8]) for i in range(0, len(payload), 8)), [])
    frame = {
        "version": 1,
        "algorithm": "hamming",
        "encoding": "text",
        "original_bits": 24,
        "block_data_bits": 8,
        "encoded_bits": "".join(map(str, encoded)),
    }
    frame["encoded_bits"] = (
        frame["encoded_bits"][:14]
        + ("1" if frame["encoded_bits"][14] == "0" else "0")
        + frame["encoded_bits"][15:]
    )
    result = decode_frame(frame)
    assert result["message"] == "abc" and result["status"] == "corrected"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "{",
        "[]",
        '{"version":1}',
        '{"version":2,"algorithm":"crc32","encoding":"bits","original_bits":1,"encoded_bits":"0"}',
    ],
)
def test_invalid_frames(bad):
    with pytest.raises(ValueError):
        parse_line(bad)


def test_json_never_executes_content():
    frame = crc_frame("safe")
    frame["extra"] = "__import__('os').system('false')"
    assert parse_line(json.dumps(frame))["message"] == "safe"
