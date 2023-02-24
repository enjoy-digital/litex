// Simple framebuffer windows for visualizations
// Copyright (C) 2022 Victor Suarez Rovere <suarezvictor@gmail.com>

#include <SDL2/SDL.h>
#include "sim_fb.h"

bool fb_init(unsigned width, unsigned height, bool vsync, fb_handle_t *handle)
{
    if(SDL_Init(SDL_INIT_VIDEO) < 0)
     return false;

    handle->win = SDL_CreateWindow("LiteX Sim Video Window", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, width, height, SDL_WINDOW_SHOWN);
    if (!handle->win)
      return false;

    handle->renderer = SDL_CreateRenderer(handle->win, -1, vsync ? SDL_RENDERER_ACCELERATED | SDL_RENDERER_TARGETTEXTURE | SDL_RENDERER_PRESENTVSYNC : 0);
    if (!handle->renderer)
      return false;

    handle->texture = SDL_CreateTexture(handle->renderer, SDL_PIXELFORMAT_BGRA32, SDL_TEXTUREACCESS_TARGET, width, height);
    if (!handle->texture)
      return false;

    return true;
}

bool fb_should_quit(void)
{
    SDL_Event event;
    while(SDL_PollEvent(&event))
    {
        switch(event.type)
        {
          case SDL_QUIT:
            return true;
          case SDL_KEYDOWN:
            if(event.key.keysym.sym == SDLK_ESCAPE)
               return true;
        }
    }
    return false;
}

void fb_update(fb_handle_t *handle, const void *buf, size_t stride_bytes)
{
    SDL_UpdateTexture(handle->texture, NULL, buf, stride_bytes);
    SDL_RenderCopy(handle->renderer, handle->texture, NULL, NULL);
    SDL_RenderPresent(handle->renderer);
}

void fb_deinit(fb_handle_t *handle)
{
    SDL_DestroyTexture(handle->texture);
    SDL_DestroyRenderer(handle->renderer);
    SDL_DestroyWindow(handle->win);
    handle->win = NULL;
    SDL_Quit();
}
