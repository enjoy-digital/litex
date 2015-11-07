#ifndef __DLFCN_H
#define __DLFCN_H

typedef struct
{
  const char *dli_fname;        /* File name of defining object.  */
  void *dli_fbase;              /* Load address of that object.  */
  const char *dli_sname;        /* Name of nearest symbol.  */
  void *dli_saddr;              /* Exact value of nearest symbol.  */
} Dl_info;

#ifdef __cplusplus
extern "C" {
#endif

extern int dl_iterate_phdr (int (*__callback) (struct dl_phdr_info *,
                                               size_t, void *),
                            void *__data);

/* Fill in *INFO with the following information about ADDRESS.
   Returns 0 iff no shared object's segments contain that address.  */
extern int dladdr (const void *__address, Dl_info *__info);

#ifdef __cplusplus
}
#endif

#endif /* __DLFCN_H */
