#include "error_control.hpp"
#include <cassert>
#include <iostream>

int main() {
  const auto bits = ecl::bytes_to_bits("A");
  assert(ecl::bits_string(bits) == "01000001");
  assert(ecl::bits_to_bytes(bits, 8) == "A");
  assert(ecl::crc32("123456789") == 0xCBF43926U);
  const ecl::Bits block{1, 0, 1, 1, 0, 0, 1, 0};
  assert(ecl::hamming_encode_block(block).size() == 13);
  auto noisy = ecl::hamming_encode_block(block);
  const auto flips = ecl::apply_noise(noisy, "positions", {0, 12}, 0.0, 1);
  assert(flips.size() == 2 && noisy[0] != ecl::hamming_encode_block(block)[0]);
  std::cout << "Pruebas C++ correctas\n";
}
