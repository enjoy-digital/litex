#ifndef __ENDIAN_H
#define __ENDIAN_H

#ifdef __cplusplus
extern "C" {
#endif

#define __LITTLE_ENDIAN 0
#define __BIG_ENDIAN 1
#define __BYTE_ORDER __BIG_ENDIAN

static inline unsigned int le32toh(unsigned int val)
{
	return (val & 0xff) << 24 |
		(val & 0xff00) << 8 |
		(val & 0xff0000) >> 8 |
		(val & 0xff000000) >> 24;
}

static inline unsigned short le16toh(unsigned short val)
{
	return (val & 0xff) << 8 |
		(val & 0xff00) >> 8;
}

#ifdef __cplusplus
}
#endif

#endif /* __ENDIAN_H */
