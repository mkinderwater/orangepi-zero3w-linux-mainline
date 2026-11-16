#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

static void logmsg(const char *s) {
    const char *dev[] = {"/dev/console", "/dev/kmsg", "/dev/ttyS0"};
    for (unsigned i=0;i<3;i++) {
        int fd=open(dev[i], O_WRONLY|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);
        if (fd<0) continue;
        if (i==1) dprintf(fd,"<0>OPI3W_PID1: %s\n",s);
        else dprintf(fd,"OPI3W_PID1: %s\n",s);
        close(fd);
    }
}
int main(void) {
    mkdir("/dev",0755);
    if (mount("devtmpfs","/dev","devtmpfs",MS_NOSUID,"")!=0 && errno!=EBUSY)
        logmsg("WARNING devtmpfs mount failed");
    logmsg("START entered PID1 before root/MMC discovery");
    struct utsname u;
    if (uname(&u)==0) {
        char buf[256];
        snprintf(buf,sizeof(buf),"UNAME %s %s %s",u.sysname,u.release,u.machine);
        logmsg(buf);
    } else logmsg("WARNING uname failed");
    logmsg("HOLD no FAT no MMC no switch_root");
    for (;;) { sleep(10); logmsg("ALIVE"); }
}
