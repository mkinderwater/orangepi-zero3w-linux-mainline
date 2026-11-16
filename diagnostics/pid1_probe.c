#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

/* Storage-independent A733 PID1 probe. Only uses the kernel LED class,
 * never direct MMIO, GPIO exports or PMIC registers.
 */
#define LED_TRIGGER "/sys/class/leds/status_led/trigger"
#define LED_BRIGHT  "/sys/class/leds/status_led/brightness"

static void logmsg(const char *s) {
    const char *dev[] = {"/dev/console", "/dev/kmsg", "/dev/ttyS0"};
    for (unsigned i = 0; i < 3; ++i) {
        int fd = open(dev[i], O_WRONLY | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) continue;
        if (i == 1) dprintf(fd, "<0>OPI3W_PID1: %s\n", s);
        else dprintf(fd, "OPI3W_PID1: %s\n", s);
        close(fd);
    }
}
static int write_sysfs(const char *path, const char *value) {
    int fd = open(path, O_WRONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    const size_t len = strlen(value);
    const ssize_t n = write(fd, value, len);
    const int saved_errno = errno;
    close(fd);
    errno = saved_errno;
    return n == (ssize_t)len ? 0 : -1;
}
static void msleep(long milliseconds) {
    struct timespec req = { milliseconds / 1000,
                            (milliseconds % 1000) * 1000000L };
    while (nanosleep(&req, &req) != 0 && errno == EINTR) {}
}
static int set_brightness(int on) {
    return write_sysfs(LED_BRIGHT, on ? "1\n" : "0\n");
}
static int led_ready(void) {
    /* LED name and PL7 were physically verified on vendor Linux 6.6.98.
     * Wait for the corresponding LED class device to register on this kernel.
     * No LED signal is inconclusive if registration never completes. */
    for (int i = 0; i < 30; ++i) {
        if (access(LED_TRIGGER, W_OK) == 0 &&
            access(LED_BRIGHT, W_OK) == 0 &&
            write_sysfs(LED_TRIGGER, "none\n") == 0 &&
            set_brightness(0) == 0) return 1;
        msleep(500);
    }
    return 0;
}
static void flash(void) {
    if (set_brightness(1) != 0) {
        logmsg("WARNING status_led on failed");
        return;
    }
    msleep(250);
    if (set_brightness(0) != 0)
        logmsg("WARNING status_led off failed");
}
int main(void) {
    mkdir("/dev", 0755);
    mkdir("/sys", 0755);
    if (mount("devtmpfs", "/dev", "devtmpfs", MS_NOSUID, "") != 0 &&
        errno != EBUSY) logmsg("WARNING devtmpfs mount failed");
    logmsg("START entered PID1 before root/MMC discovery");
    struct utsname u;
    if (uname(&u) == 0) {
        char buf[256];
        snprintf(buf, sizeof(buf), "UNAME %s %s %s",
                 u.sysname, u.release, u.machine);
        logmsg(buf);
    } else logmsg("WARNING uname failed");
    if (mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "") != 0 &&
        errno != EBUSY) logmsg("WARNING sysfs mount failed");
    const int ready = led_ready();
    if (ready) {
        logmsg("LED_READY status_led: 3 short PID1 flashes");
        for (int i = 0; i < 3; ++i) {
            flash();
            msleep(250);
        }
    } else {
        logmsg("WARNING status_led unavailable; missing flashes are inconclusive");
    }
    logmsg("HOLD no FAT no MMC no switch_root");
    for (;;) {
        msleep(10000);
        logmsg("ALIVE");
        if (ready) flash();
    }
}
