#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <stdint.h>
#include <poll.h>

static inline uint64_t get_time_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000ULL + (uint64_t)ts.tv_nsec / 1000ULL;
}

int main(int argc, char **argv) {
    const char *data_path = (argc > 1) ? argv[1] : "/dev/hidraw17";
    int duration_sec = (argc > 2) ? atoi(argv[2]) : 30;

    int fd_data = open(data_path, O_RDONLY | O_NONBLOCK);
    if (fd_data < 0) {
        perror("Failed to open digitizer device");
        return 1;
    }

    printf("=================================================================\n");
    printf("   VEIKK S640 LIVE REPORT RATE BENCHMARK (%ds Window)            \n", duration_sec);
    printf("=================================================================\n");
    printf("Listening on: %s (Active OpenTabletDriver Stream)\n", data_path);
    printf(">>> START DRAWING / CIRCLING THE PEN ON THE TABLET NOW <<<\n\n");

    unsigned char buf[64];
    uint64_t start_us = get_time_us();
    uint64_t end_target_us = start_us + (uint64_t)duration_sec * 1000000ULL;
    uint64_t last_pkt_us = 0;
    uint64_t last_print_us = start_us;

    uint64_t total_packets = 0;
    uint64_t valid_interval_count = 0;
    uint64_t total_interval_us = 0;
    uint64_t min_interval_us = UINT64_MAX;
    uint64_t max_interval_us = 0;

    uint32_t hist_1ms = 0;
    uint32_t hist_2ms = 0;
    uint32_t hist_3ms = 0;
    uint32_t hist_4ms = 0;
    uint32_t hist_other = 0;

    struct pollfd pfd = { .fd = fd_data, .events = POLLIN };

    while (get_time_us() < end_target_us) {
        int pr = poll(&pfd, 1, 50);
        if (pr > 0 && (pfd.revents & POLLIN)) {
            while (1) {
                ssize_t n = read(fd_data, buf, sizeof(buf));
                if (n <= 0) break;

                // Check for digitizer report header (0x09 0x41 ...)
                if (n >= 7 && buf[0] == 0x09 && buf[1] == 0x41) {
                    uint64_t now_us = get_time_us();
                    total_packets++;

                    if (last_pkt_us != 0) {
                        uint64_t delta = now_us - last_pkt_us;
                        if (delta > 200 && delta < 30000) {
                            valid_interval_count++;
                            total_interval_us += delta;
                            if (delta < min_interval_us) min_interval_us = delta;
                            if (delta > max_interval_us) max_interval_us = delta;

                            double dt_ms = delta / 1000.0;
                            if (dt_ms <= 1.5) hist_1ms++;
                            else if (dt_ms <= 2.5) hist_2ms++;
                            else if (dt_ms <= 3.5) hist_3ms++;
                            else if (dt_ms <= 4.5) hist_4ms++;
                            else hist_other++;
                        }
                    }
                    last_pkt_us = now_us;
                }
            }
        }

        uint64_t now = get_time_us();
        if (now - last_print_us >= 1000000ULL) {
            double elapsed = (now - start_us) / 1000000.0;
            double current_hz = 0;
            if (valid_interval_count > 0) {
                double avg_interval = (double)total_interval_us / valid_interval_count;
                current_hz = 1000000.0 / avg_interval;
            }
            printf("[%4.1fs / %ds] Packets: %5lu | Active: %5lu | Current Avg: %5.1f Hz\n",
                   elapsed, duration_sec, total_packets, valid_interval_count, current_hz);
            fflush(stdout);
            last_print_us = now;
        }
    }

    printf("\n=================================================================\n");
    printf("                    FINAL BENCHMARK REPORT                       \n");
    printf("=================================================================\n");
    printf("Total Digitizer Packets:    %lu\n", total_packets);
    printf("Valid Continuous Samples:   %lu\n", valid_interval_count);

    if (valid_interval_count > 10) {
        double avg_delta_ms = (double)total_interval_us / valid_interval_count / 1000.0;
        double avg_rate_hz = 1000.0 / avg_delta_ms;
        double min_ms = min_interval_us / 1000.0;
        double max_ms = max_interval_us / 1000.0;

        printf("Average Report Rate:        %.1f Hz\n", avg_rate_hz);
        printf("Average Inter-Packet Delay: %.3f ms\n", avg_delta_ms);
        printf("Min Delay (Peak Speed):     %.3f ms (%.1f Hz)\n", min_ms, 1000.0 / min_ms);
        printf("Max Delay (Floor Speed):    %.3f ms (%.1f Hz)\n", max_ms, 1000.0 / max_ms);
        printf("Jitter Window (Max - Min):  %.3f ms\n", max_ms - min_ms);

        printf("\n--- Inter-Packet Arrival Distribution ---\n");
        printf("  <= 1.5ms (~1000 Hz): %5u (%.1f%%)\n", hist_1ms, (double)hist_1ms / valid_interval_count * 100.0);
        printf("  ~2.0ms   (~500 Hz):  %5u (%.1f%%)\n", hist_2ms, (double)hist_2ms / valid_interval_count * 100.0);
        printf("  ~3.0ms   (~333 Hz):  %5u (%.1f%%)\n", hist_3ms, (double)hist_3ms / valid_interval_count * 100.0);
        printf("  ~4.0ms   (~250 Hz):  %5u (%.1f%%)\n", hist_4ms, (double)hist_4ms / valid_interval_count * 100.0);
        printf("  > 4.5ms  (Spikes):   %5u (%.1f%%)\n", hist_other, (double)hist_other / valid_interval_count * 100.0);
    } else {
        printf("No continuous movement recorded.\n");
    }
    printf("=================================================================\n");

    close(fd_data);
    return 0;
}
