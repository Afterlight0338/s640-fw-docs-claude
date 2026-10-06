#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s /dev/hidrawX\n", argv[0]); return 1; }

    int fd = open(argv[1], O_RDWR);
    if (fd < 0) { perror(argv[1]); return 1; }

    unsigned char pkt[10] = { 0x00, 0x09, 0x04, 0x2f, 0xeb, 0x00, 0x00, 0x00, 0x00, 0xc0 };

    if (write(fd, pkt, sizeof(pkt)) < 0) { perror("write"); close(fd); return 1; }

    close(fd);
    return 0;
}
