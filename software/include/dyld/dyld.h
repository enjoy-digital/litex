#ifndef __DYLD_H
#define __DYLD_H

#include <elf.h>

struct dyld_info {
    Elf32_Addr base;
    void *init;
    const char *strtab;
    Elf32_Sym *symtab;
    struct {
        Elf32_Word nbucket;
        Elf32_Word nchain;
        Elf32_Word *bucket;
        Elf32_Word *chain;
    } hash;
};

#ifdef __cplusplus
extern "C" {
#endif

int dyld_load(void *shlib, Elf32_Addr base,
              Elf32_Addr (*resolve_import)(const char *),
              struct dyld_info *info, const char **error_out);
void *dyld_lookup(const char *symbol, struct dyld_info *info);

#ifdef __cplusplus
}
#endif

#endif /* __DYLD_H */
