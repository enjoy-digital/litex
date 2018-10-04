#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libdylib.h"

#ifdef LIBDYLIB_CXX
using libdylib::dylib_ref;
namespace libdylib {
#endif
struct dylib_data {
    void *handle;
    const char *path;
    bool dyn_path; // true if path should be freed
    bool freed;
    bool is_self;
};
#ifdef LIBDYLIB_CXX
}
#endif

LIBDYLIB_DEFINE(const void*, get_handle)(dylib_ref lib)
{
    return lib->handle;
}

LIBDYLIB_DEFINE(const char*, get_path)(dylib_ref lib)
{
    return lib->path;
}

#define ERR_MAX_SIZE 2048
static char last_err[ERR_MAX_SIZE];
static bool last_err_set = 0;
static void set_last_error(const char *s)
{
    if (!s)
        s = "NULL error";
    last_err_set = 1;
    strncpy(last_err, s, ERR_MAX_SIZE-1);
}

static dylib_ref dylib_ref_alloc (void *handle, const char *path)
{
    if (handle == NULL)
        return NULL;
    dylib_ref ref = NULL;
    ref = (dylib_ref)malloc(sizeof(*ref));
    ref->handle = handle;
    ref->path = path;
    ref->dyn_path = false;
    ref->freed = false;
    ref->is_self = false;
    return ref;
}

/*
static dylib_ref dylib_ref_alloc_dynamic (void *handle, char *path)
{
    dylib_ref ref = dylib_ref_alloc(handle, path);
    if (ref == NULL)
        return NULL;
    ref->dyn_path = true;
    return ref;
}
*/
static void dylib_ref_free (dylib_ref ref)
{
    if (ref == NULL)
        return;
    if (ref->freed)
        return;
    ref->handle = NULL;
    if (ref->dyn_path)
        free((char*)ref->path);
    ref->freed = true;
    free((void*)ref);
}

static void platform_set_last_error();
static void *platform_raw_open (const char *path);
static void *platform_raw_open_self();
static bool platform_raw_close (void *handle);
static void *platform_raw_lookup (void *handle, const char *symbol);

#define check_null_arg(arg, msg, ret) if (arg == NULL) {set_last_error(msg); return ret; }
#define check_null_handle(handle, ret) check_null_arg(handle, "NULL library handle", ret)
#define check_null_path(path, ret) check_null_arg(path, "NULL library path", ret)

#if defined(LIBDYLIB_UNIX)
#include <dlfcn.h>

static void platform_set_last_error()
{
    set_last_error(dlerror());
}

static void *platform_raw_open (const char *path)
{
    return (void*)dlopen(path, RTLD_LOCAL | RTLD_NOW);
}

static void *platform_raw_open_self()
{
  //return (void*)RTLD_SELF;
  return NULL;
}

static bool platform_raw_close (void *handle)
{
    return dlclose(handle) == 0;
}

static void *platform_raw_lookup (void *handle, const char *symbol)
{
    return dlsym(handle, symbol);
}

// end LIBDYLIB_UNIX
#elif defined(LIBDYLIB_WINDOWS)
#include <windows.h>

static void platform_set_last_error()
{
    // Based on http://stackoverflow.com/questions/1387064
    DWORD code = GetLastError();
    if (!code)
        set_last_error(NULL);
    else
    {
        LPSTR buf = NULL;
        size_t size = FormatMessageA(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
            NULL, code, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPSTR)&buf, 0, NULL);
        set_last_error((const char*)buf);
        LocalFree(buf);
    }
}

static void *platform_raw_open (const char *path)
{
    return (void*)LoadLibrary(path);
}

static void *platform_raw_open_self()
{
    return (void*)GetModuleHandle(NULL);
}

static bool platform_raw_close (void *handle)
{
    return FreeLibrary((HMODULE)handle);
}

static void *platform_raw_lookup (void *handle, const char *symbol)
{
    return (void*)GetProcAddress((HMODULE)handle, symbol);
}

// end LIBDYLIB_WINDOWS
#else
#error "unrecognized platform"
#endif

// All platforms

LIBDYLIB_DEFINE(dylib_ref, open)(const char *path)
{
    check_null_path(path, NULL);
    dylib_ref lib = dylib_ref_alloc(platform_raw_open(path), path);
    if (lib == NULL)
        platform_set_last_error();
    return lib;
}

LIBDYLIB_DEFINE(dylib_ref, open_self)()
{
    dylib_ref lib = dylib_ref_alloc(platform_raw_open_self(), NULL);
    lib->is_self = true;
    return lib;
}

LIBDYLIB_DEFINE(bool, close)(dylib_ref lib)
{
    check_null_handle(lib, 0);
    if (lib->is_self)
    {
        dylib_ref_free(lib);
        return true;
    }
    bool ret = platform_raw_close((void*)lib->handle);
    if (!ret)
        platform_set_last_error();
    else
        dylib_ref_free(lib);
    return ret;
}

