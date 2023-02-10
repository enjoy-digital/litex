// Copyright (C) 2022 Victor Suarez Rovere <suarezvictor@gmail.com>

#ifndef __SIM_FB_H__
#define __SIM_FB_H__

struct SDL_Window;
struct SDL_Renderer;
struct SDL_Texture;

typedef struct
{
    SDL_Window* win;
    SDL_Renderer* renderer;
    SDL_Texture* texture;
} fb_handle_t;

bool fb_init(unsigned width, unsigned height, bool vsync, fb_handle_t *handle);
void fb_update(fb_handle_t *handle, const void *buf, size_t stride_bytes);
void fb_deinit(fb_handle_t *handle);
bool fb_should_quit(void);  

#ifdef __cplusplus
extern "C" {
#endif
uint64_t SDL_GetPerformanceCounter(void);
uint64_t SDL_GetPerformanceFrequency(void);
#ifdef __cplusplus
}
#endif

inline uint64_t higres_ticks() { return SDL_GetPerformanceCounter(); }
inline uint64_t higres_ticks_freq() { return SDL_GetPerformanceFrequency(); }

#endif //__SIM_FB_H__
