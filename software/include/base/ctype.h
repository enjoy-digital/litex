#ifndef __CTYPE_H
#define __CTYPE_H

static inline int isdigit(char c)
{
	return (c >= '0') && (c <= '9');
}

static inline int isxdigit(char c)
{
	return isdigit(c) || ((c >= 'a') && (c <= 'f')) || ((c >= 'A') && (c <= 'F'));
}

static inline int isupper(char c)
{
	return (c >= 'A') && (c <= 'Z');
}

static inline int islower(char c)
{
	return (c >= 'a') && (c <= 'z');
}

static inline unsigned char tolower(unsigned char c)
{
	if (isupper(c))
		c -= 'A'-'a';
	return c;
}

static inline unsigned char toupper(unsigned char c)
{
	if (islower(c))
		c -= 'a'-'A';
	return c;
}

static inline char isspace(unsigned char c)
{
	if(c == ' '
		|| c == '\f'
		|| c == '\n'
		|| c == '\r'
		|| c == '\t'
		|| c == '\v')
		return 1;

	return 0;
}

#endif /* __CTYPE_H */
