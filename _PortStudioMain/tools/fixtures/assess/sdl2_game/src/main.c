#include <SDL2/SDL.h>
/* Synthetic fixture: a tiny SDL2 game loop with sprites and a gamepad. */
int main(int argc, char **argv) {
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER);
    SDL_Window *win = SDL_CreateWindow("t", 0, 0, 640, 480, 0);
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, 0);
    SDL_GameControllerOpen(0);
    int score = 0; /* player score */
    for (;;) { SDL_Event e; while (SDL_PollEvent(&e)) if (e.type == SDL_KEYDOWN) score++; SDL_RenderCopy(ren, 0, 0, 0); }
    return 0;
}