LIBDYLIB_DEFINE(void*, lookup)(dylib_ref lib, const char *symbol)
{
    check_null_handle(lib, NULL);
    void *ret = platform_raw_lookup((void*)lib->handle, symbol);
    if (ret == NULL)
        platform_set_last_error();
    return ret;
}

LIBDYLIB_DEFINE(dylib_ref, open_list)(const char *path, ...)
{
    va_list args;
    va_start(args, path);
    dylib_ref ret = LIBDYLIB_NAME(va_open_list)(path, args);
    va_end(args);
    return ret;
}

LIBDYLIB_DEFINE(dylib_ref, va_open_list)(const char *path, va_list args)
{
    const char *curpath = path;
    dylib_ref ret = NULL;
    while (curpath)
    {
        ret = LIBDYLIB_NAME(open)(curpath);
        if (ret)
            break;
        curpath = va_arg(args, const char*);
    }
    return ret;
}

const char *locate_patterns[] =
#if defined(LIBDYLIB_APPLE)
    {"lib%s.dylib", "%s.framework/%s", "%s.dylib", "lib%s.so", "%s.so"}
#elif defined(LIBDYLIB_LINUX)
    {"lib%s.so", "%s.so"}
#elif defined(LIBDYLIB_WINDOWS)
    {"%s.dll", "lib%s.dll"}
#else
    #warning "Falling back to default open_locate patterns"
    {"lib%s.so", "%s.so"}
#endif
;

char *simple_format(const char *pattern, const char *str)
{
    size_t i_in = 0,
           i_out = 0,
           len_p = strlen(pattern),
           len_s = strlen(str),
           len_out = len_p;
    {
        const char *tmp = pattern;
        while ((tmp = strstr(tmp, "%s")))
        {
            len_out += len_s - 2;
            ++tmp;
        }
    }
    char *out = (char*)malloc((len_out + 1) * sizeof(char));
    while (i_in < len_p)
    {
        if (pattern[i_in] == '%' && pattern[i_in + 1] == 's')
        {
            strcpy(out + i_out, str);
            i_in += 2;
            i_out += len_s;
        }
        else if (pattern[i_in] == '%' && pattern[i_in + 1] == '%')
        {
            out[i_out++] = '%';
            i_in += 2;
        }
        else
        {
            out[i_out++] = pattern[i_in++];
        }
    }
    out[len_out] = 0;
    return out;
}

LIBDYLIB_DEFINE(dylib_ref, open_locate)(const char *name)
{
    dylib_ref lib = NULL;
    size_t i;
    for (i = 0; i < (sizeof(locate_patterns) / sizeof(locate_patterns[0])); ++i)
    {
        char *path = simple_format(locate_patterns[i], name);
        lib = LIBDYLIB_NAME(open)(path);
        if (lib != NULL)
            break;
        else
            free(path);
    }
    if (lib == NULL)
        lib = LIBDYLIB_NAME(open)(name);
    return lib;
}

LIBDYLIB_DEFINE(bool, bind)(dylib_ref lib, const char *symbol, void **dest)
{
    *dest = LIBDYLIB_NAME(lookup)(lib, symbol);
    return *dest != 0;
}

LIBDYLIB_DEFINE(bool, find)(dylib_ref lib, const char *symbol)
{
    return LIBDYLIB_NAME(lookup)(lib, symbol) != NULL;
}

LIBDYLIB_DEFINE(bool, find_any)(dylib_ref lib, ...)
{
    va_list args;
    va_start(args, lib);
    bool ret = LIBDYLIB_NAME(va_find_any)(lib, args);
    va_end(args);
    return ret;
}
LIBDYLIB_DEFINE(bool, va_find_any)(dylib_ref lib, va_list args)
{
    const char *cursym = NULL;
    bool ret = 0;
    while (!ret && (cursym = va_arg(args, const char*)))
    {
        if (LIBDYLIB_NAME(lookup)(lib, cursym))
            ret = 1;
    }
    return ret;
}
LIBDYLIB_DEFINE(bool, find_all)(dylib_ref lib, ...)
{
    va_list args;
    va_start(args, lib);
    bool ret = LIBDYLIB_NAME(va_find_all)(lib, args);
    va_end(args);
    return ret;
}
LIBDYLIB_DEFINE(bool, va_find_all)(dylib_ref lib, va_list args)
{
    const char *cursym = NULL;
    bool ret = 1;
    while (ret && (cursym = va_arg(args, const char*)))
    {
        if (!LIBDYLIB_NAME(lookup)(lib, cursym))
            ret = 0;
    }
    return ret;
}

LIBDYLIB_DEFINE(const char*, last_error)()
{
    if (!last_err_set)
        return NULL;
    return last_err;
}

LIBDYLIB_DEFINE(int, get_version)()
{
    return LIBDYLIB_VERSION;
}

LIBDYLIB_DEFINE(const char*, get_version_str())
{
    return LIBDYLIB_VERSION_STR;
}
