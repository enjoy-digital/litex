#ifndef __ID_H
#define __ID_H

#ifdef __cplusplus
extern "C" {
#endif

void get_sysid_formatted(char *sysid);
void get_soc_version(unsigned int *major, unsigned int *minor, unsigned int *subminor, unsigned int *rc);
void get_soc_version_formatted(char *version);

void id_print(void);

#ifdef __cplusplus
}
#endif

#endif /* __ID_H */
