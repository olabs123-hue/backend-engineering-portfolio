#include <iostream>
#include <cstdint>
// Deterministic bounded exponential retry delay, seconds.
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    int attempts = 0;
    try { attempts = std::stoi(argv[1]); } catch (...) { return 2; }
    if (attempts < 1 || attempts > 1000000) return 2;
    int delay = 1;
    for (int i = 1; i < attempts && delay < 300; ++i) {
        delay = (delay > 150) ? 300 : delay * 2;
    }
    std::cout << delay << '\n';
    return 0;
}
