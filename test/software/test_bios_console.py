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
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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

        static int test_prompt_config(void)
        {{
#ifdef BIOS_CONSOLE_NO_ANSI
            REQUIRE(strcmp(PROMPT, "litex> ") == 0);
            REQUIRE(strcmp(ANSI_BOLD, "") == 0);
            REQUIRE(strcmp(ANSI_RESET, "") == 0);
#else
            REQUIRE(strcmp(PROMPT, "\\033[92;1mlitex\\033[0m> ") == 0);
#endif
            return 0;
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
            if (test_prompt_config())
                return 1;
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
    ]
    subprocess.check_call(cmd + [str(source), "-o", str(binary)])
    subprocess.check_call([str(binary)])

    no_ansi_binary = tmp_path / "bios_readline_harness_no_ansi"
    subprocess.check_call(cmd + ["-DBIOS_CONSOLE_NO_ANSI", str(source), "-o", str(no_ansi_binary)])
    subprocess.check_call([str(no_ansi_binary)])


def test_lite_console_controls_and_bounds(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    include_dir = tmp_path / "include"
    _write(include_dir / "generated" / "csr.h")
    source = tmp_path / "lite.c"
    _write(source, f"""
        #include <assert.h>
        #include <stdio.h>
        #include <string.h>
        #include "{repo}/litex/soc/software/bios/readline_simple.c"
        int uart_read_nonblock(void) {{ return 1; }}

        static int read_input(const char *input, char *buffer, int size)
        {{
            for (int i = strlen(input) - 1; i >= 0; i--) ungetc(input[i], stdin);
            return readline(buffer, size);
        }}
        int main(void)
        {{
            char buffer[8];
            assert(read_input("danger\\003", buffer, sizeof(buffer)) == -1);
            assert(buffer[0] == 0);
            read_input("abc\\bD\\n", buffer, sizeof(buffer));
            assert(!strcmp(buffer, "abD"));
            read_input("ab\\033[Dc\\033[3~d\\033OA\\n", buffer, sizeof(buffer));
            assert(!strcmp(buffer, "abcd"));
            read_input("abc\\033\\n", buffer, sizeof(buffer));
            assert(!strcmp(buffer, "abc"));
            read_input("1234567890\\n", buffer, sizeof(buffer));
            assert(!strcmp(buffer, "1234567"));
            read_input("one\\r\\ntwo\\n", buffer, sizeof(buffer));
            assert(!strcmp(buffer, "one"));
            readline(buffer, sizeof(buffer));
            assert(!strcmp(buffer, "two"));
            return 0;
        }}
    """)
    binary = tmp_path / "lite"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Wextra", "-Werror",
        f"-I{include_dir}", f"-I{repo}/litex/soc/software",
        str(source), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)], timeout=10)
