#include <stdlib.h>
#include <string.h>

char *getenv(const char *varname) {
  if(!strcmp(varname, "LIBUNWIND_PRINT_APIS") ||
     !strcmp(varname, "LIBUNWIND_PRINT_UNWINDING")) {
    return "1";
  } else {
    return NULL;
  }
}
