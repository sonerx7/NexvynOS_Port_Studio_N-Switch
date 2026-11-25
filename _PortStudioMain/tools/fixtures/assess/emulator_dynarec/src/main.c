#include <SDL2/SDL.h>
/* Synthetic fixture: emulator front end; load_rom reads the cartridge. */
int load_rom(const char *path);
int main(int argc, char **argv) {
    SDL_Init(SDL_INIT_VIDEO);
    SDL_Texture *t = 0; SDL_UpdateTexture(t, 0, 0, 0);
    return load_rom(argv[1]);
}
