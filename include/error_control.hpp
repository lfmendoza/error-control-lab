#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace ecl {
using Bits = std::vector<int>;

Bits bytes_to_bits(std::string_view bytes);
std::string bits_to_bytes(const Bits& bits, std::size_t original_bits);
std::uint32_t crc32(std::string_view bytes);
Bits hamming_encode_block(const Bits& data);
Bits hamming_encode(const Bits& data, std::size_t block_data_bits);
std::vector<std::size_t> apply_noise(Bits& bits, std::string_view mode,
                                     const std::vector<std::size_t>& positions,
                                     double ber, std::uint64_t seed);
std::string bits_string(const Bits& bits);
std::string json_escape(std::string_view text);
}
