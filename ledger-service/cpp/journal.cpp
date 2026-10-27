#include <iostream>
#include <limits>
#include <string>
#include <vector>
#include <cstdlib>
// Input: number of signed journal legs, then one signed 64-bit integer per line.
// Exit 0 iff at least two legs sum exactly to zero (overflow-safe).
int main() {
    int n;
    if (!(std::cin >> n) || n < 2 || n > 1000) return 2;
    long long sum = 0;
    for (int i = 0; i < n; ++i) {
        long long x;
        if (!(std::cin >> x)) return 2;
        if ((x > 0 && sum > std::numeric_limits<long long>::max() - x) ||
            (x < 0 && sum < std::numeric_limits<long long>::min() - x)) return 2;
        sum += x;
    }
    if (sum != 0) return 1;
    std::cout << "BALANCED\n";
    return 0;
}
