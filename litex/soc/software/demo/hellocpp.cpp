#include <stdio.h>

extern "C" void hellocpp(void);
void hellocpp(void)
{
    printf("C++: Hello, world!\n");
}