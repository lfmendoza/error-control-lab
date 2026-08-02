import pytest
from error_control.core import (
    bits_to_bytes,
    bytes_to_bits,
    crc32,
    hamming_decode_block,
    hamming_encode_block,
    required_parity_bits,
)


def test_bit_byte_roundtrip():
    data = "Redes ✓".encode()
    assert bits_to_bytes(bytes_to_bits(data), len(data) * 8) == data


def test_crc_standard_vector():
    assert crc32(b"123456789") == 0xCBF43926


def test_hamming_parity_and_syndrome():
    data = [1, 0, 1, 1, 0, 0, 1, 0]
    encoded = hamming_encode_block(data)
    assert required_parity_bits(8) == 4
    assert hamming_decode_block(encoded, 8).status == "ok"
    encoded[5] ^= 1
    result = hamming_decode_block(encoded, 8)
    assert result.status == "corrected_single"
    assert result.syndrome == 6
    assert result.data == data


def test_global_parity_error_and_double_error():
    encoded = hamming_encode_block([1] * 8)
    encoded[-1] ^= 1
    assert hamming_decode_block(encoded, 8).status == "corrected_global_parity"
    encoded = hamming_encode_block([1] * 8)
    encoded[0] ^= 1
    encoded[1] ^= 1
    assert hamming_decode_block(encoded, 8).status == "detected_double"


def test_invalid_conversion():
    with pytest.raises(ValueError):
        bits_to_bytes([1, 0], 2)
