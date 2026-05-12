#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import textwrap


def _write(path, contents=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


def test_bios_readline_host_coverage(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    include_dir = tmp_path / "include"
    source = tmp_path / "bios_readline_harness.c"
    binary = tmp_path / "bios_readline_harness"

    _write(include_dir / "libbase" / "uart.h", """
        #ifndef __UART_H
        #define __UART_H
        int uart_read_nonblock(void);
        #endif
    """)
    _write(source, f"""
        #include <stdio.h>
        #include <string.h>

        #define BIOS_CONSOLE_NO_AUTOCOMPLETE

        int uart_read_nonblock(void);
        int uart_read_nonblock(void)
        {{
            return 1;
        }}

        #include "{repo}/litex/soc/software/bios/readline.c"

        #define REQUIRE(cond) do {{ \\
            if (!(cond)) {{ \\
                fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \\
                return 1; \\
            }} \\
        }} while (0)

        static void feed_input(const char *input)
        {{
            int i;

            for (i = strlen(input) - 1; i >= 0; i--)
                ungetc((unsigned char)input[i], stdin);
        }}

        static int read_line_from_input(const char *input, char *buf, int len)
        {{
            memset(buf, 0xa5, len);
            feed_input(input);
            return readline(buf, len);
        }}

        static int test_plain_line_and_ctrl_c(void)
        {{
            char buf[CMD_LINE_BUFFER_SIZE];
            int length;

            length = read_line_from_input("help\\n", buf, sizeof(buf));
            REQUIRE(length == 4);
            REQUIRE(strcmp(buf, "help") == 0);

            length = read_line_from_input("ab\\003cd\\n", buf, sizeof(buf));
            REQUIRE(length == -1);
            REQUIRE(buf[0] == 0);
            return 0;
        }}

        static int test_line_length_is_bounded(void)
        {{
            char buf[8];
            int length;

            length = read_line_from_input("abcdefghijklmnop\\n", buf, sizeof(buf));
            REQUIRE(length == 7);
            REQUIRE(strcmp(buf, "abcdefg") == 0);
            REQUIRE(buf[7] == 0);
            return 0;
        }}

        static int test_backspace_left_insert_and_delete(void)
        {{
            char buf[CMD_LINE_BUFFER_SIZE];
            int length;

            length = read_line_from_input("abc\\bd\\n", buf, sizeof(buf));
            REQUIRE(length == 3);
            REQUIRE(strcmp(buf, "abd") == 0);

            length = read_line_from_input("ac\\033[Db\\n", buf, sizeof(buf));
            REQUIRE(length == 3);
            REQUIRE(strcmp(buf, "abc") == 0);

            length = read_line_from_input("abc\\033[D\\033[D\\033[3~\\n", buf, sizeof(buf));
            REQUIRE(length == 2);
            REQUIRE(strcmp(buf, "ac") == 0);
            return 0;
        }}

        static int test_home_end_and_erase_controls(void)
        {{
            char buf[CMD_LINE_BUFFER_SIZE];
            int length;

            length = read_line_from_input("bc\\033[Ha\\033[Fd\\n", buf, sizeof(buf));
            REQUIRE(length == 4);
            REQUIRE(strcmp(buf, "abcd") == 0);

            length = read_line_from_input("abc\\001\\013z\\n", buf, sizeof(buf));
            REQUIRE(length == 1);
            REQUIRE(strcmp(buf, "z") == 0);

            length = read_line_from_input("abc\\030z\\n", buf, sizeof(buf));
            REQUIRE(length == 1);
            REQUIRE(strcmp(buf, "z") == 0);
            return 0;
        }}

        static int test_history_navigation(void)
        {{
            char buf[CMD_LINE_BUFFER_SIZE];
            int length;

            hist_init();
            length = read_line_from_input("first\\n", buf, sizeof(buf));
            REQUIRE(length == 5);
            length = read_line_from_input("second\\n", buf, sizeof(buf));
            REQUIRE(length == 6);

            length = read_line_from_input("\\033[A\\n", buf, sizeof(buf));
            REQUIRE(length == 6);
            REQUIRE(strcmp(buf, "second") == 0);

            hist_init();
            length = read_line_from_input("first\\n", buf, sizeof(buf));
            REQUIRE(length == 5);
            length = read_line_from_input("second\\n", buf, sizeof(buf));
            REQUIRE(length == 6);
            length = read_line_from_input("\\033[A\\033[A\\n", buf, sizeof(buf));
            REQUIRE(length == 5);
            REQUIRE(strcmp(buf, "first") == 0);

            hist_init();
            length = read_line_from_input("first\\n", buf, sizeof(buf));
            REQUIRE(length == 5);
            length = read_line_from_input("second\\n", buf, sizeof(buf));
            REQUIRE(length == 6);
            length = read_line_from_input("\\033[A\\033[B\\n", buf, sizeof(buf));
            REQUIRE(length == 0);
            REQUIRE(strcmp(buf, "") == 0);
            return 0;
        }}

        int main(void)
        {{
            hist_init();
            if (test_plain_line_and_ctrl_c())
                return 1;
            if (test_line_length_is_bounded())
                return 1;
            if (test_backspace_left_insert_and_delete())
                return 1;
            if (test_home_end_and_erase_controls())
                return 1;
            if (test_history_navigation())
                return 1;
            return 0;
        }}
    """)

    cmd = [
        "gcc",
        "-std=gnu99",
        "-Wall",
        "-Wextra",
        "-Wstrict-prototypes",
        "-Wold-style-definition",
        "-Wmissing-prototypes",
        "-Wno-sign-compare",
        f"-I{include_dir}",
        f"-I{repo}/litex/soc/software",
        f"-I{repo}/litex/soc/software/bios",
        str(source),
        "-o",
        str(binary),
    ]
    subprocess.check_call(cmd)
    subprocess.check_call([str(binary)])
