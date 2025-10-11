#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/utsname.h>

int main(void) {
    struct utsname sysinfo;
    
    printf("Hello, World from HelloApp!\n");

    if (uname(&sysinfo) == 0) {
        printf("System: %s %s\n", sysinfo.sysname, sysinfo.release);
        printf("Machine: %s\n", sysinfo.machine);
    }

    printf("Process ID: %d, Running as UID: %d\n", getpid(), getuid());
    
    return EXIT_SUCCESS;
}