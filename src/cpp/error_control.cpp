#include "error_control.hpp"

#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>

namespace ecl {
Bits bytes_to_bits(const std::string_view bytes) {
  Bits result;
  result.reserve(bytes.size() * 8U);
  for (const unsigned char byte : bytes) {
    for (int shift = 7; shift >= 0; --shift) result.push_back((byte >> shift) & 1U);
  }
  return result;
}

std::string bits_to_bytes(const Bits& bits, const std::size_t original_bits) {
  if (original_bits > bits.size() || original_bits % 8U != 0U) throw std::invalid_argument("longitud de bits inválida para bytes");
  std::string output(original_bits / 8U, '\0');
  for (std::size_t i = 0; i < original_bits; ++i) {
    if (bits[i] != 0 && bits[i] != 1) throw std::invalid_argument("bit inválido");
    output[i / 8U] = static_cast<char>(static_cast<unsigned char>(output[i / 8U]) | static_cast<unsigned char>(bits[i] << (7U - i % 8U)));
  }
  return output;
}

std::uint32_t crc32(const std::string_view bytes) {
  std::uint32_t crc = 0xFFFFFFFFU;
  for (const unsigned char byte : bytes) {
    crc ^= byte;
    for (int bit = 0; bit < 8; ++bit) crc = (crc & 1U) ? (crc >> 1U) ^ 0xEDB88320U : crc >> 1U;
  }
  return crc ^ 0xFFFFFFFFU;
}

Bits hamming_encode_block(const Bits& data) {
  std::size_t r = 0;
  while ((std::size_t{1} << r) < data.size() + r + 1U) ++r;
  const std::size_t n = data.size() + r;
  Bits code(n + 1U, 0); // índice 0 no usado; posiciones Hamming son 1..n
  std::size_t source = 0;
  for (std::size_t pos = 1; pos <= n; ++pos) {
    if ((pos & (pos - 1U)) != 0U) code[pos] = data[source++];
  }
  for (std::size_t parity = 1; parity <= n; parity <<= 1U) {
    int value = 0;
    for (std::size_t pos = 1; pos <= n; ++pos) if ((pos & parity) != 0U) value ^= code[pos];
    code[parity] = value;
  }
  Bits result(code.begin() + 1, code.end());
  int global = 0;
  for (const int bit : result) global ^= bit;
  result.push_back(global);
  return result;
}

Bits hamming_encode(const Bits& data, const std::size_t block_data_bits) {
  if (block_data_bits == 0U) throw std::invalid_argument("block_data_bits debe ser positivo");
  Bits output;
  for (std::size_t offset = 0; offset < data.size(); offset += block_data_bits) {
    Bits block(block_data_bits, 0);
    const std::size_t count = std::min(block_data_bits, data.size() - offset);
    std::copy_n(data.begin() + static_cast<std::ptrdiff_t>(offset), static_cast<std::ptrdiff_t>(count), block.begin());
    const Bits encoded = hamming_encode_block(block);
    output.insert(output.end(), encoded.begin(), encoded.end());
  }
  return output;
}

std::vector<std::size_t> apply_noise(Bits& bits, const std::string_view mode,
                                     const std::vector<std::size_t>& positions,
                                     const double ber, const std::uint64_t seed) {
  std::vector<std::size_t> flips;
  if (mode == "none") return flips;
  if (mode == "positions") flips = positions;
  else if (mode == "one" || mode == "multiple") {
    if (bits.empty()) throw std::invalid_argument("no se puede aplicar ruido a una trama vacía");
    std::mt19937_64 rng(seed);
    std::uniform_int_distribution<std::size_t> pick(0, bits.size() - 1U);
    const std::size_t wanted = mode == "one" ? 1U : std::min<std::size_t>(3U, bits.size());
    while (flips.size() < wanted) {
      const auto candidate = pick(rng);
      if (std::find(flips.begin(), flips.end(), candidate) == flips.end()) flips.push_back(candidate);
    }
  } else if (mode == "bernoulli") {
    if (ber < 0.0 || ber > 1.0) throw std::invalid_argument("BER debe estar entre 0 y 1");
    std::mt19937_64 rng(seed);
    std::bernoulli_distribution flip(ber);
    for (std::size_t i = 0; i < bits.size(); ++i) if (flip(rng)) flips.push_back(i);
  } else throw std::invalid_argument("modo de ruido desconocido");
  for (const auto position : flips) {
    if (position >= bits.size()) throw std::invalid_argument("posición de flip fuera de rango");
    bits[position] ^= 1;
  }
  return flips;
}

std::string bits_string(const Bits& bits) {
  std::string value;
  value.reserve(bits.size());
  for (const int bit : bits) value.push_back(bit == 0 ? '0' : '1');
  return value;
}

std::string json_escape(const std::string_view text) {
  std::string out;
  for (const unsigned char c : text) {
    if (c == '"' || c == '\\') { out.push_back('\\'); out.push_back(static_cast<char>(c)); }
    else if (c >= 0x20U) out.push_back(static_cast<char>(c));
    else { constexpr char hex[] = "0123456789abcdef"; out += "\\u00"; out.push_back(hex[c >> 4U]); out.push_back(hex[c & 0xFU]); }
  }
  return out;
}
}
