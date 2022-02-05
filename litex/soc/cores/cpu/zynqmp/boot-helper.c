void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);

void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr) {
    goto *addr;
}
