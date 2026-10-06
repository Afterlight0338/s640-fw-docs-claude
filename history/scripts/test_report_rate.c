#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <stdint.h>

static inline uint64_t get_time_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000ULL + (uint64_t)ts.tv_nsec / 1000ULL;
}

int main(int argc, char **argv) {
    const char *devpath = (argc > 1) ? argv[1] : "/dev/hidraw11";
    int fd = open(devpath, O_RDONLY);
    if (fd < 0) {
        perror("Failed to open device");
        return 1;
    }

    printf("Listening on %s... Move the pen on the tablet!\n", devpath);
    printf("Collecting 100 packets to calculate rate...\n");

    unsigned char buf[64];
    uint64_t last_us = 0;
    int count = 0;
    uint64_t total_deltas = 0;
    uint64_t min_delta = 9999999;
    uint64_t max_delta = 0;

    while (count < 100) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0) break;
        uint64_t now_us = get_time_us();
        if (last_us != 0) {
            uint64_t delta = now_us - last_us;
            // Only count active streaming (ignore long pauses)
            if (delta < 50000) { // < 50ms
                total_deltas += delta;
                if (delta < min_delta) min_delta = delta;
                if (delta > max_delta) max_delta = delta;
                count++;
                if (count % 20 == 0) {
                    printf("Packet %3d: delta=%5lu us (%.1f Hz) | raw: ", count, delta, 1000000.0 / delta);
                    for (int i = 0; i < n && i < 8; i++) printf("%02x ", buf[i]);
                    printf("\n");
                }
            }
        }
        last_us = now_us;
    }

    if (count > 0) {
        double avg_delta = (double)total_deltas / count;
        printf("\n=== Rate Benchmark Results ===\n");
        printf("Packets sampled: %d\n", count);
        printf("Average Interval: %.2f ms\n", avg_delta / 1000.0);
        printf("Average Report Rate: %.1f Hz\n", 1000000.0 / avg_delta);
        printf("Min Interval: %.2f ms (%.1f Hz)\n", min_delta / 1000.0, 1000000.0 / min_delta);
        printf("Max Interval: %.2f ms (%.1f Hz)\n", max_delta / 1000.0, 1000000.0 / max_delta);
    }

    close(fd);
    return 0;
}
