#ifndef __READLINE_H__
#define __READLINE_H__

#include <stdlib.h>
#include <stdio.h>

#define CMD_LINE_BUFFER_SIZE	64

#define PROMPT "\e[92;1mlitex\e[0m> "

#define ESC	27

struct esc_cmds {
	const char *seq;
	char val;
};

#define CTL_CH(c)		((c) - 'a' + 1)

/* Misc. non-Ascii keys */
#define KEY_UP			CTL_CH('p')	/* cursor key Up	*/
#define KEY_DOWN		CTL_CH('n')	/* cursor key Down	*/
#define KEY_RIGHT		CTL_CH('f')	/* Cursor Key Right	*/
#define KEY_LEFT		CTL_CH('b')	/* cursor key Left	*/
#define KEY_HOME		CTL_CH('a')	/* Cursor Key Home	*/
#define KEY_ERASE_TO_EOL	CTL_CH('k')
#define KEY_REFRESH_TO_EOL	CTL_CH('e')
#define KEY_ERASE_LINE		CTL_CH('x')
#define KEY_INSERT		CTL_CH('o')
#define KEY_CLEAR_SCREEN	CTL_CH('l')
#define KEY_DEL7		127
#define KEY_END			133		/* Cursor Key End	*/
#define KEY_PAGEUP		135		/* Cursor Key Page Up	*/
#define KEY_PAGEDOWN		136		/* Cursor Key Page Down	*/
#define KEY_DEL			137		/* Cursor Key Del	*/

#define MAX_CMDBUF_SIZE		256

#define CTL_BACKSPACE		('\b')
#define DEL			255
#define DEL7			127
#define CREAD_HIST_CHAR		('!')

#define HIST_MAX		10

#define putnstr(str,n)	do {			\
		printf ("%.*s", n, str);	\
	} while (0)

#define getcmd_putch(ch)	putchar(ch)
#define getcmd_cbeep()		getcmd_putch('\a')
#define ANSI_CLEAR_SCREEN	"\e[2J\e[;H"

#define BEGINNING_OF_LINE() {			\
	while (num) {				\
		getcmd_putch(CTL_BACKSPACE);	\
		num--;				\
	}					\
}

#define ERASE_TO_EOL() {				\
	if (num < eol_num) {				\
		int t;					\
		for (t = num; t < eol_num; t++)		\
			getcmd_putch(' ');		\
		while (t-- > num)			\
			getcmd_putch(CTL_BACKSPACE);	\
		eol_num = num;				\
	}						\
}

#define REFRESH_TO_EOL() {			\
	if (num < eol_num) {			\
		wlen = eol_num - num;		\
		putnstr(buf + num, wlen);	\
		num = eol_num;			\
	}					\
}

int readline(char *buf, int len);
void hist_init(void);

#endif /* READLINE_H_ */
