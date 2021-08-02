int getpid() {
    return 1;
}

int kill(int pid, int name) {
    _exit(0);
}

void _exit(int code) {
    while (1);
}

