#ifndef __LINK_H
#define __LINK_H

#include <stddef.h>
#include <elf.h>

#define ElfW(type) Elf32_##type

struct dl_phdr_info {
  ElfW(Addr) dlpi_addr;
  const char *dlpi_name;
  const ElfW(Phdr) *dlpi_phdr;
  ElfW(Half) dlpi_phnum;
};

#ifdef __cplusplus
extern "C" {
#endif

extern int dl_iterate_phdr (int (*__callback) (struct dl_phdr_info *,
                                               size_t, void *),
                            void *__data);

#ifdef __cplusplus
}
#endif

#endif /* __LINK_H */
