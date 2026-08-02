#include "error_control.hpp"

#include <arpa/inet.h>
#include <chrono>
#include <fstream>
#include <iostream>
#include <netdb.h>
#include <sstream>
#include <stdexcept>
#include <sys/socket.h>
#include <unistd.h>

namespace {
struct Options {
  std::string algorithm = "hamming", input, input_kind = "text", output, noise = "none", host = "127.0.0.1";
  std::vector<std::size_t> positions;
  double ber = 0.0;
  std::uint64_t seed = 1;
  int port = 0;
  bool machine = false;
};

void help() {
  std::cout << "Uso: sender encode --algorithm hamming|crc32 --text TEXTO|--bits BITS [opciones]\n"
               "Opciones: --output ARCHIVO --noise none|one|multiple|bernoulli|positions\n"
               "          --positions 0,2 --ber 0.01 --seed N --host HOST --port PUERTO --machine\n";
}

std::vector<std::size_t> parse_positions(const std::string& value) {
  std::vector<std::size_t> result; std::stringstream stream(value); std::string token;
  while (std::getline(stream, token, ',')) { if (token.empty()) throw std::invalid_argument("lista de posiciones inválida"); result.push_back(std::stoull(token)); }
  return result;
}

Options parse(const int argc, char** argv) {
  if (argc < 2 || std::string_view(argv[1]) == "--help") { help(); std::exit(argc < 2 ? 2 : 0); }
  if (std::string_view(argv[1]) != "encode") throw std::invalid_argument("comando esperado: encode");
  Options o;
  for (int i = 2; i < argc; ++i) {
    const std::string key = argv[i];
    if (key == "--machine") { o.machine = true; continue; }
    if (i + 1 >= argc) throw std::invalid_argument("falta valor para " + key);
    const std::string value = argv[++i];
    if (key == "--algorithm") o.algorithm = value;
    else if (key == "--text") { o.input = value; o.input_kind = "text"; }
    else if (key == "--bits") { o.input = value; o.input_kind = "bits"; }
    else if (key == "--output") o.output = value;
    else if (key == "--noise") o.noise = value;
    else if (key == "--positions") o.positions = parse_positions(value);
    else if (key == "--ber") o.ber = std::stod(value);
    else if (key == "--seed") o.seed = std::stoull(value);
    else if (key == "--host") o.host = value;
    else if (key == "--port") o.port = std::stoi(value);
    else throw std::invalid_argument("opción desconocida: " + key);
  }
  if (o.input.empty()) throw std::invalid_argument("se requiere --text o --bits con contenido");
  if (o.algorithm != "hamming" && o.algorithm != "crc32") throw std::invalid_argument("algoritmo debe ser hamming o crc32");
  if (o.port < 0 || o.port > 65535) throw std::invalid_argument("puerto inválido");
  return o;
}

void send_tcp(const std::string& host, const int port, const std::string& line) {
  addrinfo hints{}; hints.ai_family = AF_UNSPEC; hints.ai_socktype = SOCK_STREAM;
  addrinfo* addresses = nullptr;
  if (getaddrinfo(host.c_str(), std::to_string(port).c_str(), &hints, &addresses) != 0) throw std::runtime_error("no se pudo resolver el host");
  int fd = -1;
  for (auto* address = addresses; address; address = address->ai_next) {
    fd = socket(address->ai_family, address->ai_socktype, address->ai_protocol);
    if (fd < 0) continue;
    timeval timeout{5, 0}; setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    if (connect(fd, address->ai_addr, address->ai_addrlen) == 0) break;
    close(fd); fd = -1;
  }
  freeaddrinfo(addresses);
  if (fd < 0) throw std::runtime_error("no se pudo conectar al receptor TCP");
  std::size_t sent = 0; const std::string payload = line + "\n";
  while (sent < payload.size()) { const auto n = send(fd, payload.data() + sent, payload.size() - sent, 0); if (n <= 0) { close(fd); throw std::runtime_error("falló el envío TCP"); } sent += static_cast<std::size_t>(n); }
  shutdown(fd, SHUT_WR); close(fd);
}
}

int main(int argc, char** argv) {
  try {
    const Options o = parse(argc, argv);
    ecl::Bits raw;
    if (o.input_kind == "bits") { for (const char c : o.input) { if (c != '0' && c != '1') throw std::invalid_argument("--bits solo acepta 0 y 1"); raw.push_back(c - '0'); } }
    else raw = ecl::bytes_to_bits(o.input);
    const auto start = std::chrono::steady_clock::now();
    ecl::Bits encoded;
    if (o.algorithm == "hamming") encoded = ecl::hamming_encode(raw, 8);
    else {
      encoded = raw; ecl::Bits padded = raw; while (padded.size() % 8U) padded.push_back(0);
      const auto crc = ecl::crc32(ecl::bits_to_bytes(padded, padded.size()));
      for (int shift = 31; shift >= 0; --shift) encoded.push_back(static_cast<int>((crc >> shift) & 1U));
    }
    const auto encode_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - start).count();
    const auto flips = ecl::apply_noise(encoded, o.noise, o.positions, o.ber, o.seed);
    std::ostringstream pos; pos << '['; for (std::size_t i = 0; i < flips.size(); ++i) { if (i) pos << ','; pos << flips[i]; } pos << ']';
    std::ostringstream frame;
    frame << "{\"version\":1,\"algorithm\":\"" << o.algorithm << "\",\"encoding\":\"" << o.input_kind
          << "\",\"original_bits\":" << raw.size() << ",\"block_data_bits\":8,\"encoded_bits\":\""
          << ecl::bits_string(encoded) << "\",\"noise\":{\"mode\":\"" << ecl::json_escape(o.noise)
          << "\",\"ber\":" << o.ber << ",\"seed\":" << o.seed << ",\"flipped_positions\":" << pos.str()
          << "},\"metrics\":{\"encode_ns\":" << encode_ns << "}}";
    if (!o.output.empty()) { std::ofstream file(o.output); if (!file) throw std::runtime_error("no se pudo abrir archivo de salida"); file << frame.str() << '\n'; }
    if (o.port != 0) send_tcp(o.host, o.port, frame.str());
    if (o.output.empty() || o.machine) std::cout << frame.str() << '\n';
    else std::cerr << "Trama guardada en " << o.output << " (" << encoded.size() << " bits, " << flips.size() << " flips)\n";
    return 0;
  } catch (const std::exception& error) { std::cerr << "error: " << error.what() << '\n'; return 2; }
}
